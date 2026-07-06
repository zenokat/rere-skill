"""Unit tests for CodeBuddy background task detection."""

from __future__ import annotations

from evals.runners.background_tasks import find_pending_background_tasks, has_pending_background_tasks


def test_detects_running_background_task_from_taskoutput() -> None:
    """A latest ``TaskOutput`` status of running should be pending."""

    pending = find_pending_background_tasks(
        [
            {
                "type": "function_call_result",
                "name": "Bash",
                "output": {"type": "text", "text": "Status: Running in background with task_id: abc123"},
            },
            {
                "type": "function_call_result",
                "name": "TaskOutput",
                "output": {"type": "text", "text": "Shell ID: abc123\nStatus: running\nDuration: 10m"},
            },
        ]
    )

    assert has_pending_background_tasks(pending) is True
    assert pending.task_ids == ("abc123",)


def test_completed_task_notification_clears_pending_status() -> None:
    """A later completed task notification should clear the running state."""

    pending = find_pending_background_tasks(
        [
            {
                "type": "function_call_result",
                "name": "Bash",
                "output": {"type": "text", "text": "Status: Running in background with task_id: abc123"},
            },
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "<task-notification><task-id>abc123</task-id><status>completed</status></task-notification>",
                    }
                ],
            },
        ]
    )

    assert has_pending_background_tasks(pending) is False
    assert pending.task_ids == ()


def test_final_message_pending_marker_creates_unknown_task() -> None:
    """A final answer that says work is still running should be flagged."""

    pending = find_pending_background_tasks([], final_message="Preview 仍在进行中，等待完成通知。")

    assert has_pending_background_tasks(pending) is True
    assert pending.task_ids == ("unknown",)
    assert pending.final_message_pending is True
