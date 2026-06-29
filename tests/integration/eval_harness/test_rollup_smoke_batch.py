"""Integration tests for the revenue-recognition eval suite shape."""

from __future__ import annotations

import json
from pathlib import Path

from evals.bootstrap import build_eval_harness
from integrations.codebuddy_cli.headless_runner import CodeBuddyHeadlessRunner, HeadlessRunResult


EXAMPLE_SUITE = Path("specs/002-workbuddy-eval-harness/examples/revenue-recognition-real-smoke/suite.yaml")


def test_revenue_real_smoke_batch_writes_minimal_outputs(tmp_path: Path, monkeypatch) -> None:
    """Single-case batch should write batch, result, session, and outputs."""

    monkeypatch.setattr(CodeBuddyHeadlessRunner, "run_case", _fake_successful_codebuddy_run)

    batch = build_eval_harness().run_batch(
        suite_path=EXAMPLE_SUITE,
        output_root=tmp_path / "runs",
    )

    batch_dir = tmp_path / "runs" / batch["batch_id"]
    case_dir = batch_dir / "cases" / "revenue-recognition-dine-in-202605"
    result_payload = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))

    assert batch["status"] == "passed"
    assert batch["case_counts"]["total"] == 1
    assert result_payload["graders"][0]["score"] == 1
    assert (case_dir / "session.jsonl").exists()
    assert (case_dir / "outputs" / "preview.xlsx").exists()
    assert not (batch_dir / "_sandboxes").exists()


def _fake_successful_codebuddy_run(self, *, target, case, workspace_dir):
    """Simulate a successful CodeBuddy run and validate sandbox contents."""

    assert not (workspace_dir / "instruction.md").exists()
    assert not (workspace_dir / "EVAL_CASE_CONTEXT.md").exists()
    assert not (workspace_dir / ".bin").exists()
    assert not (workspace_dir / ".runtime").exists()
    assert target.use_container_sandbox is True
    assert "revenue-recognition" in target.skill_names
    assert (workspace_dir / ".workbuddy" / "skills" / "revenue-recognition" / "SKILL.md").exists()
    preview_file = workspace_dir / "output" / "preview.xlsx"
    preview_file.parent.mkdir(parents=True, exist_ok=True)
    preview_file.write_text("preview", encoding="utf-8")
    final_message = "dine-in preview generated."
    session_events = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "<system-reminder>ctx</system-reminder>"}],
            "sessionId": "session-integration",
        },
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": final_message}], "sessionId": "session-integration"},
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
        session_id="session-integration",
        command_line="codebuddy --sandbox container --sandbox-new --sandbox-kill --permission-mode bypassPermissions -p <prompt> --output-format json",
        permission_mode="bypassPermissions",
        final_message=final_message,
        session_file=str(session_path),
        session_events=session_events,
    )