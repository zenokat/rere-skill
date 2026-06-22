"""preview 与 baseline 一致性的最小集成测试。"""

from __future__ import annotations

from helpers.baseline_diff import compare_preview_to_baseline


def test_preview_baseline_wave1_matches_after_normalization() -> None:
    """首波回归至少应能稳定证明基础对账流程成立。"""

    preview_records = [
        {
            "期间": "202605",
            "平台ID": "163007972",
            "平台门店名称": "蔡林记(积玉桥店)",
            "商品金额": 25455.5,
        }
    ]
    baseline_records = [
        {
            "期间": 202605,
            "平台ID": 163007972,
            "平台门店名称": "蔡林记（积玉桥店）",
            "商品金额": "25455.50",
        }
    ]

    report = compare_preview_to_baseline(
        preview_records=preview_records,
        baseline_records=baseline_records,
        key_fields=["期间", "平台ID", "平台门店名称"],
    )

    assert report.matched is True
    assert report.preview_count == 1
    assert report.baseline_count == 1
    assert report.next_action == "proceed"
