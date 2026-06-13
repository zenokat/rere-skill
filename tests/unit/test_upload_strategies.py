"""上传冲突策略辅助函数单元测试。"""

from __future__ import annotations

from core.upload.upload_strategies import build_upsert_key, records_differ


def test_build_upsert_key_normalizes_string_and_numeric_period_values() -> None:
    """联合键中的期间值应忽略字符串/数值格式差异。"""

    preview_key = build_upsert_key({"期间": "202605", "平台ID": "163007972"}, ["平台ID"])
    existing_key = build_upsert_key({"期间": 202605, "平台ID": "163007972"}, ["平台ID"])

    assert preview_key == existing_key == ("202605", "163007972")


def test_records_differ_ignores_numeric_format_noise() -> None:
    """记录比较应忽略常见的数字格式噪音。"""

    preview_record = {"期间": "202605", "平台ID": "163007972", "商品金额": 25455.5}
    existing_record = {"期间": 202605, "平台ID": "163007972", "商品金额": "25455.5"}

    assert records_differ(preview_record, existing_record) is False
