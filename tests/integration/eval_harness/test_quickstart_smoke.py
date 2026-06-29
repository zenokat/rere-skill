"""Quickstart smoke command validation."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cli import run_skill_eval_batch
from integrations.codebuddy_cli.headless_runner import CodeBuddyHeadlessRunner, HeadlessRunResult


EXAMPLE_SUITE = "specs/002-workbuddy-eval-harness/examples/revenue-recognition-real-smoke/suite.yaml"


def test_quickstart_command_runs_minimal_suite(tmp_path: Path, monkeypatch) -> None:
    """The README command should produce the minimal result bundle."""

    monkeypatch.setattr(CodeBuddyHeadlessRunner, "run_case", _fake_successful_codebuddy_run)

    result = CliRunner().invoke(
        run_skill_eval_batch.app,
        [
            "--suite",
            EXAMPLE_SUITE,
            "--output_root",
            str(tmp_path / "quickstart"),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    batch_dir = Path(payload["batch_json"]).parent
    case_dir = batch_dir / "cases" / "revenue-recognition-dine-in-202605"
    assert (batch_dir / "batch.json").exists()
    assert (case_dir / "result.json").exists()
    assert (case_dir / "session.jsonl").exists()
    assert (case_dir / "outputs" / "preview.xlsx").exists()


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
    session_events = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "<system-reminder>ctx</system-reminder>"}],
            "sessionId": "session-quickstart",
        },
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": final_message}], "sessionId": "session-quickstart"},
    ]
    session_path = workspace_dir / "session.jsonl"
    session_path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in session_events) + "\n",
        encoding="utf-8",
    )
    return HeadlessRunResult(
        exit_code=0,
        stdout="",
        stderr="",
        final_json={"status": "ok", "message": final_message},
        session_id="session-quickstart",
        command_line="codebuddy --sandbox container --sandbox-new --sandbox-kill --permission-mode bypassPermissions -p <prompt> --output-format json",
        permission_mode="bypassPermissions",
        final_message=final_message,
        session_file=str(session_path),
        session_events=session_events,
    )