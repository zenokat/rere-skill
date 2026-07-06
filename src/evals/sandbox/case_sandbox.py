"""Create and clean disposable per-case sandboxes.

The sandbox is the only workspace the agent should see. Case inputs are copied
into it, skills are materialized under `.workbuddy/skills/`, and business
outputs are collected from its `output/` directory after the run. The case
`instruction.md` is sent as the first user message and is not copied into the
workspace.
"""

from __future__ import annotations

import os
import shutil
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path

from evals.cases.manifest_models import EvalCase


@dataclass(frozen=True)
class CaseSandbox:
    """Resolved paths inside a case sandbox.

    Args:
        root: Sandbox root directory.
        input_dir: Copied input directory.
        output_dir: Writable business output directory.
        workbuddy_skills_dir: WorkBuddy-style skill root.
        skill_entries: Explicit fallback paths to each materialized `SKILL.md`.
        skill_names: Materialized skill names.

    Returns:
        Immutable sandbox path bundle.
    """

    root: Path
    input_dir: Path
    output_dir: Path
    workbuddy_skills_dir: Path
    skill_entries: list[str] = field(default_factory=list)
    skill_names: list[str] = field(default_factory=list)


class CaseSandboxBuilder:
    """Materialize case folders into disposable runtime sandboxes."""

    def create(self, *, case: EvalCase, sandbox_dir: Path) -> CaseSandbox:
        """Create a clean sandbox for one case.

        Args:
            case: Loaded case folder.
            sandbox_dir: Target sandbox root.

        Returns:
            CaseSandbox describing the materialized runtime environment.
        """

        if sandbox_dir.exists():
            shutil.rmtree(sandbox_dir)
        sandbox_dir.mkdir(parents=True)

        input_dir = sandbox_dir / "input"
        _copy_tree(_effective_input_dir(case), input_dir)

        output_dir = sandbox_dir / "output"
        output_dir.mkdir()

        workbuddy_skills_dir = sandbox_dir / ".workbuddy" / "skills"
        workbuddy_skills_dir.mkdir(parents=True)
        skill_entries: list[str] = []
        skill_names: list[str] = []

        # Determine the effective skills source: case-level, or suite-level fallback.
        effective_skills_dir = _effective_skills_dir(case)
        for skill_source in sorted(effective_skills_dir.iterdir(), key=lambda path: path.name):
            if not skill_source.is_dir():
                continue
            skill_target = workbuddy_skills_dir / skill_source.name
            _copy_tree(skill_source, skill_target)
            skill_entry = skill_target / "SKILL.md"
            if skill_entry.exists():
                skill_entries.append(_sandbox_relative(skill_entry, sandbox_dir))
                skill_names.append(skill_source.name)

        return CaseSandbox(
            root=sandbox_dir,
            input_dir=input_dir,
            output_dir=output_dir,
            workbuddy_skills_dir=workbuddy_skills_dir,
            skill_entries=skill_entries,
            skill_names=skill_names,
        )


def _effective_input_dir(case: EvalCase) -> Path:
    """Return the effective input source directory for a case.

    When the case-level ``input/`` directory is empty and a suite-level
    shared input path is available, the shared path is returned instead.

    Args:
        case: Loaded case folder.

    Returns:
        Directory path to copy into the sandbox ``input/``.
    """

    if _dir_is_empty(case.input_dir) and case.suite_shared_input and case.suite_shared_input.is_dir():
        return case.suite_shared_input
    return case.input_dir


def _effective_skills_dir(case: EvalCase) -> Path:
    """Return the effective skills source directory for a case.

    When the case-level ``skills/`` directory is empty (no subdirectories)
    and a suite-level shared skills path is available, the shared path is
    returned instead.

    Args:
        case: Loaded case folder.

    Returns:
        Directory path to copy into the sandbox ``.workbuddy/skills/``.
    """

    if _dir_is_empty(case.skills_dir) and case.suite_shared_skills and case.suite_shared_skills.is_dir():
        return case.suite_shared_skills
    return case.skills_dir


def _dir_is_empty(path: Path) -> bool:
    """Check whether a directory exists but contains no subdirectories.

    Args:
        path: Directory path to check.

    Returns:
        True if the directory exists and has no child directories; False
        otherwise (including when the directory does not exist).
    """

    if not path.is_dir():
        return False
    return not any(child.is_dir() for child in path.iterdir())


def copy_outputs_to_result(*, sandbox: CaseSandbox, outputs_dir: Path) -> None:
    """Copy sandbox `output/` into the public case `outputs/` directory.

    Args:
        sandbox: Runtime sandbox.
        outputs_dir: Public result `outputs/` path.

    Returns:
        None.
    """

    if outputs_dir.exists():
        shutil.rmtree(outputs_dir)
    outputs_dir.mkdir(parents=True)
    if not sandbox.output_dir.exists():
        return
    for item in sandbox.output_dir.iterdir():
        target = outputs_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def remove_sandbox(sandbox_dir: Path) -> str | None:
    """Remove a runtime sandbox with Windows-friendly retries.

    Args:
        sandbox_dir: Sandbox root.

    Returns:
        None on success, otherwise a short error message.
    """

    if not sandbox_dir.exists():
        return None

    last_error: OSError | None = None
    for attempt in range(6):
        _remove_transient_tool_state_dirs(sandbox_dir)
        try:
            _remove_tree(sandbox_dir)
            return None
        except OSError as exc:
            last_error = exc
            time.sleep(min(0.2 * (attempt + 1), 1.0))
    return str(last_error) if last_error else None


def _remove_transient_tool_state_dirs(sandbox_dir: Path) -> None:
    """Remove known transient tool-state directories before full cleanup.

    Args:
        sandbox_dir: Sandbox root.

    Returns:
        None. Cleanup is best-effort; the full sandbox removal reports the final
        error if the directory still cannot be removed.
    """

    for child in [sandbox_dir / ".tmp", sandbox_dir / ".codebuddy" / "projects"]:
        if child.exists():
            try:
                _remove_tree(child)
            except OSError:
                pass


def _remove_tree(path: Path) -> None:
    """Remove a directory tree while relaxing read-only file attributes.

    Args:
        path: Directory or file path to remove.

    Returns:
        None.
    """

    if not path.exists():
        return
    if path.is_file() or path.is_symlink():
        _remove_leaf(path)
        return

    try:
        shutil.rmtree(path, onexc=_make_writable)
        return
    except OSError as first_error:
        try:
            _remove_tree_bottom_up(path)
        except OSError:
            pass
        if not path.exists():
            return
        try:
            shutil.rmtree(path, onexc=_make_writable)
        except OSError as second_error:
            raise second_error from first_error


def _remove_tree_bottom_up(path: Path) -> None:
    """Remove a directory tree from leaves to root.

    Args:
        path: Directory path to remove.

    Returns:
        None.
    """

    for child in sorted(path.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if child.is_file() or child.is_symlink():
            _remove_leaf(child)
        elif child.exists():
            _remove_empty_dir(child)
    _remove_empty_dir(path)


def _remove_leaf(path: Path) -> None:
    """Remove one file-like path after relaxing read-only attributes.

    Args:
        path: File or symlink path.

    Returns:
        None.
    """

    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    path.unlink(missing_ok=True)


def _remove_empty_dir(path: Path) -> None:
    """Remove one empty directory after relaxing read-only attributes.

    Args:
        path: Directory path.

    Returns:
        None.
    """

    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
    except OSError:
        pass
    path.rmdir()


def _make_writable(function, path: str, exc_info) -> None:
    """Relax file attributes and retry a failed removal callback.

    Args:
        function: Original removal function supplied by `shutil.rmtree`.
        path: Path that failed to remove.
        exc_info: Exception information supplied by `shutil.rmtree`.

    Returns:
        None.
    """

    _ = exc_info
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    function(path)


def _copy_tree(source: Path, target: Path) -> None:
    """Copy a directory tree after removing the previous target.

    Args:
        source: Source directory.
        target: Target directory.

    Returns:
        None.
    """

    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _sandbox_relative(path: Path, sandbox_dir: Path) -> str:
    """Format a sandbox path without leaking host absolute paths.

    Args:
        path: Path inside the sandbox.
        sandbox_dir: Sandbox root.

    Returns:
        POSIX-style relative path.
    """

    return path.relative_to(sandbox_dir).as_posix()