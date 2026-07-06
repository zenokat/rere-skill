"""Binary grader that checks whether the agent called a specific skill script.

This grader reads the CodeBuddy ``session.jsonl`` and looks for ``Bash``
``function_call`` events whose ``command`` argument contains
``scripts/<script_name>.py``.  It is useful for verifying that the agent
followed the expected workflow steps (e.g. running ``list_recog_items`` or
``run_recog_rollup``).

Usage in ``suite.yaml``::

    graders:
      - skill_script_called:list_recog_items
      - skill_script_called:run_recog_rollup
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MAX_SAMPLE_COMMANDS = 3
MAX_COMMAND_LENGTH = 200
COMMAND_START_OR_SEPARATOR = r"(?:^|(?:&&|\|\||[;&|])\s*)"


def grade_skill_script_called(*, session_jsonl: Path, script_name: str) -> dict[str, Any]:
    """Return score 1 when the agent called ``scripts/<script_name>.py``.

    Args:
        session_jsonl: Path to the public ``session.jsonl`` file produced by
            CodeBuddy.
        script_name: Script file name **without** the ``scripts/`` prefix and
            ``.py`` suffix, e.g. ``list_recog_items``.

    Returns:
        Grader result for ``result.json.graders[]``.
    """

    if not session_jsonl.exists():
        return {
            "id": f"skill_script_called:{script_name}",
            "type": "code",
            "score": 0,
            "summary": f"session.jsonl 不存在，无法检测脚本调用。",
            "evidence": {"script_name": script_name, "error": "session.jsonl_not_found"},
        }

    try:
        commands = _extract_bash_commands(session_jsonl)
    except Exception as exc:  # noqa: BLE001
        return {
            "id": f"skill_script_called:{script_name}",
            "type": "code",
            "score": 0,
            "summary": f"解析 session.jsonl 时出错。",
            "evidence": {
                "script_name": script_name,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        }

    matched = _find_script_calls(commands, script_name)

    if matched:
        return {
            "id": f"skill_script_called:{script_name}",
            "type": "code",
            "score": 1,
            "summary": (
                f"Agent 调用了 scripts/{script_name}.py，"
                f"匹配次数={len(matched)}。"
            ),
            "evidence": {
                "script_name": script_name,
                "match_count": len(matched),
                "sample_commands": [_truncate(cmd) for cmd in matched[:MAX_SAMPLE_COMMANDS]],
            },
        }

    return {
        "id": f"skill_script_called:{script_name}",
        "type": "code",
        "score": 0,
        "summary": (
            f"Agent 未调用 scripts/{script_name}.py；"
            f"共检查 {len(commands)} 条 Bash 命令。"
        ),
        "evidence": {
            "script_name": script_name,
            "match_count": 0,
            "bash_command_count": len(commands),
        },
    }


def _extract_bash_commands(session_jsonl: Path) -> list[str]:
    """Extract all ``command`` strings from Bash ``function_call`` events.

    Args:
        session_jsonl: Path to the CodeBuddy session JSONL file.

    Returns:
        A list of command strings. Malformed events are silently skipped.
    """

    commands: list[str] = []
    with session_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "function_call" or event.get("name") != "Bash":
                continue
            try:
                args = json.loads(event.get("arguments", "{}"))
                cmd = args.get("command")
                if isinstance(cmd, str) and cmd.strip():
                    commands.append(cmd.strip())
            except (json.JSONDecodeError, AttributeError):
                continue
    return commands


def _find_script_calls(commands: list[str], script_name: str) -> list[str]:
    """Filter commands that invoke the target skill script.

    Args:
        commands: Full list of Bash command strings.
        script_name: Script file name without prefix/suffix.

    Returns:
        Commands that match the pattern.
    """

    return [cmd for cmd in commands if _command_invokes_script(cmd, script_name)]


def _command_invokes_script(command: str, script_name: str) -> bool:
    """Return whether a Bash command runs the target script.

    Args:
        command: Raw Bash command captured from ``session.jsonl``.
        script_name: Script file name without prefix/suffix.

    Returns:
        True when the command uses either ``scripts/<script>.py`` or first
        changes into a ``scripts`` directory and then invokes ``<script>.py``.
    """

    normalized_command = command.replace("\\", "/")
    if _matches_script_path_invocation(normalized_command, script_name):
        return True
    return _changes_to_scripts_directory(normalized_command) and _matches_bare_script_invocation(
        normalized_command,
        script_name,
    )


def _matches_script_path_invocation(command: str, script_name: str) -> bool:
    """Match invocations that include a ``scripts/<script>.py`` path.

    Args:
        command: Slash-normalized command string.
        script_name: Script file name without prefix/suffix.

    Returns:
        True when the target script path appears in an executable position.
    """

    script_file = re.escape(f"{script_name}.py")
    pattern = re.compile(
        rf"{COMMAND_START_OR_SEPARATOR}"
        rf"(?:uv\s+run\s+(?:--script\s+)?|python(?:\d(?:\.\d+)?)?\s+|py\s+)?"
        rf"[\"']?(?:\./)?(?:[^\s\"';&|]+/)*scripts/{script_file}[\"']?"
        rf"(?=$|[\s;&|])",
        re.IGNORECASE,
    )
    return bool(pattern.search(command))


def _changes_to_scripts_directory(command: str) -> bool:
    """Return whether the command moves into a directory named ``scripts``.

    Args:
        command: Slash-normalized command string.

    Returns:
        True when the command contains a ``cd`` or ``pushd`` step whose target
        path ends in ``scripts``.
    """

    pattern = re.compile(
        rf"{COMMAND_START_OR_SEPARATOR}"
        rf"(?:cd|pushd)\s+[\"']?(?:[^\s\"';&|]+/)*scripts[\"']?"
        rf"(?=$|[\s;&|])",
        re.IGNORECASE,
    )
    return bool(pattern.search(command))


def _matches_bare_script_invocation(command: str, script_name: str) -> bool:
    """Match ``<script>.py`` calls after the shell is already in ``scripts``.

    Args:
        command: Slash-normalized command string.
        script_name: Script file name without prefix/suffix.

    Returns:
        True when the target script file appears in an executable position
        without a ``scripts/`` path prefix.
    """

    script_file = re.escape(f"{script_name}.py")
    pattern = re.compile(
        rf"{COMMAND_START_OR_SEPARATOR}"
        rf"(?:uv\s+run\s+(?:--script\s+)?|python(?:\d(?:\.\d+)?)?\s+|py\s+)?"
        rf"[\"']?(?:\./)?{script_file}[\"']?"
        rf"(?=$|[\s;&|])",
        re.IGNORECASE,
    )
    return bool(pattern.search(command))


def _truncate(text: str, *, max_length: int = MAX_COMMAND_LENGTH) -> str:
    """Truncate a command string for evidence readability.

    Args:
        text: Raw command string.
        max_length: Maximum character length.

    Returns:
        Truncated string with ``...`` suffix when shortened.
    """

    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
