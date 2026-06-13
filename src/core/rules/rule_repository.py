"""源文件结构与汇总规则仓库。"""

from __future__ import annotations

from typing import Any

from integrations.feishu_bitable.client import BitableApiClient
from models.domain import RollupRule, RuleBundle, SourceSheetSpec
from utils.settings import AppSettings


def _extract_feishu_text(value: Any) -> str | None:
    """从飞书字段值中提取文本。"""

    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        for item in value:
            extracted = _extract_feishu_text(item)
            if extracted:
                return extracted
        return None
    if isinstance(value, dict):
        for key in ("text", "name", "value"):
            if key in value:
                extracted = _extract_feishu_text(value[key])
                if extracted:
                    return extracted
    return str(value)


def _extract_feishu_bool(value: Any) -> bool:
    """从飞书字段值中提取布尔值。"""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return False


class FeishuRuleRepository:
    """从飞书配置库读取源结构与规则配置。"""

    def __init__(self, client: BitableApiClient, settings: AppSettings) -> None:
        """初始化仓库。"""

        self._client = client
        self._settings = settings

    def load_rule_bundle(self, recog_id: str) -> RuleBundle:
        """按项目读取源结构与规则集合。"""

        source_records = self._client.list_records(
            app_token=self._settings.config_bitable_app_token,
            table_id=self._settings.source_spec_table_id,
        )
        rule_records = self._client.list_records(
            app_token=self._settings.config_bitable_app_token,
            table_id=self._settings.rollup_rule_table_id,
        )

        source_sheets = [
            SourceSheetSpec(
                recog_id=recog_id,
                sheet=_extract_feishu_text(fields.get("sheet")) or "",
                category_row=_parse_optional_int(_extract_feishu_text(fields.get("category_row"))),
                field_row=int(_extract_feishu_text(fields.get("field_row")) or 0),
                last_row=int(_extract_feishu_text(fields.get("last_row")) or 0),
                optional=_extract_feishu_bool(fields.get("optional")),
            )
            for record in source_records
            for fields in [record.get("fields", {})]
            if (_extract_feishu_text(fields.get("recog_id")) or _extract_feishu_text(fields.get("recognition_id"))) == recog_id
        ]
        rollup_rules = [
            RollupRule(
                recog_id=recog_id,
                bitable_field=_extract_feishu_text(fields.get("bitable_field")) or "",
                type=(_extract_feishu_text(fields.get("type")) or "").upper(),
                sheet=_extract_feishu_text(fields.get("sheet")) or "",
                category=_extract_feishu_text(fields.get("category")),
                field=_extract_feishu_text(fields.get("field")) or "",
                condition=_extract_feishu_text(fields.get("condition")),
                optional=_extract_feishu_bool(fields.get("optional")),
            )
            for record in rule_records
            for fields in [record.get("fields", {})]
            if (_extract_feishu_text(fields.get("recog_id")) or _extract_feishu_text(fields.get("recognition_id"))) == recog_id
        ]

        return RuleBundle(recog_id=recog_id, source_sheets=source_sheets, rollup_rules=rollup_rules)


def _parse_optional_int(value: str | None) -> int | None:
    """把可空字符串转成可空整数。"""

    if value in (None, ""):
        return None
    return int(value)
