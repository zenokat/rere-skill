"""Contract tests for the minimal suite and case-folder manifest."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.cases.manifest_loader import ManifestLoadError, load_suite_manifest


EXAMPLE_SUITE = Path("specs/002-workbuddy-eval-harness/examples/revenue-recognition-real-smoke/suite.yaml")


def test_revenue_real_smoke_manifest_loads_case_folder() -> None:
    """The README example suite should load only the minimal user fields."""

    manifest = load_suite_manifest(EXAMPLE_SUITE)

    assert manifest.suite_id == "revenue-recognition-real-smoke"
    assert manifest.graders == ["preview_file_exists"]
    assert [case.case_id for case in manifest.enabled_cases()] == ["revenue-recognition-dine-in-202605"]
    case = manifest.cases[0]
    assert case.case_dir.name == "revenue-recognition-dine-in-202605"
    assert case.instruction_path.name == "instruction.md"
    assert case.skills_dir.name == "skills"
    assert case.input_dir.name == "input"
    assert "202605" in case.instruction


def test_manifest_rejects_legacy_prompt_and_skill_fields(tmp_path: Path) -> None:
    """Old `skill.*` and inline `cases[].prompt` are no longer user contract."""

    manifest_path = tmp_path / "legacy.yaml"
    manifest_path.write_text(
        """
suite_id: legacy
skill:
  name: revenue-recognition
  path: skill/revenue-recognition
graders:
  - preview_file_exists
cases:
  - case_id: legacy-case
    prompt: hello
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestLoadError):
        load_suite_manifest(manifest_path)


def test_manifest_rejects_path_traversal_case_id(tmp_path: Path) -> None:
    """Case ids must be plain folder names under the suite cases directory."""

    suite = tmp_path / "suite.yaml"
    suite.write_text(
        """
suite_id: unsafe
graders:
  - preview_file_exists
cases:
  - ../escape
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestLoadError):
        load_suite_manifest(suite)
