"""Unit tests for the preview-vs-baseline eval grader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from evals.graders.preview_matches_baseline import grade_preview_matches_baseline


class FakeBaselineSource:
    """In-memory baseline source for grader tests.

    Args:
        baseline_records: Records returned by ``fetch_period_records``.

    Returns:
        FakeBaselineSource instance.
    """

    def __init__(self, baseline_records: list[dict[str, Any]]) -> None:
        """Store test baseline records.

        Args:
            baseline_records: Records returned to the grader.

        Returns:
            None.
        """

        self.baseline_records = baseline_records
        self.requested_table_id: str | None = None
        self.requested_period: str | None = None
        self.requested_field_names: list[str] | None = None

    def table_id_for_recog_id(self, recog_id: str) -> str | None:
        """Return a stable fake result table id.

        Args:
            recog_id: Recognition project id.

        Returns:
            Fake table id when the project id is non-empty.
        """

        return "tbl_fake" if recog_id else None

    def fetch_period_records(
        self,
        *,
        table_id: str,
        period: str,
        field_names: list[str],
    ) -> list[dict[str, Any]]:
        """Return configured baseline records and record the request.

        Args:
            table_id: Requested result table id.
            period: Requested accounting period.
            field_names: Requested Feishu fields.

        Returns:
            Configured baseline records.
        """

        self.requested_table_id = table_id
        self.requested_period = period
        self.requested_field_names = field_names
        return self.baseline_records


def test_preview_matches_baseline_passes_when_excel_rows_match(tmp_path: Path) -> None:
    """The grader should pass when preview rows equal the shadow baseline."""

    outputs_dir = tmp_path / "outputs"
    preview_file = outputs_dir / "202605_dine_in_revenue_preview.xlsx"
    _write_preview_file(
        preview_file,
        recog_id="dine_in_revenue",
        period="202605",
        group_fields=["全来店ID"],
        rows=[
            {"期间": "202605", "全来店ID": "1001", "流水金额": 100.0},
        ],
    )
    baseline_source = FakeBaselineSource(
        baseline_records=[
            {"期间": 202605, "全来店ID": "1001", "流水金额": "100.00"},
        ]
    )

    result = grade_preview_matches_baseline(outputs_dir=outputs_dir, baseline_source=baseline_source)

    assert result["score"] == 1
    assert result["evidence"]["recog_id"] == "dine_in_revenue"
    assert result["evidence"]["period"] == "202605"
    assert result["evidence"]["preview_count"] == 1
    assert result["evidence"]["baseline_count"] == 1
    assert result["evidence"]["difference_count"] == 0
    assert baseline_source.requested_field_names == ["期间", "全来店ID", "流水金额"]


def test_preview_matches_baseline_reports_value_mismatch(tmp_path: Path) -> None:
    """The grader should fail with compact evidence when a value differs."""

    outputs_dir = tmp_path / "outputs"
    preview_file = outputs_dir / "202605_dine_in_revenue_preview.xlsx"
    _write_preview_file(
        preview_file,
        recog_id="dine_in_revenue",
        period="202605",
        group_fields=["全来店ID"],
        rows=[
            {"期间": "202605", "全来店ID": "1001", "流水金额": 100.0},
        ],
    )
    baseline_source = FakeBaselineSource(
        baseline_records=[
            {"期间": 202605, "全来店ID": "1001", "流水金额": 101.0},
        ]
    )

    result = grade_preview_matches_baseline(outputs_dir=outputs_dir, baseline_source=baseline_source)

    assert result["score"] == 0
    assert result["evidence"]["diff_type"] == "value_mismatch"
    assert result["evidence"]["difference_count"] == 1
    assert result["evidence"]["sample_differences"][0]["key"] == ["202605", "1001"]
    assert result["evidence"]["sample_differences"][0]["differences"][0] == {
        "field": "流水金额",
        "preview_value": 100.0,
        "baseline_value": 101.0,
    }


def test_preview_matches_baseline_fails_without_preview_artifact(tmp_path: Path) -> None:
    """A missing preview file should be a clean grader failure."""

    result = grade_preview_matches_baseline(outputs_dir=tmp_path / "outputs", baseline_source=FakeBaselineSource([]))

    assert result["score"] == 0
    assert result["evidence"] == {"checked_dir": "outputs/"}


def _write_preview_file(
    path: Path,
    *,
    recog_id: str,
    period: str,
    group_fields: list[str],
    rows: list[dict[str, Any]],
) -> None:
    """Create a minimal real preview Excel artifact for grader tests.

    Args:
        path: Destination file path.
        recog_id: Preview metadata recognition project id.
        period: Preview metadata accounting period.
        group_fields: Preview metadata business key fields.
        rows: Result-sheet records.

    Returns:
        None.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0].keys()) if rows else ["期间", *group_fields]
    workbook = Workbook()
    results_sheet = workbook.active
    results_sheet.title = "results"
    results_sheet.append(headers)
    for row in rows:
        results_sheet.append([row.get(header) for header in headers])

    metadata_sheet = workbook.create_sheet("__meta__")
    metadata_sheet.sheet_state = "hidden"
    metadata_sheet.append(["key", "value"])
    metadata_sheet.append(["recog_id", recog_id])
    metadata_sheet.append(["period", period])
    metadata_sheet.append(["group_fields", json.dumps(group_fields, ensure_ascii=False)])
    workbook.save(path)
    workbook.close()
