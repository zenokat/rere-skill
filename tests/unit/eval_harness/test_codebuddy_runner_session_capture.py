"""Tests for CodeBuddy command construction and session recovery."""

from __future__ import annotations

import json
from pathlib import Path

from evals.cases.manifest_models import EvalCase, TargetConfig
from evals.shared.windows_paths import as_filesystem_path
from integrations.codebuddy_cli.command_builder import CodeBuddyCommandBuilder
from integrations.codebuddy_cli.headless_runner import (
    _capture_latest_session,
    _list_session_files,
    _parse_stdout_events,
    _project_session_dir,
    _raw_project_session_dir_name,
    _summarize_session_events,
)
from integrations.codebuddy_cli.safety_guard import CodeBuddySafetyGuard, SafetyDecision


def test_codebuddy_command_uses_docker_as_isolation_boundary(tmp_path: Path) -> None:
    """Eval runs should use Docker as the primary isolation boundary."""

    case = EvalCase(
        case_id="workspace-case",
        case_dir=tmp_path / "case",
        instruction_path=tmp_path / "case" / "instruction.md",
        skills_dir=tmp_path / "case" / "skills",
        input_dir=tmp_path / "case" / "input",
        instruction="/revenue-recognition handle 202605 dine-in revenue. Do not upload.",
    )
    command = CodeBuddyCommandBuilder().build(
        target=TargetConfig(
            skill_names=["revenue-recognition"],
            skill_entries=[".workbuddy/skills/revenue-recognition/SKILL.md"],
            use_container_sandbox=True,
        ),
        case=case,
        working_directory=tmp_path,
        safety_decision=SafetyDecision(allowed=True, permission_mode="bypassPermissions", inject_skip_permissions=False),
    )

    assert command.args[0] == "codebuddy"
    assert "-p" in command.args
    assert "--output-format" in command.args
    assert "json" in command.args
    assert "--permission-mode" in command.args
    assert "bypassPermissions" in command.args
    assert "--sandbox" in command.args
    assert "container" in command.args
    assert "--sandbox-new" in command.args
    assert "--sandbox-kill" in command.args
    assert "--allowedTools" not in command.args
    assert "--tools" in command.args
    assert "--dangerously-skip-permissions" not in command.args
    assert "--system-prompt" not in command.args
    assert command.stdin is not None
    prompt = command.stdin
    assert "system-reminder" in prompt
    assert "identity_context" in prompt
    assert "additional_data" in prompt
    assert "connector-status" in prompt
    assert "manually_attached_skills" in prompt
    assert "fallback_path: .workbuddy/skills/revenue-recognition/SKILL.md" in prompt
    assert "EVAL_CASE_CONTEXT.md" not in prompt
    assert "instruction.md" not in prompt
    assert ".bin/" not in prompt
    assert ".runtime/" not in prompt


def test_codebuddy_prompt_omits_manual_attachment_without_slash(tmp_path: Path) -> None:
    """Skills should not be declared as manually attached without slash usage."""

    case = EvalCase(
        case_id="workspace-case",
        case_dir=tmp_path / "case",
        instruction_path=tmp_path / "case" / "instruction.md",
        skills_dir=tmp_path / "case" / "skills",
        input_dir=tmp_path / "case" / "input",
        instruction="Handle 202605 dine-in revenue. Do not upload.",
    )
    command = CodeBuddyCommandBuilder().build(
        target=TargetConfig(
            skill_names=["revenue-recognition"],
            skill_entries=[".workbuddy/skills/revenue-recognition/SKILL.md"],
        ),
        case=case,
        working_directory=tmp_path,
        safety_decision=SafetyDecision(allowed=True, permission_mode="bypassPermissions"),
    )

    assert command.stdin is not None
    assert "manually_attached_skills" not in command.stdin
    assert "/revenue-recognition" not in command.stdin


def test_safety_guard_allows_negative_upload_instruction(tmp_path: Path) -> None:
    """Instructions that prohibit upload should still be runnable."""

    case = EvalCase(
        case_id="negative-upload-case",
        case_dir=tmp_path / "case",
        instruction_path=tmp_path / "case" / "instruction.md",
        skills_dir=tmp_path / "case" / "skills",
        input_dir=tmp_path / "case" / "input",
        instruction="Run validate and preview only. Do not run upload.",
    )

    decision = CodeBuddySafetyGuard().decide(case=case)

    assert decision.allowed is True
    assert decision.permission_mode == "bypassPermissions"


def test_safety_guard_blocks_positive_upload_instruction(tmp_path: Path) -> None:
    """Instructions that request upload should be blocked by the first slice."""

    case = EvalCase(
        case_id="positive-upload-case",
        case_dir=tmp_path / "case",
        instruction_path=tmp_path / "case" / "instruction.md",
        skills_dir=tmp_path / "case" / "skills",
        input_dir=tmp_path / "case" / "input",
        instruction="Run validate, preview, and then upload the result.",
    )

    decision = CodeBuddySafetyGuard().decide(case=case)

    assert decision.allowed is False
    assert decision.blocked_reason is not None


def test_capture_latest_session_extracts_assistant_response_and_events(tmp_path: Path, monkeypatch) -> None:
    """When stdout is empty, runner can recover answer and events from JSONL."""

    config_dir = tmp_path / "codebuddy-home"
    monkeypatch.setenv("CODEBUDDY_CONFIG_DIR", str(config_dir))
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    before = _list_session_files(workspace_dir)

    session_dir = _project_session_dir(workspace_dir)
    session_dir.mkdir(parents=True)
    session_file = session_dir / "session-1.jsonl"
    session_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "handle preview"}],
                        "sessionId": "session-1",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "type": "function_call",
                        "name": "Bash",
                        "callId": "call-1",
                        "arguments": "{\"command\":\"run preview\"}",
                        "sessionId": "session-1",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "need clean source file"}],
                        "providerData": {"model": "glm-test", "usage": {"totalTokens": 3}},
                        "sessionId": "session-1",
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    captured = _capture_latest_session(workspace_dir, before)

    assert captured is not None
    assert captured["session_id"] == "session-1"
    assert captured["assistant_text"] == "need clean source file"
    assert captured["model"] == "glm-test"
    assert captured["session_file"].endswith("session-1.jsonl")
    assert [event["type"] for event in captured["events"]] == ["message", "function_call", "message"]


def test_capture_latest_session_handles_windows_long_project_paths(tmp_path: Path) -> None:
    """Session capture should survive CodeBuddy's deep Windows project paths."""

    config_dir = tmp_path / ("codebuddy-state-" + "c" * 70)
    workspace_dir = tmp_path / ("workspace-" + "w" * 70)
    workspace_dir.mkdir(parents=True)
    session_dir = config_dir / "projects" / _raw_project_session_dir_name(workspace_dir)
    as_filesystem_path(session_dir).mkdir(parents=True)
    session_file = session_dir / "session-long.jsonl"
    as_filesystem_path(session_file).write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "long path captured"}],
                        "providerData": {"model": "glm-test", "usage": {"totalTokens": 12}},
                        "sessionId": "session-long",
                    },
                    ensure_ascii=False,
                )
            ]
        ),
        encoding="utf-8",
    )

    captured = _capture_latest_session(workspace_dir, before={}, config_dir=config_dir)

    assert captured is not None
    assert captured["session_id"] == "session-long"
    assert captured["assistant_text"] == "long path captured"
    assert captured["usage"] == {"totalTokens": 12}
    assert captured["session_file"] == str(session_file)


def test_parse_stdout_event_array_extracts_final_answer() -> None:
    """CodeBuddy JSON event stdout should be usable as transcript evidence."""

    raw_events = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "run preview"}],
            "sessionId": "stdout-session",
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "preview artifact generated"}],
            "providerData": {"model": "glm-test", "usage": {"totalTokens": 9}},
            "sessionId": "stdout-session",
        },
    ]

    events = _parse_stdout_events(json.dumps(raw_events, ensure_ascii=False))
    captured = _summarize_session_events(events)

    assert [event["type"] for event in events] == ["message", "message"]
    assert captured["session_id"] == "stdout-session"
    assert captured["assistant_text"] == "preview artifact generated"
    assert captured["model"] == "glm-test"
    assert captured["usage"] == {"totalTokens": 9}
