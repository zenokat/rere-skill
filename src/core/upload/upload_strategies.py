"""上传冲突处理策略。"""

from __future__ import annotations

from typing import Any


def build_upsert_key(record_fields: dict[str, Any], group_fields: list[str], period_field: str = "期间") -> tuple[Any, ...]:
    """构造 upsert 用的联合业务键。"""

    return tuple(_normalize_key_value(record_fields.get(field_name)) for field_name in [period_field, *group_fields])


def records_differ(
    preview_record: dict[str, Any],
    existing_record: dict[str, Any],
) -> bool:
    """判断 preview 记录与远端现有记录是否存在真实差异。"""

    all_fields = set(preview_record) | set(existing_record)
    for field_name in all_fields:
        if _normalize_compare_value(preview_record.get(field_name)) != _normalize_compare_value(existing_record.get(field_name)):
            return True
    return False


def _normalize_compare_value(value: Any) -> Any:
    """把上传前后的字段值归一成稳定可比较的形式。"""

    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric.is_integer():
            return int(numeric)
        return round(numeric, 2)
    return value


def _normalize_key_value(value: Any) -> Any:
    """把联合键中的字段值归一成稳定可匹配形式。"""

    normalized = _normalize_compare_value(value)
    if normalized is None:
        return None
    if isinstance(normalized, (int, float)):
        numeric = float(normalized)
        if numeric.is_integer():
            return str(int(numeric))
        return str(numeric)
    if isinstance(normalized, str):
        return normalized
    return str(normalized)
