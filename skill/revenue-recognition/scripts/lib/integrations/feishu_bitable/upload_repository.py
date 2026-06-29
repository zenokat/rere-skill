"""飞书镜像表上传仓库。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from integrations.feishu_bitable.client import BitableApiClient
from integrations.feishu_bitable.field_values import flatten_feishu_fields


@dataclass
class _FieldMetadataCache:
    """缓存单次仓库实例内的目标表字段元数据。"""

    field_items_by_table: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    period_field_type_by_table: dict[str, int | None] = field(default_factory=dict)
    field_types_by_table: dict[str, dict[str, int]] = field(default_factory=dict)


class FeishuUploadRepository:
    """封装目标表记录读取、创建与更新。"""

    def __init__(self, client: BitableApiClient, result_bitable_app_token: str) -> None:
        """初始化仓库。"""

        self._client = client
        self._result_bitable_app_token = result_bitable_app_token
        self._field_metadata_cache = _FieldMetadataCache()

    def list_records(self, table_id: str) -> list[dict[str, Any]]:
        """列出目标表记录。"""

        raw_records = self._client.list_records(self._result_bitable_app_token, table_id)
        return [self._normalize_record(record) for record in raw_records]

    def search_period_records(self, table_id: str, *, period: int | str) -> list[dict[str, Any]]:
        """按期间查询目标表记录。"""

        period_field_type = self._lookup_period_field_type(table_id)
        filter_value = self._build_period_filter_value(period=period, field_type=period_field_type)
        raw_records = self._client.search_records(
            self._result_bitable_app_token,
            table_id,
            filter_info={
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": "期间",
                        "operator": "is",
                        "value": [filter_value],
                    }
                ],
            },
        )
        return [self._normalize_record(record) for record in raw_records]

    def create_records(self, table_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        """批量创建记录。"""

        if not records:
            return {"records": []}
        payload = [{"fields": record} for record in self._normalize_outbound_records(table_id, records)]
        return self._client.batch_create_records(self._result_bitable_app_token, table_id, payload)

    def update_records(self, table_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        """批量更新记录。"""

        if not records:
            return {"records": []}
        normalized_records = [
            {
                **record,
                "fields": self._normalize_outbound_record(table_id, record.get("fields", {})),
            }
            for record in records
        ]
        return self._client.batch_update_records(self._result_bitable_app_token, table_id, normalized_records)

    def _lookup_period_field_type(self, table_id: str) -> int | None:
        """读取目标表 `期间` 字段类型。"""

        cached = self._field_metadata_cache.period_field_type_by_table.get(table_id)
        if table_id in self._field_metadata_cache.period_field_type_by_table:
            return cached
        field_items = self._list_field_items(table_id)
        for field_item in field_items:
            if field_item.get("field_name") == "期间":
                field_type = field_item.get("type")
                resolved = field_type if isinstance(field_type, int) else None
                self._field_metadata_cache.period_field_type_by_table[table_id] = resolved
                return resolved
        self._field_metadata_cache.period_field_type_by_table[table_id] = None
        return None

    def _lookup_field_types(self, table_id: str) -> dict[str, int]:
        """读取目标表字段类型映射。"""

        cached = self._field_metadata_cache.field_types_by_table.get(table_id)
        if cached is not None:
            return cached
        field_items = self._list_field_items(table_id)
        field_types = {
            str(field_item.get("field_name")): int(field_item.get("type"))
            for field_item in field_items
            if field_item.get("field_name") is not None and isinstance(field_item.get("type"), int)
        }
        self._field_metadata_cache.field_types_by_table[table_id] = field_types
        return field_types

    def _list_field_items(self, table_id: str) -> list[dict[str, Any]]:
        """读取并缓存整张表的字段元数据。"""

        cached = self._field_metadata_cache.field_items_by_table.get(table_id)
        if cached is not None:
            return cached
        field_items = self._client.list_fields(self._result_bitable_app_token, table_id)
        self._field_metadata_cache.field_items_by_table[table_id] = field_items
        return field_items

    @staticmethod
    def _build_period_filter_value(*, period: int | str, field_type: int | None) -> int | str:
        """根据字段类型构造 `期间` 查询值。"""

        normalized = str(period).strip()
        if field_type == 2 and normalized.isdigit():
            return int(normalized)
        return normalized

    @staticmethod
    def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
        """把飞书原始记录归一成上传阶段易用结构。"""

        return {
            **record,
            "fields": flatten_feishu_fields(record.get("fields", {})),
        }

    def _normalize_outbound_records(self, table_id: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按目标表字段类型规范化待上传记录。"""

        return [self._normalize_outbound_record(table_id, record) for record in records]

    def _normalize_outbound_record(self, table_id: str, record: dict[str, Any]) -> dict[str, Any]:
        """按目标表字段类型规范化单条待上传记录。"""

        field_types = self._lookup_field_types(table_id)
        normalized_record: dict[str, Any] = {}
        for field_name, value in record.items():
            normalized_record[field_name] = self._normalize_outbound_value(
                value=value,
                field_type=field_types.get(field_name),
            )
        return normalized_record

    @staticmethod
    def _normalize_outbound_value(value: Any, field_type: int | None) -> Any:
        """将本地记录值转换为飞书目标字段期望的基础类型。"""

        if value is None:
            return None
        if field_type == 2:
            if isinstance(value, str):
                stripped = value.strip()
                if stripped == "":
                    return None
                numeric = float(stripped)
            elif isinstance(value, (int, float)):
                numeric = float(value)
            else:
                return value
            if numeric.is_integer():
                return int(numeric)
            return numeric
        return value
