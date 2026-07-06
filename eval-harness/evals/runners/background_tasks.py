"""Helpers for detecting unfinished CodeBuddy background shell tasks.

CodeBuddy can move long-running Bash commands into a background task and later
report progress through ``TaskOutput`` events.  The eval harness needs to know
whether the final assistant answer was produced while such a task was still
running, because copying ``output/`` at that moment can miss artifacts that are
still being generated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_BACKGROUND_START_RE = re.compile(
    r"Status:\s+Running in background with task_id:\s*([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
_SHELL_ID_RE = re.compile(r"Shell ID:\s*([A-Za-z0-9_.-]+)", re.IGNORECASE)
_STATUS_LINE_RE = re.compile(r"^Status:\s*([A-Za-z_ -]+)\s*$", re.IGNORECASE | re.MULTILINE)
_TASK_ID_TAG_RE = re.compile(r"<task-id>\s*([^<\s]+)\s*</task-id>", re.IGNORECASE)
_TASK_STATUS_TAG_RE = re.compile(r"<status>\s*([^<\s]+)\s*</status>", re.IGNORECASE)
_PENDING_FINAL_MESSAGE_MARKERS = (
    "仍在进行",
    "等待完成通知",
    "进程仍在运行",
    "still running",
    "still in progress",
    "waiting for completion",
)


@dataclass(frozen=True)
class PendingBackgroundTasks:
    """Unfinished background task summary.

    Args:
        task_ids: Known CodeBuddy background task ids whose latest status is
            still running.  The tuple can contain ``"unknown"`` when only the
            assistant's final text indicates unfinished work.
        final_message_pending: Whether the final assistant message itself says
            the work is still in progress.

    Returns:
        Immutable summary used by the batch runner before collecting outputs.
    """

    task_ids: tuple[str, ...]
    final_message_pending: bool = False


def find_pending_background_tasks(
    events: list[dict[str, Any]],
    *,
    final_message: str = "",
) -> PendingBackgroundTasks:
    """Find background tasks that were still running at the end of a session.

    Args:
        events: Raw CodeBuddy session events recovered from ``session.jsonl``.
        final_message: Final assistant-facing answer recovered by the runner.

    Returns:
        PendingBackgroundTasks with any unfinished task ids.
    """

    latest_status_by_task: dict[str, str] = {}
    for event in events:
        for task_id, status in _extract_event_task_statuses(event):
            latest_status_by_task[task_id] = status

    pending_ids = [
        task_id
        for task_id, status in sorted(latest_status_by_task.items())
        if _status_is_pending(status)
    ]
    final_pending = _final_message_indicates_pending(final_message)
    if final_pending and not pending_ids:
        pending_ids.append("unknown")

    return PendingBackgroundTasks(task_ids=tuple(pending_ids), final_message_pending=final_pending)


def has_pending_background_tasks(pending: PendingBackgroundTasks) -> bool:
    """Return whether a pending-task summary contains unfinished work.

    Args:
        pending: Summary returned by ``find_pending_background_tasks``.

    Returns:
        True when at least one background task is still pending.
    """

    return bool(pending.task_ids)


def _extract_event_task_statuses(event: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract task status updates from one raw session event.

    Args:
        event: Raw CodeBuddy session event.

    Returns:
        List of ``(task_id, status)`` pairs found in the event.
    """

    statuses: list[tuple[str, str]] = []
    text = _extract_event_text(event)
    if not text:
        return statuses

    started_task_id = _extract_background_start_task_id(text)
    if started_task_id:
        statuses.append((started_task_id, "running"))

    shell_status = _extract_shell_status(text)
    if shell_status is not None:
        statuses.append(shell_status)

    task_notification_status = _extract_task_notification_status(text)
    if task_notification_status is not None:
        statuses.append(task_notification_status)

    return statuses


def _extract_event_text(event: dict[str, Any]) -> str:
    """Extract the human-readable text from a session event.

    Args:
        event: Raw CodeBuddy session event.

    Returns:
        Text payload from tool output or message content, or an empty string.
    """

    output = event.get("output")
    if isinstance(output, dict) and isinstance(output.get("text"), str):
        return output["text"]

    content = event.get("content")
    if isinstance(content, list):
        parts = [
            str(item.get("text"))
            for item in content
            if isinstance(item, dict)
            and item.get("type") in {"input_text", "output_text"}
            and item.get("text")
        ]
        return "\n".join(parts)

    provider_data = event.get("providerData")
    if isinstance(provider_data, dict):
        tool_result = provider_data.get("toolResult")
        if isinstance(tool_result, dict) and isinstance(tool_result.get("content"), str):
            return tool_result["content"]

    return ""


def _extract_background_start_task_id(text: str) -> str | None:
    """Extract a task id from a Bash auto-background message.

    Args:
        text: Tool output text.

    Returns:
        Task id, or None when the text is not a background-start message.
    """

    match = _BACKGROUND_START_RE.search(text)
    return match.group(1) if match else None


def _extract_shell_status(text: str) -> tuple[str, str] | None:
    """Extract the latest ``TaskOutput`` shell status from text.

    Args:
        text: Tool output text.

    Returns:
        ``(task_id, status)`` when both values are present; otherwise None.
    """

    shell_match = _SHELL_ID_RE.search(text)
    status_match = _STATUS_LINE_RE.search(text)
    if not shell_match or not status_match:
        return None
    return shell_match.group(1), status_match.group(1).strip().lower()


def _extract_task_notification_status(text: str) -> tuple[str, str] | None:
    """Extract task status from a CodeBuddy ``<task-notification>`` message.

    Args:
        text: Message text from a meta user notification.

    Returns:
        ``(task_id, status)`` when the notification contains both fields.
    """

    task_id_match = _TASK_ID_TAG_RE.search(text)
    status_match = _TASK_STATUS_TAG_RE.search(text)
    if not task_id_match or not status_match:
        return None
    return task_id_match.group(1), status_match.group(1).strip().lower()


def _status_is_pending(status: str) -> bool:
    """Return whether a CodeBuddy task status means work is unfinished.

    Args:
        status: Raw lowercased status text.

    Returns:
        True for running-like statuses; False for completed or terminal states.
    """

    normalized = status.strip().lower()
    return normalized in {"running", "in progress", "background"}


def _final_message_indicates_pending(final_message: str) -> bool:
    """Return whether the final answer says the work has not completed yet.

    Args:
        final_message: Final assistant answer.

    Returns:
        True when the message contains a known pending-work marker.
    """

    normalized = final_message.lower()
    return any(marker in normalized for marker in _PENDING_FINAL_MESSAGE_MARKERS)
