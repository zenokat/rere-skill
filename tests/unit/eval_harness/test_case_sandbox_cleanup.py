"""Tests for disposable case sandbox cleanup."""

from __future__ import annotations

import stat
from pathlib import Path

from evals.sandbox.case_sandbox import remove_sandbox


def test_remove_sandbox_cleans_codebuddy_project_state(tmp_path: Path) -> None:
    """Sandbox cleanup should remove transient CodeBuddy project files.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        None.
    """

    sandbox_dir = tmp_path / "case-sandbox"
    session_dir = sandbox_dir / ".codebuddy" / "projects" / "project-id"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "session.jsonl"
    session_file.write_text('{"type":"message"}\n', encoding="utf-8")
    session_file.chmod(stat.S_IREAD)

    cleanup_error = remove_sandbox(sandbox_dir)

    assert cleanup_error is None
    assert not sandbox_dir.exists()