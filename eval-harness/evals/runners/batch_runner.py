"""Minimal batch runner for isolated WorkBuddy / CodeBuddy evals.

`BatchRunner` orchestrates the evaluator-facing flow: load case materials,
materialize a disposable sandbox, invoke the real CodeBuddy runner, collect
transcript and outputs, run binary graders, write `result.json`, and finally
remove the sandbox.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.cases.case_selector import select_cases
from evals.cases.manifest_models import EvalCase, EvalSuiteManifest, SuiteModelConfig, TargetConfig
from evals.cases.model_config_file import (
    copy_model_config_file,
    fingerprint_model_config_file,
    validate_model_config_file,
)
from evals.graders.preview_matches_baseline import grade_preview_matches_baseline
from evals.graders.preview_file_exists import grade_preview_file_exists
from evals.graders.skill_script_called import grade_skill_script_called
from evals.graders.skill_script_args import grade_skill_script_args
from evals.reports.serializers import write_json
from evals.sandbox.case_sandbox import CaseSandboxBuilder, copy_outputs_to_result, remove_sandbox
from evals.shared.ids import make_batch_id
from evals.shared.output_layout import CaseArtifactLayout, OutputLayout
from evals.shared.windows_paths import as_filesystem_path
from integrations.codebuddy_cli.headless_runner import CodeBuddyHeadlessRunner, HeadlessRunner, HeadlessRunResult


@dataclass(frozen=True)
class RuntimeModelRequest:
    """Resolved model request for one eval batch.

    Args:
        id: CodeBuddy model id to pass to ``--model``. None means use the
            CodeBuddy default.
        config_file: Optional suite-level ``models.json`` to copy into each
            isolated CodeBuddy config directory.
        config_fingerprint: Short fingerprint for result evidence when
            ``config_file`` is present.

    Returns:
        Immutable runtime model request.
    """

    id: str | None
    config_file: Path | None = None
    config_fingerprint: str | None = None


class BatchRunner:
    """Run an eval batch and create the minimal result bundle."""

    def __init__(self, *, repo_root: Path, runner: HeadlessRunner | None = None) -> None:
        """Initialize the batch runner.

        Args:
            repo_root: Repository root used only by the harness, not exposed as
                the agent workspace.
            runner: Optional replaceable runner for tests.

        Returns:
            None.
        """

        self._repo_root = repo_root.resolve()
        self._runner = runner or CodeBuddyHeadlessRunner()
        self._sandbox_builder = CaseSandboxBuilder()

    def run(
        self,
        *,
        manifest: EvalSuiteManifest,
        output_root: Path,
        selected_case_ids: list[str] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Run a full eval batch.

        Args:
            manifest: Loaded suite manifest.
            output_root: Evaluator-provided output root.
            selected_case_ids: Optional case allowlist.
            model: Optional CodeBuddy model id requested for every case.

        Returns:
            `batch.json` payload.
        """

        model_request = _build_runtime_model_request(suite_model=manifest.model, override_model=model)
        batch_started = time.perf_counter()
        batch_id = make_batch_id(manifest.suite_id)
        layout = OutputLayout(output_root=output_root, batch_id=batch_id)
        layout.ensure_batch_dirs()

        cases = select_cases(manifest, selected_case_ids)
        case_payloads = [
            self._run_one_case(manifest=manifest, case=case, layout=layout, model_request=model_request)
            for case in cases
        ]

        cleanup_internal_dir(layout.batch.sandboxes_dir)
        case_counts = _build_case_counts(case_payloads)
        batch_payload = {
            "batch_id": batch_id,
            "suite_id": manifest.suite_id,
            "model": _batch_model_payload(model_request),
            "status": "passed" if case_counts["failed"] == 0 else "failed",
            "case_counts": case_counts,
            "metrics": {
                "duration_ms": _elapsed_ms(batch_started),
                "tokens": _sum_tokens([payload["metrics"]["tokens"] for payload in case_payloads]),
                "cost": {"amount": None, "currency": None},
            },
        }
        write_json(layout.batch.batch_json, batch_payload)
        return batch_payload

    def _run_one_case(
        self,
        *,
        manifest: EvalSuiteManifest,
        case: EvalCase,
        layout: OutputLayout,
        model_request: RuntimeModelRequest,
    ) -> dict[str, Any]:
        """Run one case and write its result files.

        Args:
            manifest: Loaded suite manifest.
            case: Current case.
            layout: Batch output layout.
            model_request: Batch-level model request for this case.

        Returns:
            `result.json` payload.
        """

        case_started_perf = time.perf_counter()
        case_layout = layout.ensure_case_dirs(case.case_id)
        cleanup_errors: list[str] = []

        try:
            sandbox = self._sandbox_builder.create(case=case, sandbox_dir=case_layout.sandbox_dir)
            skill_names = _sandbox_skill_names(sandbox.root)
            skill_entries = _sandbox_skill_entries(sandbox.root)
            target = TargetConfig(
                skill_names=skill_names,
                skill_entries=skill_entries,
                codebuddy_executable="codebuddy",
                model=model_request.id,
                use_container_sandbox=True,
                env=_default_codebuddy_env(case_layout=case_layout, model_request=model_request),
            )
            runner_result = self._runner.run_case(target=target, case=case, workspace_dir=sandbox.root)
            session_missing = _copy_session_raw(
                case_layout=case_layout,
                session_file=runner_result.session_file,
            )
            copy_outputs_to_result(sandbox=sandbox, outputs_dir=case_layout.outputs_dir)
            cleanup_errors.extend(_cleanup_runtime_dirs(case_layout))
            result_payload = self._build_result_payload(
                manifest=manifest,
                case=case,
                case_layout=case_layout,
                runner_result=runner_result,
                duration_ms=_elapsed_ms(case_started_perf),
                model_request=model_request,
                missing_evidence=[*session_missing, *([f"sandbox_cleanup_failed: {item}" for item in cleanup_errors])],
            )
        except Exception as exc:
            cleanup_errors.extend(_cleanup_runtime_dirs(case_layout))
            _ensure_minimal_case_files(case_layout)
            result_payload = self._build_failed_result_payload(
                case=case,
                case_layout=case_layout,
                duration_ms=_elapsed_ms(case_started_perf),
                error=exc,
                cleanup_errors=cleanup_errors,
                model_request=model_request,
            )

        write_json(case_layout.result_json, result_payload)
        return result_payload

    def _build_result_payload(
        self,
        *,
        manifest: EvalSuiteManifest,
        case: EvalCase,
        case_layout: CaseArtifactLayout,
        runner_result: HeadlessRunResult,
        duration_ms: int,
        model_request: RuntimeModelRequest,
        missing_evidence: list[str],
    ) -> dict[str, Any]:
        """Build the successful or runner-failed result payload.

        Args:
            manifest: Loaded suite manifest.
            case: Current case.
            case_layout: Case result paths.
            runner_result: CodeBuddy run result.
            duration_ms: Case duration in milliseconds.
            model_request: Model id and optional config passed to CodeBuddy.
            missing_evidence: Missing evidence labels.

        Returns:
            `result.json` payload.
        """

        graders = self._run_graders(manifest=manifest, case_layout=case_layout)
        status = "completed" if runner_result.exit_code == 0 else "failed"
        score = 1 if status == "completed" and all(item["score"] == 1 for item in graders) else 0
        return {
            "case_id": case.case_id,
            "status": status,
            "verdict": "pass" if score == 1 else "fail",
            "score": score,
            "final_response": runner_result.final_message,
            "model": _case_model_payload(model_request, observed_model=runner_result.model),
            "metrics": {
                "duration_ms": duration_ms,
                "tokens": _normalize_tokens(runner_result.usage),
                "cost": {"amount": None, "currency": None},
            },
            "graders": graders,
            "evidence": {
                "session_path": "session.jsonl",
                "outputs_path": "outputs/",
                "missing": missing_evidence,
            },
        }

    def _build_failed_result_payload(
        self,
        *,
        case: EvalCase,
        case_layout: CaseArtifactLayout,
        duration_ms: int,
        error: Exception,
        cleanup_errors: list[str],
        model_request: RuntimeModelRequest,
    ) -> dict[str, Any]:
        """Build a result payload for harness-level failures.

        Args:
            case: Current case.
            case_layout: Case result paths.
            duration_ms: Case duration in milliseconds.
            error: Raised exception.
            cleanup_errors: Sandbox cleanup errors, if any.
            model_request: Model id and optional config passed to CodeBuddy.

        Returns:
            Failed `result.json` payload.
        """

        missing = ["runner_result"]
        if not case_layout.session_jsonl.exists():
            missing.append("codebuddy_session_jsonl")
        if cleanup_errors:
            missing.extend(f"sandbox_cleanup_failed: {item}" for item in cleanup_errors)
        return {
            "case_id": case.case_id,
            "status": "failed",
            "verdict": "fail",
            "score": 0,
            "final_response": str(error),
            "model": _case_model_payload(model_request, observed_model=None),
            "metrics": {
                "duration_ms": duration_ms,
                "tokens": {"input": None, "output": None, "total": None},
                "cost": {"amount": None, "currency": None},
            },
            "graders": [],
            "evidence": {
                "session_path": "session.jsonl",
                "outputs_path": "outputs/",
                "missing": missing,
            },
        }

    def _run_graders(self, *, manifest: EvalSuiteManifest, case_layout: CaseArtifactLayout) -> list[dict[str, Any]]:
        """Run graders declared by the suite manifest.

        Args:
            manifest: Loaded suite manifest.
            case_layout: Case result paths.

        Returns:
            Grader result list.

        Raises:
            ValueError: If an unknown grader id is declared.
        """

        results: list[dict[str, Any]] = []
        for grader_id in manifest.graders:
            if grader_id == "preview_file_exists":
                results.append(grade_preview_file_exists(outputs_dir=case_layout.outputs_dir))
                continue
            if grader_id == "preview_matches_baseline":
                results.append(grade_preview_matches_baseline(outputs_dir=case_layout.outputs_dir))
                continue
            if grader_id.startswith("skill_script_called:"):
                script_name = grader_id.split(":", 1)[1]
                results.append(
                    grade_skill_script_called(
                        session_jsonl=case_layout.session_jsonl,
                        script_name=script_name,
                    )
                )
                continue
            if grader_id.startswith("skill_script_args:"):
                parts = grader_id.split(":", 2)
                script_name = parts[1]
                arg_pattern = parts[2]
                results.append(
                    grade_skill_script_args(
                        session_jsonl=case_layout.session_jsonl,
                        script_name=script_name,
                        arg_pattern=arg_pattern,
                    )
                )
                continue
            raise ValueError(f"unknown grader: {grader_id}")
        return results


def _default_codebuddy_env(
    *, case_layout: CaseArtifactLayout, model_request: RuntimeModelRequest | None = None
) -> dict[str, str]:
    """Return eval-safe environment variables for the CodeBuddy process.

    Args:
        case_layout: Public and internal paths for the current case.
        model_request: Optional batch-level model request. When it includes a
            suite ``models.json``, the file is copied into CodeBuddy's isolated
            config directory before the child process starts.

    Returns:
        Minimal environment overrides. CodeBuddy state is written under the
        internal case sandbox directory, not the host user home directory.
        Feishu credentials are injected so the self-contained skill can reach
        the real Bitable API; the host PYTHONPATH is never carried over (the
        runner strips it) so the agent cannot resolve host repository modules.
    """

    codebuddy_config_dir = case_layout.codebuddy_config_dir
    codebuddy_config_dir.mkdir(parents=True, exist_ok=True)
    if model_request and model_request.config_file:
        copy_model_config_file(source=model_request.config_file, destination_dir=codebuddy_config_dir)
    env = {
        "PYTHONIOENCODING": "utf-8",
        # Force UTF-8 at the Python level so CodeBuddy's own subprocesses are
        # less likely to write session JSONL using the host code page.
        "PYTHONUTF8": "1",
        "CODEBUDDY_CONFIG_DIR": str(codebuddy_config_dir),
        "RERE_OUTPUT_ROOT": str(case_layout.sandbox_dir / "output"),
        "HTTP_PROXY": "",
        "HTTPS_PROXY": "",
        "http_proxy": "",
        "https_proxy": "",
        "ALL_PROXY": "",
        "all_proxy": "",
        "NO_PROXY": "localhost,127.0.0.1,::1",
        "no_proxy": "localhost,127.0.0.1,::1",
    }
    if model_request and model_request.config_file:
        env["CODEBUDDY_DISABLE_BUILTIN_MODELS"] = "1"
    for key, value in _load_feishu_credentials().items():
        env.setdefault(key, value)
    return env


# Feishu Bitable variables the self-contained revenue-recognition skill needs at
# runtime. These are read from the host (evaluator's) environment / repo `.env`
# and forwarded to the CodeBuddy subprocess so the skill can connect to the real
# Bitable API without bundling secrets inside the skill package.
_FEISHU_CREDENTIAL_VARS = (
    "RERE_FEISHU_APP_ID",
    "RERE_FEISHU_APP_SECRET",
    "RERE_CONFIG_BITABLE_APP_TOKEN",
    "RERE_RESULT_BITABLE_APP_TOKEN",
    "RERE_PROJECT_CATALOG_TABLE_ID",
    "RERE_SOURCE_SPEC_TABLE_ID",
    "RERE_ROLLUP_RULE_TABLE_ID",
)


def _load_feishu_credentials() -> dict[str, str]:
    """Collect Feishu credentials for the CodeBuddy subprocess.

    Args:
        None.

    Returns:
        A dict of credential variables. The host process environment takes
        precedence; otherwise the host repository root `.env` / `.env.local`
        files are parsed in place (without polluting the harness process
        ``os.environ``). Empty values are skipped.
    """

    creds: dict[str, str] = _read_dotenv_into(_repo_root() / ".env")
    creds.update(_read_dotenv_into(_repo_root() / ".env.local"))
    for key in _FEISHU_CREDENTIAL_VARS:
        value = os.environ.get(key)
        if value:
            creds[key] = value
    return {key: value for key, value in creds.items() if value}


def _read_dotenv_into(dotenv_path: Path) -> dict[str, str]:
    """Parse a ``KEY=VALUE`` dotenv file into a dict without touching os.environ.

    Args:
        dotenv_path: Path to a dotenv file.

    Returns:
        Parsed key/value pairs. Supports single- and double-quoted values.
    """

    values: dict[str, str] = {}
    if not dotenv_path.exists():
        return values
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _repo_root() -> Path:
    """Return the repository root hosting this harness.

    Args:
        None.

    Returns:
        Repository root path. ``batch_runner.py`` lives in
        ``<repo>/eval-harness/evals/runners/``, so the repo root is three parents up.
    """

    return Path(__file__).resolve().parents[3]


def _cleanup_runtime_dirs(case_layout: CaseArtifactLayout) -> list[str]:
    """Remove disposable case runtime directories.

    Args:
        case_layout: Case result and runtime paths.

    Returns:
        Human-readable cleanup warnings for the business workspace. CodeBuddy
        state cleanup is best-effort because it may finish writing session
        history after the case has already produced all required evidence.
    """

    cleanup_errors: list[str] = []
    cleanup_error = remove_sandbox(case_layout.sandbox_dir)
    if cleanup_error:
        cleanup_errors.append(f"workspace: {cleanup_error}")
    remove_sandbox(case_layout.codebuddy_config_dir)
    return cleanup_errors


def _copy_session_raw(*, case_layout: CaseArtifactLayout, session_file: str | None) -> list[str]:
    """Copy the raw CodeBuddy session JSONL into the public result directory.

    Args:
        case_layout: Case result paths.
        session_file: Original CodeBuddy session JSONL path captured by the
            headless runner, or None when no session was captured.

    Returns:
        Missing evidence labels. Returns an empty list on success; returns
        ``["codebuddy_session_jsonl"]`` when the session path is missing or the
        source file cannot be read. The raw session is the single source of
        truth for the agent trajectory, so it is copied verbatim with no
        normalization or path scrubbing.

    Notes:
        The content is read and written explicitly (instead of
        ``shutil.copyfile``) because the CodeBuddy session file lives under a
        deep ``codebuddy-state/.../projects/<cwd-id>/`` tree whose path often
        exceeds the Windows ``MAX_PATH`` limit, where ``Path.exists`` and
        ``shutil.copyfile`` fail even though ``read_bytes`` succeeds.
    """

    if not session_file:
        return ["codebuddy_session_jsonl"]
    source = as_filesystem_path(Path(session_file))
    try:
        case_layout.session_jsonl.write_bytes(source.read_bytes())
    except OSError:
        return ["codebuddy_session_jsonl"]
    return []


def _sandbox_skill_names(sandbox_root: Path) -> list[str]:
    """List materialized sandbox skill names.

    Args:
        sandbox_root: Runtime sandbox root.

    Returns:
        Sorted skill names.
    """

    skills_dir = sandbox_root / ".workbuddy" / "skills"
    if not skills_dir.exists():
        return []
    return sorted(path.name for path in skills_dir.iterdir() if path.is_dir())


def _sandbox_skill_entries(sandbox_root: Path) -> list[str]:
    """List fallback `SKILL.md` paths for the prompt.

    Args:
        sandbox_root: Runtime sandbox root.

    Returns:
        POSIX-style sandbox-relative `SKILL.md` paths.
    """

    entries: list[str] = []
    for skill_name in _sandbox_skill_names(sandbox_root):
        skill_entry = sandbox_root / ".workbuddy" / "skills" / skill_name / "SKILL.md"
        if skill_entry.exists():
            entries.append(skill_entry.relative_to(sandbox_root).as_posix())
    return entries


def _ensure_minimal_case_files(case_layout: CaseArtifactLayout) -> None:
    """Ensure failed cases still expose the contracted `outputs/` directory.

    Args:
        case_layout: Case result paths.

    Returns:
        None. A failed case does not fabricate a `session.jsonl`; the missing
        session evidence is recorded by `_build_failed_result_payload`.
    """

    case_layout.outputs_dir.mkdir(parents=True, exist_ok=True)


def cleanup_internal_dir(path: Path) -> None:
    """Remove an internal runtime directory when it is empty or disposable.

    Args:
        path: Directory to remove.

    Returns:
        None. Cleanup is best-effort because case evidence has already been
        copied into the public result bundle before this helper runs.
    """

    remove_sandbox(path)


def _build_runtime_model_request(
    *, suite_model: SuiteModelConfig | None, override_model: str | None
) -> RuntimeModelRequest:
    """Resolve the batch-level model request.

    Args:
        suite_model: Optional model block from ``suite.yaml``.
        override_model: Optional CLI override. It changes only the requested
            model id; a suite ``config_file`` still applies and must define the
            overridden id.

    Returns:
        RuntimeModelRequest used by every case in the batch.

    Raises:
        ValueError: If a suite model config file does not define the effective
            model id.
    """

    cli_model = _normalize_requested_model(override_model)
    requested_id = cli_model or (suite_model.id if suite_model else None)
    config_file = suite_model.config_file if suite_model else None
    if config_file and requested_id:
        validate_model_config_file(config_file=config_file, model_id=requested_id)
    fingerprint = fingerprint_model_config_file(config_file) if config_file else None
    return RuntimeModelRequest(id=requested_id, config_file=config_file, config_fingerprint=fingerprint)


def _batch_model_payload(model_request: RuntimeModelRequest) -> dict[str, Any]:
    """Build the batch-level model evidence payload.

    Args:
        model_request: Resolved batch-level model request.

    Returns:
        JSON-ready model payload for ``batch.json``. The ``config`` field is
        present only when the suite supplied a custom ``models.json``.
    """

    payload: dict[str, Any] = {"requested": model_request.id}
    config_payload = _model_config_payload(model_request)
    if config_payload is not None:
        payload["config"] = config_payload
    return payload


def _case_model_payload(model_request: RuntimeModelRequest, *, observed_model: str | None) -> dict[str, Any]:
    """Build the case-level model evidence payload.

    Args:
        model_request: Resolved batch-level model request.
        observed_model: Model id or name recovered from CodeBuddy evidence.

    Returns:
        JSON-ready model payload for ``result.json``.
    """

    payload: dict[str, Any] = {"requested": model_request.id, "observed": observed_model}
    config_payload = _model_config_payload(model_request)
    if config_payload is not None:
        payload["config"] = config_payload
    return payload


def _model_config_payload(model_request: RuntimeModelRequest) -> dict[str, str] | None:
    """Build public evidence for a custom model config file.

    Args:
        model_request: Resolved batch-level model request.

    Returns:
        Small config evidence payload, or None when no suite config file is
        used. The source file path and API key are intentionally omitted.
    """

    if not model_request.config_file:
        return None
    return {
        "source": "suite_config_file",
        "fingerprint": model_request.config_fingerprint or "",
    }


def _normalize_requested_model(model: str | None) -> str | None:
    """Normalize the optional batch-level model id.

    Args:
        model: Raw model id from the CLI or caller.

    Returns:
        Cleaned model id, or None when the caller wants CodeBuddy's default.
    """

    if model is None:
        return None
    cleaned = model.strip()
    return cleaned or None


def _build_case_counts(case_payloads: list[dict[str, Any]]) -> dict[str, int]:
    """Summarize case counts for `batch.json`.

    Args:
        case_payloads: Per-case result payloads.

    Returns:
        Count dictionary.
    """

    total = len(case_payloads)
    completed = sum(1 for payload in case_payloads if payload["status"] == "completed")
    passed = sum(1 for payload in case_payloads if payload["verdict"] == "pass")
    return {
        "total": total,
        "completed": completed,
        "passed": passed,
        "failed": total - passed,
    }


def _normalize_tokens(usage: dict[str, Any] | None) -> dict[str, int | None]:
    """Normalize CodeBuddy token usage to README fields.

    Args:
        usage: Raw CodeBuddy usage object.

    Returns:
        Token dictionary with input, output, and total keys.
    """

    if not usage:
        return {"input": None, "output": None, "total": None}
    return {
        "input": _first_int(usage, ["inputTokens", "prompt_tokens", "input_tokens"]),
        "output": _first_int(usage, ["outputTokens", "completion_tokens", "output_tokens"]),
        "total": _first_int(usage, ["totalTokens", "total_tokens"]),
    }


def _sum_tokens(token_sets: list[dict[str, int | None]]) -> dict[str, int | None]:
    """Sum batch-level token metrics.

    Args:
        token_sets: Case token dictionaries.

    Returns:
        Batch token dictionary.
    """

    result: dict[str, int | None] = {}
    for key in ["input", "output", "total"]:
        values = [tokens[key] for tokens in token_sets if tokens.get(key) is not None]
        result[key] = sum(int(value) for value in values) if values else None
    return result


def _first_int(payload: dict[str, Any], keys: list[str]) -> int | None:
    """Extract the first integer value from candidate keys.

    Args:
        payload: Raw dictionary.
        keys: Candidate keys.

    Returns:
        Integer value or None.
    """

    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None


def _elapsed_ms(started_at: float) -> int:
    """Calculate elapsed milliseconds.

    Args:
        started_at: `time.perf_counter()` start value.

    Returns:
        Elapsed milliseconds.
    """

    return int((time.perf_counter() - started_at) * 1000)
