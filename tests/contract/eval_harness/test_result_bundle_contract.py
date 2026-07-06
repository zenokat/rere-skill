"""Contract tests for the minimal result bundle."""

from __future__ import annotations

import json
from pathlib import Path

from evals.bootstrap import build_eval_harness
from integrations.codebuddy_cli.headless_runner import CodeBuddyHeadlessRunner, HeadlessRunResult


EXAMPLE_SUITE = Path("specs/002-workbuddy-eval-harness/examples/revenue-recognition-real-smoke/suite.yaml")


def test_result_bundle_contains_only_minimal_public_files(tmp_path: Path, monkeypatch) -> None:
    """Completed runs should expose only batch, result, session, and outputs."""

    monkeypatch.setattr(CodeBuddyHeadlessRunner, "run_case", _fake_successful_codebuddy_run)

    batch = build_eval_harness().run_batch(
        suite_path=EXAMPLE_SUITE,
        output_root=tmp_path / "runs",
    )
    batch_dir = tmp_path / "runs" / batch["batch_id"]
    case_dir = batch_dir / "cases" / "revenue-recognition-dine-in-202605"

    assert (batch_dir / "batch.json").exists()
    assert (case_dir / "result.json").exists()
    assert (case_dir / "session.jsonl").exists()
    assert (case_dir / "outputs").is_dir()
    assert not (batch_dir / "_sandboxes").exists()
    for forbidden in [
        "summary.md",
        "artifact-index.json",
        "agent-result.json",
        "baseline.json",
        "compare",
        "run.json",
        "final.json",
        "scorecard.json",
        "stdout.txt",
        "stderr.txt",
        "evidence.md",
        "trajectory.jsonl",
        "workspace",
        "transcript.jsonl",
    ]:
        assert not (batch_dir / forbidden).exists()
        assert not (case_dir / forbidden).exists()

    batch_payload = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))
    assert "cases" not in batch_payload
    assert batch_payload["model"] == {"requested": None}
    assert batch_payload["case_counts"] == {"total": 1, "completed": 1, "passed": 1, "failed": 0}

    result_payload = json.loads((case_dir / "result.json").read_text(encoding="utf-8"))
    assert result_payload["score"] == 1
    assert result_payload["verdict"] == "pass"
    assert result_payload["model"] == {"requested": None, "observed": None}
    assert result_payload["graders"][0]["id"] == "preview_file_exists"
    assert result_payload["graders"][0]["evidence"]["file"].startswith("outputs/")
    assert result_payload["evidence"]["session_path"] == "session.jsonl"
    assert result_payload["evidence"]["outputs_path"] == "outputs/"
    assert result_payload["evidence"]["missing"] == []

    # session.jsonl keeps original event names for grader compatibility, but
    # sensitive command output is redacted before it enters the public bundle.
    session_text = (case_dir / "session.jsonl").read_text(encoding="utf-8")
    assert '"type":"function_call"' in session_text
    assert '"sessionId":"session-test"' in session_text
    assert "contract-secret-value" not in session_text
    assert "<redacted:rere_feishu_app_secret>" in session_text
    assert "sk-contract-hidden-value" not in result_payload["final_response"]
    assert result_payload["evidence"]["redaction"]["enabled"] is True
    assert result_payload["evidence"]["redaction"]["replacement_count"] >= 2


def _fake_successful_codebuddy_run(self, *, target, case, workspace_dir):
    """Simulate a successful CodeBuddy run that writes a preview artifact."""

    assert not (workspace_dir / "instruction.md").exists()
    assert not (workspace_dir / "EVAL_CASE_CONTEXT.md").exists()
    assert not (workspace_dir / ".bin").exists()
    assert not (workspace_dir / ".runtime").exists()
    assert (workspace_dir / ".workbuddy" / "skills" / "revenue-recognition" / "SKILL.md").exists()
    assert (workspace_dir / "input").is_dir()
    assert (workspace_dir / "output").is_dir()
    preview_file = workspace_dir / "output" / "preview.xlsx"
    preview_file.parent.mkdir(parents=True, exist_ok=True)
    preview_file.write_text("preview", encoding="utf-8")
    final_message = "preview generated; apiKey=sk-contract-hidden-value; upload not run."
    session_events = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "<system-reminder>ctx</system-reminder>"}],
            "sessionId": "session-test",
        },
        {"type": "function_call", "name": "Bash", "callId": "call-1", "arguments": "run preview", "sessionId": "session-test"},
        {
            "type": "function_call_result",
            "name": "Bash",
            "callId": "call-1",
            "status": "completed",
            "output": {
                "type": "text",
                "text": f"RERE_FEISHU_APP_SECRET=contract-secret-value\nresult_file: {preview_file}",
            },
            "sessionId": "session-test",
        },
        {"type": "reasoning", "rawContent": [{"type": "reasoning_text", "text": "hidden"}], "sessionId": "session-test"},
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": final_message}], "sessionId": "session-test"},
    ]
    # The fake writes a realistic source session; the harness should redact it
    # while copying into the public result bundle.
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
        session_id="session-test",
        command_line="codebuddy --sandbox container --sandbox-new --sandbox-kill --permission-mode bypassPermissions -p <prompt> --output-format json",
        permission_mode="bypassPermissions",
        final_message=final_message,
        session_file=str(session_path),
        session_events=session_events,
        usage={"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
    )
