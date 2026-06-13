"""开发阶段用于读取飞书镜像表 baseline 的辅助工具。"""

from __future__ import annotations

from typing import Any

from integrations.feishu_bitable.client import BitableApiClient

PERIOD_FIELD_NAME = "期间"
TEXTUAL_FIELD_TYPES = {1}
NUMERIC_FIELD_TYPES = {2}


def extract_feishu_scalar(value: Any) -> Any:
    """把飞书记录字段值尽量展开成可比较的标量。"""

    if isinstance(value, list):
        if not value:
            return None
        if len(value) == 1:
            return extract_feishu_scalar(value[0])
        return [extract_feishu_scalar(item) for item in value]
    if isinstance(value, dict):
        if "text" in value:
            return value["text"]
        if "type" in value and "value" in value:
            inner = value["value"]
            if isinstance(inner, list) and len(inner) == 1:
                return extract_feishu_scalar(inner[0])
            return extract_feishu_scalar(inner)
        if "value" in value:
            inner = value["value"]
            if isinstance(inner, list) and len(inner) == 1:
                return extract_feishu_scalar(inner[0])
            return extract_feishu_scalar(inner)
        return {key: extract_feishu_scalar(inner_value) for key, inner_value in value.items()}
    return value


def flatten_feishu_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """把飞书记录 fields 结构压平成普通字典。"""

    return {field_name: extract_feishu_scalar(field_value) for field_name, field_value in fields.items()}


def fetch_period_baseline_records(
    client: BitableApiClient,
    *,
    app_token: str,
    table_id: str,
    period: int | str,
    field_names: list[str],
) -> list[dict[str, Any]]:
    """按期间从飞书镜像表读取 baseline 记录。

    这里显式读取一次字段元数据来判断 `期间` 是文本列还是数值列，
    避免把看起来像 `202604` 的期间值用错误类型传给飞书筛选条件，
    进而查询出“0 条假空结果”。
    """

    normalized_field_names = _ensure_period_field(field_names)
    period_field_type = _lookup_period_field_type(client=client, app_token=app_token, table_id=table_id)
    normalized_period = _normalize_period_token(period)
    filter_value = _build_period_filter_value(normalized_period, period_field_type)

    records = client.search_records(
        app_token=app_token,
        table_id=table_id,
        field_names=normalized_field_names,
        filter_info={
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": PERIOD_FIELD_NAME,
                    "operator": "is",
                    "value": [filter_value],
                }
            ],
        },
    )
    return [flatten_feishu_fields(record.get("fields", {})) for record in records]


def _lookup_period_field_type(
    client: BitableApiClient,
    *,
    app_token: str,
    table_id: str,
) -> int | None:
    """读取 `期间` 字段类型，用来决定筛选值该传文本还是数值。"""

    field_items = client.list_fields(app_token=app_token, table_id=table_id)
    for field_item in field_items:
        if field_item.get("field_name") == PERIOD_FIELD_NAME:
            field_type = field_item.get("type")
            return field_type if isinstance(field_type, int) else None
    return None


def _normalize_period_token(period: int | str) -> str:
    """把输入期间规范成 `YYYYMM` 形式的字符串。"""

    normalized = str(period).strip()
    if len(normalized) != 6 or not normalized.isdigit():
        raise ValueError("The baseline period must be a 6-digit YYYYMM token.")
    return normalized


def _build_period_filter_value(period_token: str, field_type: int | None) -> int | str:
    """根据飞书字段类型构造正确的筛选值类型。"""

    if field_type in NUMERIC_FIELD_TYPES:
        return int(period_token)
    if field_type in TEXTUAL_FIELD_TYPES:
        return period_token
    return period_token


def _ensure_period_field(field_names: list[str]) -> list[str]:
    """确保读取字段中包含 `期间`，避免后续对账缺少联合键。"""

    ordered = list(field_names)
    if PERIOD_FIELD_NAME not in ordered:
        ordered.insert(0, PERIOD_FIELD_NAME)
    return ordered
