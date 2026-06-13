"""baseline 对比辅助单元测试。"""

from __future__ import annotations

from tests.helpers.baseline_diff import compare_preview_to_baseline


def test_compare_preview_to_baseline_normalizes_string_and_numeric_keys() -> None:
    """联合键中的字符串/整数形式应被视为同一业务键。"""

    preview_records = [
        {
            "期间": "202605",
            "全来店ID": "1001",
            "流水金额": 100.0,
        }
    ]
    baseline_records = [
        {
            "期间": 202605,
            "全来店ID": "1001",
            "流水金额": 100,
        }
    ]

    report = compare_preview_to_baseline(
        preview_records=preview_records,
        baseline_records=baseline_records,
        key_fields=["期间", "全来店ID"],
    )

    assert report.matched is True
    assert report.differences == []


def test_compare_preview_to_baseline_reports_real_missing_record_only() -> None:
    """真实缺失记录应被保留下来，而不是被辅助逻辑吞掉。"""

    preview_records = [
        {"期间": "202605", "全来店ID": "1001", "流水金额": 100.0},
    ]
    baseline_records = [
        {"期间": 202605, "全来店ID": "1001", "流水金额": 100},
        {"期间": 202605, "全来店ID": "MD00105", "流水金额": 200},
    ]

    report = compare_preview_to_baseline(
        preview_records=preview_records,
        baseline_records=baseline_records,
        key_fields=["期间", "全来店ID"],
    )

    assert report.matched is False
    assert len(report.differences) == 1
    assert report.differences[0].issue_type == "missing_in_preview"
    assert report.differences[0].key == ("202605", "MD00105")


def test_compare_preview_to_baseline_treats_numeric_strings_as_equal_values() -> None:
    """baseline 中的数字字符串不应被误报成金额差异。"""

    preview_records = [
        {
            "期间": "202605",
            "全来店名称": "蔡林记中南店",
            "收款合计": 8651.93,
            "微信": 8300.0,
            "退现金卡值": -148.07,
        }
    ]
    baseline_records = [
        {
            "期间": "202605",
            "全来店名称": "蔡林记中南店",
            "收款合计": "8651.93",
            "微信": "8300",
            "退现金卡值": "-148.07",
        }
    ]

    report = compare_preview_to_baseline(
        preview_records=preview_records,
        baseline_records=baseline_records,
        key_fields=["期间", "全来店名称"],
    )

    assert report.matched is True
    assert report.differences == []
