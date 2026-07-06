"""Unit tests for the skill_script_called eval grader."""

from __future__ import annotations

import json
from pathlib import Path

from evals.graders.skill_script_called import grade_skill_script_called


def _write_session(tmp_path: Path, events: list[dict | str]) -> Path:
    """Write a synthetic session.jsonl from event dicts or raw lines.

    Args:
        tmp_path: Temporary directory for the file.
        events: List of event dicts or raw JSON lines. Dicts are serialized;
            strings are written verbatim (one line per entry).

    Returns:
        Path to the written session.jsonl.
    """

    session = tmp_path / "session.jsonl"
    with session.open("w", encoding="utf-8") as handle:
        for event in events:
            if isinstance(event, dict):
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            else:
                handle.write(str(event) + "\n")
    return session


def _bash_event(command: str) -> dict:
    """Build a Bash function_call event.

    Args:
        command: The shell command string.

    Returns:
        Event dict suitable for session.jsonl.
    """

    return {
        "type": "function_call",
        "name": "Bash",
        "arguments": json.dumps({"command": command}, ensure_ascii=False),
    }


def _read_event(text: str) -> dict:
    """Build a non-Bash Read function_call event.

    Args:
        text: File path argument.

    Returns:
        Event dict.
    """

    return {
        "type": "function_call",
        "name": "Read",
        "arguments": json.dumps({"file_path": text}, ensure_ascii=False),
    }


def test_passes_when_script_called_in_command(tmp_path: Path) -> None:
    """Score 1 when a Bash command contains scripts/<name>.py."""

    session = _write_session(tmp_path, [
        _bash_event('uv run scripts/list_recog_items.py 2>&1'),
        {"type": "message", "role": "assistant"},
    ])
    result = grade_skill_script_called(session_jsonl=session, script_name="list_recog_items")

    assert result["score"] == 1
    assert result["id"] == "skill_script_called:list_recog_items"
    assert result["evidence"]["match_count"] == 1
    assert "list_recog_items" in result["evidence"]["sample_commands"][0]


def test_passes_when_script_called_with_flags(tmp_path: Path) -> None:
    """Score 1 when the script is invoked with additional flags."""

    session = _write_session(tmp_path, [
        _bash_event(
            'cd /some/dir && uv run scripts/run_recog_rollup.py --validate --recog_id foo'
        ),
    ])
    result = grade_skill_script_called(session_jsonl=session, script_name="run_recog_rollup")

    assert result["score"] == 1
    assert result["evidence"]["match_count"] == 1


def test_fails_when_no_matching_command(tmp_path: Path) -> None:
    """Score 0 when no Bash command references the target script."""

    session = _write_session(tmp_path, [
        _bash_event("ls -la input/"),
        _bash_event("echo hello"),
    ])
    result = grade_skill_script_called(session_jsonl=session, script_name="list_recog_items")

    assert result["score"] == 0
    assert result["evidence"]["match_count"] == 0
    assert result["evidence"]["bash_command_count"] == 2


def test_fails_when_session_missing(tmp_path: Path) -> None:
    """Score 0 when session.jsonl does not exist."""

    missing = tmp_path / "nonexistent" / "session.jsonl"
    result = grade_skill_script_called(session_jsonl=missing, script_name="list_recog_items")

    assert result["score"] == 0
    assert "session.jsonl_not_found" in result["evidence"]["error"]


def test_ignores_non_bash_function_calls(tmp_path: Path) -> None:
    """Non-Bash function_call events must not produce false positives."""

    session = _write_session(tmp_path, [
        _read_event("scripts/list_recog_items.py"),
        _bash_event("ls"),
    ])
    result = grade_skill_script_called(session_jsonl=session, script_name="list_recog_items")

    assert result["score"] == 0


def test_evidence_samples_multiple_matches(tmp_path: Path) -> None:
    """Evidence should contain up to 3 sample commands."""

    events = [_bash_event(f"uv run scripts/run_recog_rollup.py --recog_id id{i}") for i in range(5)]
    events.append(_bash_event("ls"))
    session = _write_session(tmp_path, events)
    result = grade_skill_script_called(session_jsonl=session, script_name="run_recog_rollup")

    assert result["score"] == 1
    assert result["evidence"]["match_count"] == 5
    assert len(result["evidence"]["sample_commands"]) == 3


def test_handles_malformed_json_lines_gracefully(tmp_path: Path) -> None:
    """Malformed JSON lines should be skipped, not crash the grader."""

    session = _write_session(tmp_path, [
        "this is not json",
        {"type": "function_call", "name": "Bash", "arguments": "not-json"},
        _bash_event("uv run scripts/list_recog_items.py"),
    ])
    result = grade_skill_script_called(session_jsonl=session, script_name="list_recog_items")

    assert result["score"] == 1
    assert result["evidence"]["match_count"] == 1


def test_evidence_truncates_long_commands(tmp_path: Path) -> None:
    """Long commands in evidence should be truncated to 200 characters."""

    long_cmd = "uv run scripts/run_recog_rollup.py " + "x" * 300
    session = _write_session(tmp_path, [_bash_event(long_cmd)])
    result = grade_skill_script_called(session_jsonl=session, script_name="run_recog_rollup")

    assert result["score"] == 1
    assert len(result["evidence"]["sample_commands"][0]) <= 203
    assert result["evidence"]["sample_commands"][0].endswith("...")
