"""preview 与 baseline 的差异对比工具。

该模块仅服务于 Ralph 内层循环中的开发期对账，不属于工具本体。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from helpers.normalizers import normalize_record


@dataclass
class DifferenceDetail:
    """单个字段差异。"""

    field: str
    preview_value: Any
    baseline_value: Any


@dataclass
class DifferenceEntry:
    """单条记录的差异。"""

    key: tuple[Any, ...]
    issue_type: str
    differences: list[DifferenceDetail]


@dataclass
class BaselineDiffReport:
    """一次 preview/baseline 对比的完整结果。"""

    matched: bool
    preview_count: int
    baseline_count: int
    key_fields: list[str]
    differences: list[DifferenceEntry]
    requires_business_confirmation: bool
    next_action: str


def compare_preview_to_baseline(
    preview_records: list[dict[str, Any]],
    baseline_records: list[dict[str, Any]],
    key_fields: list[str],
    ignore_fields: list[str] | None = None,
    numeric_digits: int = 2,
) -> BaselineDiffReport:
    """按联合业务键对比 preview 与 baseline。"""

    ignored = set(ignore_fields or [])
    preview_map = _index_records(records=preview_records, key_fields=key_fields, numeric_digits=numeric_digits)
    baseline_map = _index_records(records=baseline_records, key_fields=key_fields, numeric_digits=numeric_digits)

    differences: list[DifferenceEntry] = []
    all_keys = sorted(set(preview_map) | set(baseline_map), key=str)

    for key in all_keys:
        preview_record = preview_map.get(key)
        baseline_record = baseline_map.get(key)
        if preview_record is None:
            differences.append(
                DifferenceEntry(
                    key=key,
                    issue_type="missing_in_preview",
                    differences=[
                        DifferenceDetail(field="__record__", preview_value=None, baseline_value=baseline_record),
                    ],
                )
            )
            continue
        if baseline_record is None:
            differences.append(
                DifferenceEntry(
                    key=key,
                    issue_type="missing_in_baseline",
                    differences=[
                        DifferenceDetail(field="__record__", preview_value=preview_record, baseline_value=None),
                    ],
                )
            )
            continue

        field_differences: list[DifferenceDetail] = []
        all_fields = sorted((set(preview_record) | set(baseline_record)) - ignored)
        for field_name in all_fields:
            if field_name in key_fields:
                continue
            preview_value = preview_record.get(field_name)
            baseline_value = baseline_record.get(field_name)
            if preview_value != baseline_value:
                field_differences.append(
                    DifferenceDetail(
                        field=field_name,
                        preview_value=preview_value,
                        baseline_value=baseline_value,
                    )
                )
        if field_differences:
            differences.append(
                DifferenceEntry(
                    key=key,
                    issue_type="value_mismatch",
                    differences=field_differences,
                )
            )

    matched = not differences
    return BaselineDiffReport(
        matched=matched,
        preview_count=len(preview_records),
        baseline_count=len(baseline_records),
        key_fields=key_fields,
        differences=differences,
        requires_business_confirmation=not matched,
        next_action="proceed" if matched else "report_to_business_owner",
    )


def summarize_diff_type(report: BaselineDiffReport) -> str:
    """把差异结果归纳成 coverage matrix 可写入的摘要分类。"""

    if report.matched:
        return "matched"
    issue_types = {difference.issue_type for difference in report.differences}
    if issue_types == {"value_mismatch"}:
        return "value_mismatch"
    if issue_types == {"missing_in_preview"}:
        return "missing_in_preview"
    if issue_types == {"missing_in_baseline"}:
        return "missing_in_baseline"
    return "mixed"


def build_business_confirmation_message(
    report: BaselineDiffReport,
    recog_id: str,
    period: str,
) -> str:
    """构造需要汇报给业务负责人的简短差异摘要。"""

    diff_type = summarize_diff_type(report)
    return (
        f"Preview 与 baseline 存在差异，recog_id={recog_id}，period={period}，"
        f"diff_type={diff_type}，difference_count={len(report.differences)}。"
        "请先向业务负责人汇报差异和判断建议，确认口径后再继续迭代。"
    )


def _index_records(
    records: list[dict[str, Any]],
    key_fields: list[str],
    numeric_digits: int,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    """把记录按联合键索引。"""

    indexed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for record in records:
        normalized = normalize_record(record, digits=numeric_digits)
        key = tuple(_normalize_key_value(normalized.get(field_name)) for field_name in key_fields)
        indexed[key] = normalized
    return indexed


def _normalize_key_value(value: Any) -> Any:
    """把联合键中的值归一成稳定可比较的形式。"""

    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        numeric_value = float(value)
        if numeric_value.is_integer():
            return str(int(numeric_value))
        return str(numeric_value)
    return str(value)
