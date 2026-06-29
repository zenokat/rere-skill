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