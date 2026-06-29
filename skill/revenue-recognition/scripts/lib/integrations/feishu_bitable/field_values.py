"""飞书字段值解包工具。

上传、对账、配置读取等场景都可能拿到飞书原始 `fields` 结构。
这里把它们尽量归一成普通标量，避免每个调用点重复猜测字段格式。
"""

from __future__ import annotations

from typing import Any


def extract_feishu_scalar(value: Any) -> Any:
    """把飞书字段值尽量展开成可比较的标量。"""

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
    """把飞书原始 fields 压平成普通字典。"""

    return {field_name: extract_feishu_scalar(field_value) for field_name, field_value in fields.items()}
