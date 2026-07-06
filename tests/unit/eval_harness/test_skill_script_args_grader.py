"""Unit tests for the skill_script_args eval grader."""

from __future__ import annotations

import json
from pathlib import Path

from evals.graders.skill_script_args import grade_skill_script_args


def _write_session(tmp_path: Path, events: list[dict | str]) -> Path:
    """Write a synthetic session.jsonl from event dicts or raw lines.

    Args:
        tmp_path: Temporary directory for the file.
        events: List of event dicts or raw JSON lines.

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


def test_passes_when_script_called_with_target_arg(tmp_path: Path) -> None:
    """Score 1 when the script is invoked with the expected flag."""

    session = _write_session(tmp_path, [
        _bash_event("uv run scripts/run_recog_rollup.py --validate --recog_id foo"),
    ])
    result = grade_skill_script_args(
        session_jsonl=session, script_name="run_recog_rollup", arg_pattern="--validate",
    )

    assert result["score"] == 1
    assert result["id"] == "skill_script_args:run_recog_rollup:--validate"
    assert result["evidence"]["match_count"] == 1


def test_passes_when_any_invocation_has_target_arg(tmp_path: Path) -> None:
    """Score 1 when at least one of several invocations carries the flag."""

    session = _write_session(tmp_path, [
        _bash_event("uv run scripts/run_recog_rollup.py --recog_id foo"),
        _bash_event("uv run scripts/run_recog_rollup.py --preview --recog_id foo"),
    ])
    result = grade_skill_script_args(
        session_jsonl=session, script_name="run_recog_rollup", arg_pattern="--preview",
    )

    assert result["score"] == 1
    assert result["evidence"]["match_count"] == 1


def test_fails_when_script_called_without_target_arg(tmp_path: Path) -> None:
    """Score 0 when the script is called but without the expected flag."""

    session = _write_session(tmp_path, [
        _bash_event("uv run scripts/run_recog_rollup.py --recog_id foo"),
    ])
    result = grade_skill_script_args(
        session_jsonl=session, script_name="run_recog_rollup", arg_pattern="--validate",
    )

    assert result["score"] == 0
    assert result["evidence"]["match_count"] == 0
    assert result["evidence"]["script_call_count"] == 1


def test_fails_when_script_never_called(tmp_path: Path) -> None:
    """Score 0 when the target script is not invoked at all."""

    session = _write_session(tmp_path, [
        _bash_event("uv run scripts/list_recog_items.py"),
    ])
    result = grade_skill_script_args(
        session_jsonl=session, script_name="run_recog_rollup", arg_pattern="--validate",
    )

    assert result["score"] == 0
    assert "未调用" in result["summary"]


def test_fails_when_session_missing(tmp_path: Path) -> None:
    """Score 0 when session.jsonl does not exist."""

    missing = tmp_path / "nonexistent" / "session.jsonl"
    result = grade_skill_script_args(
        session_jsonl=missing, script_name="run_recog_rollup", arg_pattern="--validate",
    )

    assert result["score"] == 0
    assert "session.jsonl_not_found" in result["evidence"]["error"]


def test_arg_pattern_matches_substring(tmp_path: Path) -> None:
    """The arg_pattern is a plain substring match."""

    session = _write_session(tmp_path, [
        _bash_event("uv run scripts/run_recog_rollup.py --validate --recog_id foo --period 202605"),
    ])
    result = grade_skill_script_args(
        session_jsonl=session, script_name="run_recog_rollup", arg_pattern="--period",
    )

    assert result["score"] == 1
    assert result["evidence"]["match_count"] == 1


def test_evidence_samples_multiple_matches(tmp_path: Path) -> None:
    """Evidence should contain up to 3 sample commands."""

    events = [
        _bash_event(f"uv run scripts/run_recog_rollup.py --validate --recog_id id{i}")
        for i in range(5)
    ]
    session = _write_session(tmp_path, events)
    result = grade_skill_script_args(
        session_jsonl=session, script_name="run_recog_rollup", arg_pattern="--validate",
    )

    assert result["score"] == 1
    assert result["evidence"]["match_count"] == 5
    assert len(result["evidence"]["sample_commands"]) == 3


def test_does_not_match_arg_in_unrelated_command(tmp_path: Path) -> None:
    """Args in non-script Bash commands must not produce false positives."""

    session = _write_session(tmp_path, [
        _bash_event("some_other_tool --validate"),
        _bash_event("uv run scripts/run_recog_rollup.py --recog_id foo"),
    ])
    result = grade_skill_script_args(
        session_jsonl=session, script_name="run_recog_rollup", arg_pattern="--validate",
    )

    assert result["score"] == 0
