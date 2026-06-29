"""Tests for eval output and runtime sandbox path layout.

These tests protect the contract that public result files and disposable runtime
state are kept separate, even when callers provide relative configuration paths.
"""

from pathlib import Path

from evals.shared.output_layout import OutputLayout


def test_relative_runtime_sandbox_root_is_resolved(monkeypatch, tmp_path):
    """Resolve a relative sandbox root before passing it to child processes.

    Args:
        monkeypatch: Pytest helper used to isolate environment variables and cwd.
        tmp_path: Temporary directory used as the caller's working directory.

    Returns:
        None. The assertions verify that internal runtime paths are absolute.
    """

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RERE_EVAL_SANDBOX_ROOT", "relative-sandboxes")

    layout = OutputLayout(output_root=Path("public-results"), batch_id="batch-001")
    case_layout = layout.case_layout("revenue-recognition-dine-in-202605")

    expected_root = (tmp_path / "relative-sandboxes" / "batch-001").resolve()
    assert layout.batch.sandboxes_dir == expected_root
    assert case_layout.sandbox_dir.is_absolute()
    assert case_layout.codebuddy_config_dir.is_absolute()
    assert case_layout.sandbox_dir.is_relative_to(expected_root)
    assert case_layout.codebuddy_config_dir.is_relative_to(expected_root)
