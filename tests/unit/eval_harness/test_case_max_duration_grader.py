"""Unit tests for the case_max_duration eval grader."""

from __future__ import annotations

import json
from pathlib import Path

from evals.graders.case_max_duration import grade_case_max_duration


def _write_result(tmp_path: Path, *, duration_ms: int | None = None) -> Path:
    """Write a synthetic result.json with a given duration_ms.

    Args:
        tmp_path: Temporary directory for the file.
        duration_ms: Duration value to embed. When None, omits the field
            entirely to test the missing-field path.

    Returns:
        Path to the written result.json.
    """

    result_file = tmp_path / "result.json"
    metrics: dict = {}
    if duration_ms is not None:
        metrics["duration_ms"] = duration_ms
    data = {
        "case_id": "test_case",
        "verdict": "pass",
        "metrics": metrics,
    }
    result_file.write_text(json.dumps(data), encoding="utf-8")
    return result_file


def test_passes_when_within_budget(tmp_path: Path) -> None:
    """Score 1 when duration is under the threshold."""

    result_file = _write_result(tmp_path, duration_ms=300_000)
    result = grade_case_max_duration(result_json=result_file, max_seconds=600)

    assert result["score"] == 1
    assert result["id"] == "case_max_duration:600"
    assert "通过" in result["summary"]
    assert result["evidence"]["duration_s"] == 300.0
    assert result["evidence"]["margin_s"] == 300.0


def test_fails_when_over_budget(tmp_path: Path) -> None:
    """Score 0 when duration exceeds the threshold."""

    result_file = _write_result(tmp_path, duration_ms=700_000)
    result = grade_case_max_duration(result_json=result_file, max_seconds=600)

    assert result["score"] == 0
    assert "超出阈值" in result["summary"]
    assert result["evidence"]["duration_s"] == 700.0
    assert result["evidence"]["margin_s"] == -100.0


def test_passes_when_exactly_at_budget(tmp_path: Path) -> None:
    """Score 1 when duration equals the threshold (boundary is inclusive)."""

    result_file = _write_result(tmp_path, duration_ms=600_000)
    result = grade_case_max_duration(result_json=result_file, max_seconds=600)

    assert result["score"] == 1
    assert "通过" in result["summary"]


def test_fails_when_result_json_missing(tmp_path: Path) -> None:
    """Score 0 when result.json does not exist."""

    missing = tmp_path / "nonexistent" / "result.json"
    result = grade_case_max_duration(result_json=missing, max_seconds=600)

    assert result["score"] == 0
    assert "result_json_not_found" in result["evidence"]["error"]


def test_fails_when_duration_ms_missing(tmp_path: Path) -> None:
    """Score 0 when result.json has no metrics.duration_ms field."""

    result_file = _write_result(tmp_path, duration_ms=None)
    result = grade_case_max_duration(result_json=result_file, max_seconds=600)

    assert result["score"] == 0
    assert "duration_ms_missing" in result["evidence"]["error"]


def test_evidence_contains_expected_fields(tmp_path: Path) -> None:
    """Evidence must include all diagnostic fields for debugging."""

    result_file = _write_result(tmp_path, duration_ms=450_000)
    result = grade_case_max_duration(result_json=result_file, max_seconds=900)

    evidence = result["evidence"]
    assert evidence["duration_ms"] == 450_000
    assert evidence["duration_s"] == 450.0
    assert evidence["max_seconds"] == 900
    assert evidence["margin_s"] == 450.0
