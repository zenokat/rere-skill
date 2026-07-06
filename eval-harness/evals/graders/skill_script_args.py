"""Binary grader that checks whether a skill script was called with specific arguments.

This grader reads the CodeBuddy ``session.jsonl`` and looks for ``Bash``
``function_call`` events that invoke ``scripts/<script_name>.py`` **and**
contain a given argument substring (e.g. ``--validate``, ``--preview``,
``--period``).

It is the argument-checking counterpart of ``skill_script_called``: the
latter only verifies that the script was called at all, while this grader
verifies that a particular flag or argument was present in the invocation.

Usage in ``suite.yaml``::

    graders:
      - skill_script_called:run_recog_rollup              # called at all?
      - skill_script_args:run_recog_rollup:--validate        # called with --validate?
      - skill_script_args:run_recog_rollup:--preview         # called with --preview?
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.graders.skill_script_called import (
    MAX_COMMAND_LENGTH,
    MAX_SAMPLE_COMMANDS,
    _extract_bash_commands,
    _find_script_calls,
    _truncate,
)

GRADER_ID_PREFIX = "skill_script_args"


def grade_skill_script_args(
    *,
    session_jsonl: Path,
    script_name: str,
    arg_pattern: str,
) -> dict[str, Any]:
    """Return score 1 when the agent called ``scripts/<script_name>.py`` with *arg_pattern*.

    The grader first filters Bash commands that invoke the target script,
    then checks whether any of those commands also contain *arg_pattern* as a
    substring.

    Args:
        session_jsonl: Path to the public ``session.jsonl`` file produced by
            CodeBuddy.
        script_name: Script file name **without** the ``scripts/`` prefix and
            ``.py`` suffix, e.g. ``run_recog_rollup``.
        arg_pattern: Argument substring that must appear in the same command,
            e.g. ``--validate`` or ``--period``.

    Returns:
        Grader result for ``result.json.graders[]``.
    """

    grader_id = f"{GRADER_ID_PREFIX}:{script_name}:{arg_pattern}"

    if not session_jsonl.exists():
        return _fail(
            grader_id=grader_id,
            summary="session.jsonl 不存在，无法检测脚本参数。",
            evidence={"script_name": script_name, "arg_pattern": arg_pattern, "error": "session.jsonl_not_found"},
        )

    try:
        commands = _extract_bash_commands(session_jsonl)
    except Exception as exc:  # noqa: BLE001
        return _fail(
            grader_id=grader_id,
            summary="解析 session.jsonl 时出错。",
            evidence={
                "script_name": script_name,
                "arg_pattern": arg_pattern,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )

    script_calls = _find_script_calls(commands, script_name)

    if not script_calls:
        return _fail(
            grader_id=grader_id,
            summary=(
                f"Agent 未调用 scripts/{script_name}.py，"
                f"无法检测参数 {arg_pattern}。"
            ),
            evidence={
                "script_name": script_name,
                "arg_pattern": arg_pattern,
                "match_count": 0,
                "bash_command_count": len(commands),
            },
        )

    matched = [cmd for cmd in script_calls if arg_pattern in cmd]

    if matched:
        return {
            "id": grader_id,
            "type": "code",
            "score": 1,
            "summary": (
                f"Agent 调用 scripts/{script_name}.py 时携带了 {arg_pattern}，"
                f"匹配次数={len(matched)}。"
            ),
            "evidence": {
                "script_name": script_name,
                "arg_pattern": arg_pattern,
                "match_count": len(matched),
                "sample_commands": [_truncate(cmd) for cmd in matched[:MAX_SAMPLE_COMMANDS]],
            },
        }

    return _fail(
        grader_id=grader_id,
        summary=(
            f"Agent 调用了 scripts/{script_name}.py 但未携带 {arg_pattern}；"
            f"共 {len(script_calls)} 次脚本调用。"
        ),
        evidence={
            "script_name": script_name,
            "arg_pattern": arg_pattern,
            "match_count": 0,
            "script_call_count": len(script_calls),
        },
    )


def _fail(*, grader_id: str, summary: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Build a failed grader result.

    Args:
        grader_id: Full grader identifier string.
        summary: Human-readable failure summary.
        evidence: Structured evidence for ``result.json``.

    Returns:
        Grader result dictionary with score 0.
    """

    return {
        "id": grader_id,
        "type": "code",
        "score": 0,
        "summary": summary,
        "evidence": evidence,
    }
