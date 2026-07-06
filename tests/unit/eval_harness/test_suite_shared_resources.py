"""Tests for suite-level shared input and skills fallback.

The eval-harness supports declaring ``input`` and ``skills`` at the suite level
in ``suite.yaml``.  When a case-level ``input/`` or ``skills/`` directory is
empty, the sandbox builder falls back to the suite-level shared path.

These tests verify two layers:

* **manifest_loader** -- parsing and attaching shared paths to EvalCase.
* **case_sandbox** -- effective directory resolution during sandbox build.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.cases.manifest_loader import ManifestLoadError, load_suite_manifest
from evals.cases.manifest_models import EvalCase
from evals.sandbox.case_sandbox import (
    CaseSandboxBuilder,
    _dir_is_empty,
    _effective_input_dir,
    _effective_skills_dir,
)


# ---------------------------------------------------------------------------
# Helpers -- build a minimal but valid suite directory in tmp_path
# ---------------------------------------------------------------------------


def _build_suite(
    *,
    tmp_path: Path,
    suite_id: str = "test-suite",
    grader: str = "preview_file_exists",
    shared_input: Path | None = None,
    shared_skills: Path | None = None,
    case_ids: list[str] | None = None,
) -> Path:
    """Scaffold a complete, loadable suite directory.

    Args:
        tmp_path: Pytest temporary directory.
        suite_id: Value written to ``suite.yaml``.
        grader: Single grader id.
        shared_input: If provided, written as suite-level ``input`` in YAML.
        shared_skills: If provided, written as suite-level ``skills`` in YAML.
        case_ids: Case folder names to create (each with ``instruction.md``,
            ``input/``, ``skills/``).

    Returns:
        Path to the generated ``suite.yaml``.
    """

    case_ids = case_ids or ["case-a"]
    suite_dir = tmp_path / suite_id
    suite_dir.mkdir()
    cases_dir = suite_dir / "cases"

    for case_id in case_ids:
        case_dir = cases_dir / case_id
        case_dir.mkdir(parents=True)
        (case_dir / "instruction.md").write_text(f"Task for {case_id}", encoding="utf-8")
        (case_dir / "input").mkdir()
        (case_dir / "skills").mkdir()

    # IMPORTANT: do NOT create shared resource directories here.
    # The caller is responsible for creating them (or deliberately leaving
    # them absent for negative-path tests).

    # Write suite.yaml
    lines: list[str] = [f"suite_id: {suite_id}", "graders:", f"  - {grader}", "cases:"]
    for cid in case_ids:
        lines.append(f"  - {cid}")
    if shared_input is not None:
        lines.append(f"input: {shared_input}")
    if shared_skills is not None:
        lines.append(f"skills: {shared_skills}")

    suite_yaml = suite_dir / "suite.yaml"
    suite_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return suite_yaml


def _make_case(
    *,
    tmp_path: Path,
    case_id: str = "case-a",
    has_input_files: bool = False,
    has_skill_subdirs: bool = False,
    suite_shared_input: Path | None = None,
    suite_shared_skills: Path | None = None,
) -> EvalCase:
    """Create an EvalCase with real or empty directories.

    Args:
        tmp_path: Pytest temporary directory.
        case_id: Identifier for the case.
        has_input_files: If True, puts a file in case-level input/.
        has_skill_subdirs: If True, creates a subdirectory in case-level skills/.
        suite_shared_input: Optional suite-level shared input path.
        suite_shared_skills: Optional suite-level shared skills path.

    Returns:
        EvalCase instance ready for sandbox resolution tests.
    """

    case_dir = tmp_path / "cases" / case_id
    case_dir.mkdir(parents=True)
    (case_dir / "instruction.md").write_text("test", encoding="utf-8")

    input_dir = case_dir / "input"
    input_dir.mkdir()
    if has_input_files:
        (input_dir / "data.xlsx").write_text("fake", encoding="utf-8")

    skills_dir = case_dir / "skills"
    skills_dir.mkdir()
    if has_skill_subdirs:
        (skills_dir / "my-skill").mkdir()

    return EvalCase(
        case_id=case_id,
        case_dir=case_dir,
        instruction_path=case_dir / "instruction.md",
        skills_dir=skills_dir,
        input_dir=input_dir,
        instruction="test",
        suite_shared_input=suite_shared_input,
        suite_shared_skills=suite_shared_skills,
    )


# ---------------------------------------------------------------------------
# manifest_loader tests
# ---------------------------------------------------------------------------


class TestSuiteSharedResourcesManifest:
    """Suite-level ``input`` and ``skills`` are parsed and attached to cases."""

    def test_shared_input_and_skills_parsed(self, tmp_path: Path) -> None:
        """Both shared fields appear on every loaded case."""

        shared_input = tmp_path / "shared-input"
        shared_input.mkdir()
        shared_skills = tmp_path / "shared-skills"
        shared_skills.mkdir()
        suite_yaml = _build_suite(
            tmp_path=tmp_path,
            shared_input=shared_input,
            shared_skills=shared_skills,
        )

        manifest = load_suite_manifest(suite_yaml)

        assert manifest.suite_shared_input == shared_input.resolve()
        assert manifest.suite_shared_skills == shared_skills.resolve()
        for case in manifest.cases:
            assert case.suite_shared_input == shared_input.resolve()
            assert case.suite_shared_skills == shared_skills.resolve()

    def test_shared_input_only(self, tmp_path: Path) -> None:
        """Declaring only ``input`` leaves ``skills`` as None."""

        shared_input = tmp_path / "shared-input"
        shared_input.mkdir()
        suite_yaml = _build_suite(tmp_path=tmp_path, shared_input=shared_input)

        manifest = load_suite_manifest(suite_yaml)

        assert manifest.suite_shared_input is not None
        assert manifest.suite_shared_skills is None

    def test_no_shared_resources(self, tmp_path: Path) -> None:
        """A suite without ``input`` or ``skills`` fields still loads."""

        suite_yaml = _build_suite(tmp_path=tmp_path)
        manifest = load_suite_manifest(suite_yaml)

        assert manifest.suite_shared_input is None
        assert manifest.suite_shared_skills is None

    def test_nonexistent_shared_input_rejected(self, tmp_path: Path) -> None:
        """A shared input path that does not exist triggers ManifestLoadError."""

        # Deliberately pass a path without creating the directory.
        nonexistent = tmp_path / "does-not-exist"
        suite_yaml = _build_suite(
            tmp_path=tmp_path,
            shared_input=nonexistent,
        )

        with pytest.raises(ManifestLoadError, match="suite input path does not exist"):
            load_suite_manifest(suite_yaml)

    def test_nonexistent_shared_skills_rejected(self, tmp_path: Path) -> None:
        """A shared skills path that does not exist triggers ManifestLoadError."""

        nonexistent = tmp_path / "does-not-exist"
        suite_yaml = _build_suite(
            tmp_path=tmp_path,
            shared_skills=nonexistent,
        )

        with pytest.raises(ManifestLoadError, match="suite skills path does not exist"):
            load_suite_manifest(suite_yaml)

    def test_relative_shared_path_resolved_against_suite_dir(self, tmp_path: Path) -> None:
        """A relative shared path is resolved relative to the suite directory."""

        # _build_suite puts suite at tmp_path/test-suite/suite.yaml.
        # "../shared-input" from the suite dir resolves to tmp_path/shared-input.
        shared_input = tmp_path / "shared-input"
        shared_input.mkdir()
        suite_yaml = _build_suite(
            tmp_path=tmp_path,
            shared_input=shared_input,
        )
        # Rewrite YAML with a relative path
        content = suite_yaml.read_text(encoding="utf-8")
        content = content.replace(f"input: {shared_input}", "input: ../shared-input")
        suite_yaml.write_text(content, encoding="utf-8")

        manifest = load_suite_manifest(suite_yaml)

        assert manifest.suite_shared_input == shared_input.resolve()


# ---------------------------------------------------------------------------
# case_sandbox helper tests
# ---------------------------------------------------------------------------


class TestDirIsEmpty:
    """_dir_is_empty returns True only for directories with no child dirs."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """A directory with no children is considered empty."""

        empty = tmp_path / "empty"
        empty.mkdir()

        assert _dir_is_empty(empty) is True

    def test_directory_with_files_only(self, tmp_path: Path) -> None:
        """Files (not subdirectories) do not count as content."""

        d = tmp_path / "with-files"
        d.mkdir()
        (d / "readme.txt").write_text("hello", encoding="utf-8")

        # _dir_is_empty checks for child directories, not files.
        assert _dir_is_empty(d) is True

    def test_directory_with_subdirectories(self, tmp_path: Path) -> None:
        """A child directory means the directory is not empty."""

        d = tmp_path / "with-subdirs"
        d.mkdir()
        (d / "child").mkdir()

        assert _dir_is_empty(d) is False

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """A missing directory returns False (not empty, not usable)."""

        assert _dir_is_empty(tmp_path / "nope") is False


class TestEffectiveInputDir:
    """_effective_input_dir falls back to suite-level when case-level has no subdirectories.

    Note: ``_dir_is_empty`` only checks for child *directories*, not files.
    This matches the runtime convention where input subdirectories represent
    structured data sources (e.g. per-period Excel folders).
    """

    def test_uses_case_input_when_has_subdirectory(self, tmp_path: Path) -> None:
        """Case-level input with a subdirectory takes priority over suite-level."""

        shared_input = tmp_path / "shared-input"
        shared_input.mkdir()
        case = _make_case(tmp_path=tmp_path, has_input_files=False, suite_shared_input=shared_input)
        # Create a subdirectory inside case-level input so _dir_is_empty returns False.
        (case.input_dir / "202605").mkdir()

        assert _effective_input_dir(case) == case.input_dir

    def test_falls_back_to_shared_when_no_subdirectories(self, tmp_path: Path) -> None:
        """Case-level input with no subdirectories falls back to suite-level shared path."""

        shared_input = tmp_path / "shared-input"
        shared_input.mkdir()
        case = _make_case(tmp_path=tmp_path, has_input_files=False, suite_shared_input=shared_input)

        assert _effective_input_dir(case) == shared_input

    def test_uses_case_input_when_no_shared_available(self, tmp_path: Path) -> None:
        """Case-level input is used when no suite-level shared path exists."""

        case = _make_case(tmp_path=tmp_path, has_input_files=False)

        assert _effective_input_dir(case) == case.input_dir


class TestEffectiveSkillsDir:
    """_effective_skills_dir falls back to suite-level when case-level is empty."""

    def test_uses_case_skills_when_populated(self, tmp_path: Path) -> None:
        """Case-level skills with a subdirectory take priority."""

        shared_skills = tmp_path / "shared-skills"
        shared_skills.mkdir()
        case = _make_case(tmp_path=tmp_path, has_skill_subdirs=True, suite_shared_skills=shared_skills)

        assert _effective_skills_dir(case) == case.skills_dir

    def test_falls_back_to_shared_when_case_empty(self, tmp_path: Path) -> None:
        """Empty case-level skills fall back to suite-level shared path."""

        shared_skills = tmp_path / "shared-skills"
        shared_skills.mkdir()
        case = _make_case(tmp_path=tmp_path, has_skill_subdirs=False, suite_shared_skills=shared_skills)

        assert _effective_skills_dir(case) == shared_skills

    def test_uses_case_skills_when_no_shared_available(self, tmp_path: Path) -> None:
        """Case-level skills are used when no suite-level shared path exists."""

        case = _make_case(tmp_path=tmp_path, has_skill_subdirs=False)

        assert _effective_skills_dir(case) == case.skills_dir


# ---------------------------------------------------------------------------
# Integration: sandbox build with shared resources
# ---------------------------------------------------------------------------


class TestSandboxBuildWithSharedResources:
    """CaseSandboxBuilder copies shared resources into the sandbox."""

    def test_shared_input_copied_into_sandbox(self, tmp_path: Path) -> None:
        """When case-level input has no subdirectories, suite-level shared files appear in sandbox input/."""

        shared_input = tmp_path / "shared-input"
        shared_input.mkdir()
        (shared_input / "source.xlsx").write_text("data", encoding="utf-8")

        case = _make_case(tmp_path=tmp_path, has_input_files=False, suite_shared_input=shared_input)
        sandbox_dir = tmp_path / "sandbox"

        CaseSandboxBuilder().create(case=case, sandbox_dir=sandbox_dir)

        sandbox_input = sandbox_dir / "input"
        assert (sandbox_input / "source.xlsx").exists()

    def test_shared_skills_copied_into_sandbox(self, tmp_path: Path) -> None:
        """When case-level skills has no subdirectories, suite-level shared skills appear in sandbox."""

        shared_skills = tmp_path / "shared-skills"
        shared_skills.mkdir()
        skill_dir = shared_skills / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# My Skill", encoding="utf-8")

        case = _make_case(tmp_path=tmp_path, has_skill_subdirs=False, suite_shared_skills=shared_skills)
        sandbox_dir = tmp_path / "sandbox"

        CaseSandboxBuilder().create(case=case, sandbox_dir=sandbox_dir)

        sandbox_skill = sandbox_dir / ".workbuddy" / "skills" / "my-skill"
        assert sandbox_skill.is_dir()
        assert (sandbox_skill / "SKILL.md").exists()
