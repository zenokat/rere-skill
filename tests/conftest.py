"""Shared pytest configuration for the repository."""

from __future__ import annotations

import itertools
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_TMP_PATH_COUNTER = itertools.count()


def _inject_src_into_sys_path() -> None:
    """Add `src/`, `tests/` and skill `scripts/lib/` to `sys.path`.

    Args:
        None.

    Returns:
        None. The revenue-recognition business logic lives in the deliverable
        skill package (`skill/revenue-recognition/scripts/lib/`); tests import
        it via the same `cli.`/`core.`/`models.`/`utils.` package paths, so the
        skill lib directory is added here. `src/` is kept for the eval-harness
        modules that remain there.
    """

    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    tests_path = repo_root / "tests"
    skill_lib_path = repo_root / "skill" / "revenue-recognition" / "scripts" / "lib"

    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    if str(tests_path) not in sys.path:
        sys.path.insert(0, str(tests_path))
    if str(skill_lib_path) not in sys.path:
        sys.path.insert(0, str(skill_lib_path))


_inject_src_into_sys_path()


@pytest.fixture(scope="session")
def tmp_path_factory(request: pytest.FixtureRequest) -> pytest.TempPathFactory:
    """Configure pytest temporary paths in a writable location.

    Args:
        request: Pytest fixture request exposing the internal temp factory.

    Returns:
        The configured pytest temporary path factory.
    """

    factory = request.config._tmp_path_factory  # type: ignore[attr-defined]
    base_temp = _resolve_base_temp(Path(__file__).resolve().parents[1])
    factory._basetemp = base_temp.resolve()  # type: ignore[attr-defined]
    return factory


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    """Create per-test temp directories with inherited Windows permissions.

    Args:
        request: Pytest fixture request with the current node name.

    Returns:
        Writable per-test temporary directory.
    """

    repo_root = Path(__file__).resolve().parents[1]
    base_temp = _resolve_base_temp(repo_root)
    safe_name = _safe_node_name(request.node.name)
    path = base_temp / f"{safe_name}-{next(_TMP_PATH_COUNTER)}"
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, mode=0o777)
    _verify_writable(path)
    return path


def _resolve_base_temp(repo_root: Path) -> Path:
    """Choose a writable, process-local base directory for pytest temp files.

    Args:
        repo_root: Repository root path.

    Returns:
        Writable temporary directory path.

    Raises:
        PermissionError: If no candidate directory can be created and written.
    """

    run_name = f"run-{os.getpid()}"
    last_error: OSError | None = None
    for candidate_root in _candidate_base_temp_roots(repo_root):
        candidate = candidate_root / run_name
        try:
            candidate.mkdir(parents=True, exist_ok=True, mode=0o777)
            _verify_writable(candidate)
            return candidate
        except OSError as exc:
            last_error = exc
    raise PermissionError(f"No writable pytest temp directory found. Last error: {last_error}")


def _candidate_base_temp_roots(repo_root: Path) -> list[Path]:
    """Return temp root candidates in preference order.

    Args:
        repo_root: Repository root path.

    Returns:
        Candidate root directory list. `PYTEST_BASETEMP` wins when provided.
    """

    env_value = os.environ.get("PYTEST_BASETEMP")
    candidates: list[Path] = []
    if env_value:
        candidates.append(Path(env_value))
    candidates.append(repo_root / ".tmp" / "pytest-tmp-runs")
    candidates.append(Path(tempfile.gettempdir()) / "rere-agent-pytest")
    return candidates


def _safe_node_name(value: str) -> str:
    """Convert a pytest node name to a safe directory component.

    Args:
        value: Raw pytest node name.

    Returns:
        Filesystem-safe short name.
    """

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    return cleaned[:80] or "test"


def _verify_writable(path: Path) -> None:
    """Verify that a directory supports nested writes.

    Args:
        path: Directory to test.

    Returns:
        None.
    """

    child = path / "child-probe"
    child.mkdir(parents=True, exist_ok=True, mode=0o777)
    probe = child / ".write-probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
