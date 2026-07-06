"""CLI contract tests for `run_skill_eval_batch`."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cli import run_skill_eval_batch
from integrations.codebuddy_cli.headless_runner import CodeBuddyHeadlessRunner, HeadlessRunResult


EXAMPLE_SUITE = "specs/002-workbuddy-eval-harness/examples/revenue-recognition-real-smoke/suite.yaml"
runner = CliRunner()


def test_run_skill_eval_batch_stdout_contract(tmp_path: Path, monkeypatch) -> None:
    """CLI stdout should return only batch id, status, counts, and batch path."""

    monkeypatch.setattr(CodeBuddyHeadlessRunner, "run_case", _fake_successful_codebuddy_run)

    result = runner.invoke(
        run_skill_eval_batch.app,
        [
            "--suite",
            EXAMPLE_SUITE,
            "--output_root",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert sorted(payload) == ["batch_id", "batch_json", "case_counts", "status"]
    assert payload["status"] == "passed"
    assert payload["case_counts"] == {"total": 1, "completed": 1, "passed": 1, "failed": 0}
    assert Path(payload["batch_json"]).exists()


def test_run_skill_eval_batch_accepts_model(tmp_path: Path, monkeypatch) -> None:
    """CLI ``--model`` should reach the CodeBuddy target and result bundle."""

    def fake_model_codebuddy_run(self, *, target, case, workspace_dir):
        """Simulate a model-specific CodeBuddy run.

        Args:
            self: Patched runner instance.
            target: Runtime target built by the harness.
            case: Current eval case.
            workspace_dir: Disposable sandbox workspace.

        Returns:
            A successful ``HeadlessRunResult`` carrying the observed model.
        """

        assert target.model == "glm-5.2"
        preview_file = workspace_dir / "output" / "preview.xlsx"
        preview_file.parent.mkdir(parents=True, exist_ok=True)
        preview_file.write_text("preview", encoding="utf-8")
        final_message = "preview file generated with requested model."
        session_path = workspace_dir / "session.jsonl"
        session_path.write_text(
            json.dumps(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": final_message}],
                    "providerData": {"model": "glm-5.2", "usage": {"totalTokens": 8}},
                    "sessionId": "session-model",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return HeadlessRunResult(
            exit_code=0,
            stdout="",
            stderr="",
            final_json={"status": "ok", "message": final_message},
            session_id="session-model",
            command_line="codebuddy --model glm-5.2 -p <prompt> --output-format json",
            permission_mode="bypassPermissions",
            final_message=final_message,
            session_file=str(session_path),
            model="glm-5.2",
            usage={"totalTokens": 8},
        )

    monkeypatch.setattr(CodeBuddyHeadlessRunner, "run_case", fake_model_codebuddy_run)

    result = runner.invoke(
        run_skill_eval_batch.app,
        [
            "--suite",
            EXAMPLE_SUITE,
            "--output_root",
            str(tmp_path / "runs"),
            "--model",
            "glm-5.2",
        ],
    )

    assert result.exit_code == 0
    stdout_payload = json.loads(result.stdout)
    batch_json = Path(stdout_payload["batch_json"])
    batch_payload = json.loads(batch_json.read_text(encoding="utf-8"))
    case_result = json.loads(
        (batch_json.parent / "cases" / "revenue-recognition-dine-in-202605" / "result.json").read_text(
            encoding="utf-8"
        )
    )
    assert batch_payload["model"] == {"requested": "glm-5.2"}
    assert case_result["model"] == {"requested": "glm-5.2", "observed": "glm-5.2"}


def test_suite_model_config_is_copied_to_isolated_codebuddy_config(tmp_path: Path, monkeypatch) -> None:
    """Suite ``model.config_file`` should be copied into CodeBuddy's runtime config."""

    suite_yaml, model_config_file = _build_model_config_suite(tmp_path)

    def fake_model_config_codebuddy_run(self, *, target, case, workspace_dir):
        """Verify the runtime target sees the suite model and copied config.

        Args:
            self: Patched runner instance.
            target: Runtime target built by the harness.
            case: Current eval case.
            workspace_dir: Disposable sandbox workspace.

        Returns:
            A successful ``HeadlessRunResult`` carrying the observed model.
        """

        assert target.model == "glm-5"
        assert target.env["CODEBUDDY_DISABLE_BUILTIN_MODELS"] == "1"
        copied_config = Path(target.env["CODEBUDDY_CONFIG_DIR"]) / "models.json"
        assert copied_config.read_text(encoding="utf-8") == model_config_file.read_text(encoding="utf-8")

        preview_file = workspace_dir / "output" / "preview.xlsx"
        preview_file.parent.mkdir(parents=True, exist_ok=True)
        preview_file.write_text("preview", encoding="utf-8")
        final_message = "preview file generated with suite model config."
        session_path = workspace_dir / "session.jsonl"
        session_path.write_text(
            json.dumps(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": final_message}],
                    "providerData": {"model": "glm-5", "usage": {"totalTokens": 8}},
                    "sessionId": "session-suite-model",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return HeadlessRunResult(
            exit_code=0,
            stdout="",
            stderr="",
            final_json={"status": "ok", "message": final_message},
            session_id="session-suite-model",
            command_line="codebuddy --model glm-5 -p <prompt> --output-format json",
            permission_mode="bypassPermissions",
            final_message=final_message,
            session_file=str(session_path),
            model="glm-5",
            usage={"totalTokens": 8},
        )

    monkeypatch.setattr(CodeBuddyHeadlessRunner, "run_case", fake_model_config_codebuddy_run)

    result = runner.invoke(
        run_skill_eval_batch.app,
        [
            "--suite",
            str(suite_yaml),
            "--output_root",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0
    stdout_payload = json.loads(result.stdout)
    batch_json = Path(stdout_payload["batch_json"])
    batch_payload = json.loads(batch_json.read_text(encoding="utf-8"))
    case_result = json.loads((batch_json.parent / "cases" / "case-a" / "result.json").read_text(encoding="utf-8"))
    assert batch_payload["model"]["requested"] == "glm-5"
    assert batch_payload["model"]["config"]["source"] == "suite_config_file"
    assert batch_payload["model"]["config"]["fingerprint"].startswith("sha256:")
    assert case_result["model"]["requested"] == "glm-5"
    assert case_result["model"]["observed"] == "glm-5"
    assert case_result["model"]["config"] == batch_payload["model"]["config"]


def _fake_successful_codebuddy_run(self, *, target, case, workspace_dir):
    """Simulate a successful CodeBuddy run."""

    assert not (workspace_dir / "instruction.md").exists()
    assert not (workspace_dir / "EVAL_CASE_CONTEXT.md").exists()
    assert not (workspace_dir / ".bin").exists()
    assert not (workspace_dir / ".runtime").exists()
    preview_file = workspace_dir / "output" / "preview.xlsx"
    preview_file.parent.mkdir(parents=True, exist_ok=True)
    preview_file.write_text("preview", encoding="utf-8")
    final_message = "preview file generated."
    return HeadlessRunResult(
        exit_code=0,
        stdout="",
        stderr="",
        final_json={"status": "ok", "message": final_message},
        session_id="session-cli",
        command_line="codebuddy --sandbox container --sandbox-new --sandbox-kill --permission-mode bypassPermissions -p <prompt> --output-format json",
        permission_mode="bypassPermissions",
        final_message=final_message,
        session_events=[
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "<system-reminder>ctx</system-reminder>"}],
                "sessionId": "session-cli",
            },
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": final_message}], "sessionId": "session-cli"},
        ],
    )


def _build_model_config_suite(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal suite that declares ``model.id`` and ``config_file``.

    Args:
        tmp_path: Temporary directory for the suite and config file.

    Returns:
        Tuple of ``(suite_yaml, model_config_file)``.
    """

    suite_dir = tmp_path / "model-suite"
    case_dir = suite_dir / "cases" / "case-a"
    case_dir.mkdir(parents=True)
    (case_dir / "instruction.md").write_text("Generate a preview file.", encoding="utf-8")
    (case_dir / "input").mkdir()
    (case_dir / "skills").mkdir()
    model_config_file = suite_dir / "models.json"
    model_config_file.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "glm-5",
                        "apiKey": "secret",
                        "url": "https://example.test/v1/chat/completions",
                    }
                ],
                "availableModels": ["glm-5"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    suite_yaml = suite_dir / "suite.yaml"
    suite_yaml.write_text(
        "\n".join(
            [
                "suite_id: model-suite",
                "model:",
                "  id: glm-5",
                "  config_file: models.json",
                "graders:",
                "  - preview_file_exists",
                "cases:",
                "  - case-a",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return suite_yaml, model_config_file
