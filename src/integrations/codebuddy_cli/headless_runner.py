"""Headless CodeBuddy CLI runner for eval harness cases.

This module invokes `codebuddy -p`, captures stdout, and also recovers the
visible answer and tool events from CodeBuddy local session JSONL files. Session
capture is intentionally best-effort because CodeBuddy may write stdout and
session files differently across versions.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from evals.cases.manifest_models import EvalCase, TargetConfig
from evals.shared.windows_paths import as_filesystem_path, without_windows_long_path_prefix
from integrations.codebuddy_cli.command_builder import CodeBuddyCommand, CodeBuddyCommandBuilder
from integrations.codebuddy_cli.safety_guard import CodeBuddySafetyGuard, SafetyDecision


@dataclass
class HeadlessRunResult:
    """Result of running one eval case through CodeBuddy.

    Attributes:
        exit_code: CodeBuddy process exit code.
        stdout: Captured stdout, or synthesized JSON when session recovery wins.
        stderr: Captured stderr.
        final_json: Parsed or synthesized final result payload.
        session_id: CodeBuddy session id when available.
        command_line: Human-readable command line for evidence.
        permission_mode: Requested CodeBuddy permission mode.
        final_message: Final assistant-facing answer.
        safety_decision: Pre-run safety decision.
        session_file: Recovered CodeBuddy session JSONL path.
        session_events: Recovered CodeBuddy session events.
        model: Model recorded in the session.
        usage: Token usage recorded in the session.
    """

    exit_code: int
    stdout: str
    stderr: str
    final_json: dict[str, Any]
    session_id: str | None
    command_line: str
    permission_mode: str
    final_message: str = ""
    safety_decision: SafetyDecision | None = None
    session_file: str | None = None
    session_events: list[dict[str, Any]] = field(default_factory=list)
    model: str | None = None
    usage: dict[str, Any] | None = None


class HeadlessRunner(Protocol):
    """Minimal protocol used by the batch runner."""

    def run_case(self, *, target: TargetConfig, case: EvalCase, workspace_dir: Path) -> HeadlessRunResult:
        """Run a single eval case.

        Args:
            target: Runtime target configuration.
            case: Current eval case.
            workspace_dir: Disposable sandbox workspace.

        Returns:
            HeadlessRunResult for this case.
        """


class CodeBuddyHeadlessRunner:
    """Real CodeBuddy CLI headless runner."""

    def __init__(self, *, timeout_seconds: int = 900) -> None:
        """Initialize the runner.

        Args:
            timeout_seconds: Max seconds allowed for one case.
        """

        self._timeout_seconds = timeout_seconds
        self._guard = CodeBuddySafetyGuard()
        self._builder = CodeBuddyCommandBuilder()

    def run_case(self, *, target: TargetConfig, case: EvalCase, workspace_dir: Path) -> HeadlessRunResult:
        """Run one case by invoking CodeBuddy CLI.

        Args:
            target: Runtime target configuration.
            case: Current eval case.
            workspace_dir: Disposable sandbox workspace.

        Returns:
            HeadlessRunResult with stdout and recovered session evidence.
        """

        safety = self._guard.decide(case=case)
        command = self._builder.build(
            target=target,
            case=case,
            working_directory=workspace_dir,
            safety_decision=safety,
        )
        if not safety.allowed:
            return self._blocked_result(case=case, command=command, safety=safety)

        executable = shutil.which(target.codebuddy_executable)
        if executable is None:
            message = f"CodeBuddy CLI not found: {target.codebuddy_executable}"
            return HeadlessRunResult(
                exit_code=127,
                stdout="",
                stderr=message,
                final_json={"status": "error", "stage": "runtime_environment", "message": message},
                session_id=None,
                command_line=command.display,
                permission_mode=safety.permission_mode,
                final_message=message,
                safety_decision=safety,
            )


        if target.use_container_sandbox and shutil.which("docker") is None:
            message = "Docker CLI not found; Docker is required for eval isolation."
            return HeadlessRunResult(
                exit_code=127,
                stdout="",
                stderr=message,
                final_json={"status": "error", "stage": "runtime_environment", "message": message},
                session_id=None,
                command_line=command.display,
                permission_mode=safety.permission_mode,
                final_message=message,
                safety_decision=safety,
            )
        args = [executable, *command.args[1:]]
        env = _build_isolated_env(base=os.environ, overrides=target.env)
        config_dir = _codebuddy_config_dir(env)
        session_files_before = _list_session_files(workspace_dir, config_dir=config_dir)
        try:
            completed = subprocess.run(
                args,
                cwd=workspace_dir,
                env=env,
                input=command.stdin,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return HeadlessRunResult(
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=(exc.stderr or "") + "\nCodeBuddy run timed out.",
                final_json={"status": "error", "stage": "runtime_environment", "message": "CodeBuddy run timed out."},
                session_id=None,
                command_line=command.display,
                permission_mode=safety.permission_mode,
                final_message="CodeBuddy run timed out.",
                safety_decision=safety,
            )

        session_capture = _capture_latest_session(workspace_dir, session_files_before, config_dir=config_dir)
        stdout = completed.stdout
        stdout_events = _parse_stdout_events(stdout)
        final_json = _parse_final_json(stdout, completed.returncode)
        session_id = _extract_session_id(final_json)
        final_message = _extract_message(final_json, stdout, completed.stderr)
        session_file = None
        session_events: list[dict[str, Any]] = []
        model = None
        usage = None

        if session_capture:
            session_id = session_id or session_capture["session_id"]
            session_file = session_capture.get("session_file")
            session_events = list(session_capture.get("events") or [])
            model = session_capture.get("model")
            usage = session_capture.get("usage")
            assistant_text = str(session_capture.get("assistant_text") or "")
            if assistant_text:
                final_message = assistant_text
                final_json = {
                    "status": "ok" if completed.returncode == 0 else "error",
                    "session_id": session_id,
                    "message": final_message,
                    "source": "codebuddy_session_jsonl",
                    "model": model,
                    "usage": usage,
                    "session_file": session_file,
                }
                stdout = json.dumps(final_json, ensure_ascii=False, indent=2)
        elif stdout_events:
            stdout_capture = _summarize_session_events(stdout_events)
            session_id = session_id or stdout_capture.get("session_id")
            session_events = stdout_events
            model = stdout_capture.get("model")
            usage = stdout_capture.get("usage")
            assistant_text = str(stdout_capture.get("assistant_text") or "")
            if assistant_text:
                final_message = assistant_text
                final_json = {
                    "status": "ok" if completed.returncode == 0 else "error",
                    "session_id": session_id,
                    "message": final_message,
                    "source": "codebuddy_stdout_events",
                    "model": model,
                    "usage": usage,
                }
                stdout = json.dumps(final_json, ensure_ascii=False, indent=2)

        return HeadlessRunResult(
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=completed.stderr,
            final_json=final_json,
            session_id=session_id,
            command_line=command.display,
            permission_mode=safety.permission_mode,
            final_message=final_message,
            safety_decision=safety,
            session_file=session_file,
            session_events=session_events,
            model=model,
            usage=usage,
        )

    def _blocked_result(self, *, case: EvalCase, command: CodeBuddyCommand, safety: SafetyDecision) -> HeadlessRunResult:
        """Build a blocked result.

        Args:
            case: Current eval case.
            command: Prepared CodeBuddy command.
            safety: Safety decision.

        Returns:
            Blocked HeadlessRunResult.
        """

        message = safety.blocked_reason or "Blocked by safety policy."
        return HeadlessRunResult(
            exit_code=4,
            stdout="",
            stderr=message,
            final_json={"status": "blocked", "case_id": case.case_id, "message": message},
            session_id=None,
            command_line=command.display,
            permission_mode=safety.permission_mode,
            final_message=message,
            safety_decision=safety,
        )


def _parse_final_json(stdout: str, exit_code: int) -> dict[str, Any]:
    """Parse CodeBuddy stdout into a final payload.

    Args:
        stdout: Captured stdout.
        exit_code: CodeBuddy process exit code.

    Returns:
        Parsed JSON object, or a fallback payload.
    """

    text = stdout.strip()
    if not text:
        return {"status": "error" if exit_code else "ok", "message": ""}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"status": "ok" if exit_code == 0 else "error", "value": parsed}
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    return {"status": "error" if exit_code else "ok", "message": text}


def _parse_stdout_events(stdout: str) -> list[dict[str, Any]]:
    """Parse CodeBuddy JSON stdout when it is a raw event array.

    Args:
        stdout: Captured CodeBuddy stdout.

    Returns:
        List of event dictionaries, or an empty list when stdout is not an
        event stream.
    """

    text = stdout.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


# Host environment variables that can leak the original development repository
# location into the CodeBuddy subprocess. These are stripped before the eval
# runs so the agent cannot `import cli.*` or `import core.*` against the host
# checkout. CodeBuddy still receives everything it needs to run (PATH,
# SystemRoot, TEMP, credentials injected by the harness, etc.).
_REPO_LEAK_VARS = {
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "VIRTUAL_ENV",
    "REPO_ROOT",
    "RERE_REPO_ROOT",
}


def _build_isolated_env(*, base: dict[str, str], overrides: dict[str, str]) -> dict[str, str]:
    """Build the environment for the CodeBuddy subprocess.

    Args:
        base: Host process environment (e.g. ``os.environ``).
        overrides: Harness-provided overrides, including injected credentials.

    Returns:
        A new environment dict with repository-leaking variables removed and
        ``PYTHONPATH`` explicitly emptied, then ``overrides`` applied on top.

    Notes:
        A blocklist is used instead of an allowlist because a strict allowlist
        would have to enumerate OS-essential variables (PATH, SystemRoot, TEMP,
        USERPROFILE, ...) which is fragile and non-portable. The blocklist only
        targets the known leak channels while preserving normal execution.
    """

    env = {key: value for key, value in base.items() if key not in _REPO_LEAK_VARS}
    # Explicit empty value (rather than deleting) so the variable cannot be
    # re-injected by inherited mechanisms downstream.
    env["PYTHONPATH"] = ""
    env.update(overrides)
    return env


def _codebuddy_config_dir(env: dict[str, str] | None = None) -> Path:
    """Return the CodeBuddy config directory.

    Args:
        None.

    Returns:
        Config directory path, honoring CODEBUDDY_CONFIG_DIR when provided.
    """

    source_env = env if env is not None else os.environ
    configured = source_env.get("CODEBUDDY_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codebuddy"


def _project_session_dir(workspace_dir: Path, config_dir: Path | None = None) -> Path:
    """Return the shortened session directory used by tests.

    Args:
        workspace_dir: Workspace directory passed to CodeBuddy.

    Returns:
        Shortened project session directory path.
    """

    root = config_dir or _codebuddy_config_dir()
    return root / "projects" / _project_session_dir_name(workspace_dir)


def _project_session_dirs(workspace_dir: Path, config_dir: Path | None = None) -> list[Path]:
    """Return possible CodeBuddy session directories for a workspace.

    Args:
        workspace_dir: Workspace directory passed to CodeBuddy.

    Returns:
        Candidate directories. Real CodeBuddy uses the raw cwd id; tests may use
        the shortened id to avoid Windows path-length problems.
    """

    root = config_dir or _codebuddy_config_dir()
    projects_dir = root / "projects"
    raw_dir = projects_dir / _raw_project_session_dir_name(workspace_dir)
    short_dir = projects_dir / _project_session_dir_name(workspace_dir)
    if raw_dir == short_dir:
        return [raw_dir]
    return [raw_dir, short_dir]


def _raw_project_session_dir_name(workspace_dir: Path) -> str:
    """Build the exact cwd id used by CodeBuddy project history.

    Args:
        workspace_dir: Workspace directory passed to CodeBuddy.

    Returns:
        Raw normalized cwd id. CodeBuddy lowercases the Windows drive letter in
        its project history directory name (e.g. ``d-tmp-...`` for ``D:\\tmp``),
        so the leading drive letter is lowercased here to match.
    """

    normalized = str(workspace_dir.resolve()).replace(":", "").replace("\\", "-").replace("/", "-")
    if normalized and normalized[0].isupper() and len(normalized) > 1 and normalized[1] == "-":
        normalized = normalized[0].lower() + normalized[1:]
    return normalized


def _project_session_dir_name(workspace_dir: Path) -> str:
    """Build a short, stable project directory name.

    Args:
        workspace_dir: Workspace directory passed to CodeBuddy.

    Returns:
        Shortened normalized cwd id with a hash suffix when needed.
    """

    normalized = _raw_project_session_dir_name(workspace_dir)
    max_length = 96
    if len(normalized) <= max_length:
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    prefix_length = max_length - len(digest) - 1
    return f"{normalized[:prefix_length]}-{digest}"


def _list_session_files(workspace_dir: Path, config_dir: Path | None = None) -> dict[Path, float]:
    """List CodeBuddy session files that exist before a run.

    Args:
        workspace_dir: Workspace directory passed to CodeBuddy.

    Returns:
        Mapping from JSONL file path to modification time.
    """

    files: dict[Path, float] = {}
    for session_dir in _project_session_dirs(workspace_dir, config_dir=config_dir):
        filesystem_dir = as_filesystem_path(session_dir)
        if not filesystem_dir.exists():
            continue
        files.update(
            {
                without_windows_long_path_prefix(path): path.stat().st_mtime
                for path in filesystem_dir.glob("*.jsonl")
                if path.is_file()
            }
        )
    return files


def _capture_latest_session(
    workspace_dir: Path, before: dict[Path, float], config_dir: Path | None = None
) -> dict[str, Any] | None:
    """Read the newly created or updated CodeBuddy session JSONL.

    Args:
        workspace_dir: Workspace directory passed to CodeBuddy.
        before: Session file mtimes captured before the run.

    Returns:
        Session summary and events, or None when no session file is found.
    """

    candidates: list[Path] = []
    for session_dir in _project_session_dirs(workspace_dir, config_dir=config_dir):
        filesystem_dir = as_filesystem_path(session_dir)
        if not filesystem_dir.exists():
            continue
        for path in filesystem_dir.glob("*.jsonl"):
            if not path.is_file():
                continue
            logical_path = without_windows_long_path_prefix(path)
            previous_mtime = before.get(logical_path)
            current_mtime = path.stat().st_mtime
            if previous_mtime is None or current_mtime > previous_mtime:
                candidates.append(logical_path)
    if not candidates:
        return None

    latest = max(candidates, key=lambda item: as_filesystem_path(item).stat().st_mtime)
    messages = _read_jsonl(latest)
    if not messages:
        return None

    summary = _summarize_session_events(messages)
    summary["session_file"] = str(latest)
    if not summary.get("session_id"):
        summary["session_id"] = latest.stem
    return summary


def _summarize_session_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract final assistant text and metadata from session-like events.

    Args:
        events: Raw CodeBuddy JSONL events or JSON stdout event array.

    Returns:
        Summary containing session id, final assistant text, model, usage, and
        the original event list.
    """

    assistant_messages = [
        item for item in events if item.get("type") == "message" and item.get("role") == "assistant"
    ]
    assistant = assistant_messages[-1] if assistant_messages else {}
    provider_data = assistant.get("providerData") if isinstance(assistant.get("providerData"), dict) else {}
    message_payload = assistant.get("message") if isinstance(assistant.get("message"), dict) else {}
    session_id = _first_session_id(events) or assistant.get("sessionId")
    return {
        "session_id": str(session_id) if session_id else None,
        "assistant_text": _join_output_text(assistant.get("content", [])),
        "model": provider_data.get("model") or provider_data.get("requestModelName"),
        "usage": provider_data.get("usage") or message_payload.get("usage"),
        "events": events,
    }


def _first_session_id(events: list[dict[str, Any]]) -> str | None:
    """Return the first session id found in raw events.

    Args:
        events: Raw CodeBuddy events.

    Returns:
        Session id, or None when not present.
    """

    for event in events:
        value = event.get("sessionId") or event.get("session_id")
        if value:
            return str(value)
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file and ignore malformed lines.

    Args:
        path: JSONL file path.

    Returns:
        Parsed JSON object list. Each line gets a best-effort mojibake recovery
        pass before parsing, because CodeBuddy's own writer may emit CJK text
        using the host code page rather than UTF-8.
    """

    items: list[dict[str, Any]] = []
    try:
        for line in as_filesystem_path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            recovered = _recover_mojibake_text(line)
            try:
                parsed = json.loads(recovered)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                items.append(parsed)
    except OSError:
        return []
    return items


# CodeBuddy sometimes writes CJK content through a misconfigured code page,
# producing mojibake (e.g. U+FFFD replacements or latin-1-read bytes of GBK).
# The root cause is in the writer, which this harness cannot control; this
# helper only provides a best-effort, opt-in recovery on the read side.
_MOJIBAKE_MARKERS = ("�", "Ã", "Â", "é", "æ")


def _recover_mojibake_text(text: str) -> str:
    """Best-effort recovery of CJK text mangled by a wrong code page.

    Args:
        text: One JSONL line as read with UTF-8 + errors="replace".

    Returns:
        Recovered text when a reverse encoding chain clearly increases the CJK
        ratio; otherwise the input unchanged. Normal ASCII/UTF-8 text passes
        through at zero cost.
    """

    if not text or ("�" not in text and not any(marker in text for marker in _MOJIBAKE_MARKERS)):
        return text
    best = text
    best_ratio = _cjk_ratio(text)
    for src_enc in ("utf-8", "latin-1"):
        try:
            byte_form = text.encode(src_enc, errors="ignore")
        except UnicodeEncodeError:
            continue
        for dst_enc in ("utf-8", "gbk", "gb18030"):
            if src_enc == dst_enc:
                continue
            try:
                candidate = byte_form.decode(dst_enc, errors="ignore")
            except (UnicodeDecodeError, LookupError):
                continue
            ratio = _cjk_ratio(candidate)
            if ratio > best_ratio:
                best, best_ratio = candidate, ratio
    return best


def _cjk_ratio(text: str) -> float:
    """Return the fraction of CJK characters in non-whitespace text.

    Args:
        text: Input text.

    Returns:
        Ratio in [0, 1]. Used only to compare recovery candidates.
    """

    meaningful = [ch for ch in text if not ch.isspace()]
    if not meaningful:
        return 0.0
    cjk = sum(1 for ch in meaningful if "一" <= ch <= "鿿")
    return cjk / len(meaningful)


def _join_output_text(content: object) -> str:
    """Join assistant output_text blocks from CodeBuddy message content.

    Args:
        content: Message content field.

    Returns:
        Joined assistant text.
    """

    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "output_text" and item.get("text"):
            parts.append(str(item["text"]))
    return "\n".join(parts).strip()


def _extract_session_id(final_json: dict[str, Any]) -> str | None:
    """Extract a session id from CodeBuddy stdout JSON.

    Args:
        final_json: Parsed final stdout JSON.

    Returns:
        Session id when present.
    """

    value = final_json.get("session_id") or final_json.get("sessionId")
    return str(value) if value else None


def _extract_message(final_json: dict[str, Any], stdout: str, stderr: str) -> str:
    """Extract a final answer from stdout or stderr.

    Args:
        final_json: Parsed final stdout JSON.
        stdout: Captured stdout.
        stderr: Captured stderr.

    Returns:
        Final answer text or fallback diagnostic text.
    """

    for key in ["message", "final_message", "result", "summary"]:
        value = final_json.get(key)
        if value:
            return str(value)
    if not stdout.strip():
        return ""
    return (stderr or stdout or "").strip()[:1000]
