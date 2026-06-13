"""飞书 baseline 解包辅助单元测试。"""

from __future__ import annotations

import pytest

from tests.helpers.feishu_baseline import (
    extract_feishu_scalar,
    fetch_period_baseline_records,
    flatten_feishu_fields,
)


def test_extract_feishu_scalar_unwraps_nested_type_value_payload() -> None:
    """飞书返回的 type/value 包装应被正确解包。"""

    value = {
        "type": 2,
        "value": [202605],
    }

    assert extract_feishu_scalar(value) == 202605


def test_extract_feishu_scalar_prefers_text_from_link_field() -> None:
    """关联/富文本字段中的 text 应优先作为比较值。"""

    value = [{"text": "MD00105", "type": "text"}]

    assert extract_feishu_scalar(value) == "MD00105"


def test_flatten_feishu_fields_converts_mixed_payloads_to_plain_dict() -> None:
    """整条飞书 fields 应被压平成普通字典。"""

    fields = {
        "期间": {"type": 2, "value": [202605]},
        "全来店ID": [{"text": "MD00105", "type": "text"}],
        "流水金额": 20452.18,
    }

    flattened = flatten_feishu_fields(fields)

    assert flattened == {
        "期间": 202605,
        "全来店ID": "MD00105",
        "流水金额": 20452.18,
    }


def test_fetch_period_baseline_records_uses_string_filter_for_text_period_field() -> None:
    """当 `期间` 是文本字段时，应使用字符串值筛选。"""

    class FakeClient:
        """用于校验筛选值类型的假客户端。"""

        def list_fields(self, app_token: str, table_id: str) -> list[dict[str, object]]:
            return [{"field_name": "期间", "type": 1}]

        def search_records(
            self,
            app_token: str,
            table_id: str,
            *,
            field_names: list[str] | None = None,
            filter_info: dict[str, object] | None = None,
        ) -> list[dict[str, object]]:
            assert field_names == ["期间", "平台ID"]
            assert filter_info == {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": "期间",
                        "operator": "is",
                        "value": ["202604"],
                    }
                ],
            }
            return [{"fields": {"期间": "202604", "平台ID": "DY001"}}]

    records = fetch_period_baseline_records(
        FakeClient(),  # type: ignore[arg-type]
        app_token="app-token",
        table_id="table-id",
        period=202604,
        field_names=["平台ID"],
    )

    assert records == [{"期间": "202604", "平台ID": "DY001"}]


def test_fetch_period_baseline_records_uses_numeric_filter_for_number_period_field() -> None:
    """当 `期间` 是数值字段时，应使用整数值筛选。"""

    class FakeClient:
        """用于校验数值期间筛选的假客户端。"""

        def list_fields(self, app_token: str, table_id: str) -> list[dict[str, object]]:
            return [{"field_name": "期间", "type": 2}]

        def search_records(
            self,
            app_token: str,
            table_id: str,
            *,
            field_names: list[str] | None = None,
            filter_info: dict[str, object] | None = None,
        ) -> list[dict[str, object]]:
            assert field_names == ["期间", "平台ID"]
            assert filter_info == {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_name": "期间",
                        "operator": "is",
                        "value": [202604],
                    }
                ],
            }
            return [{"fields": {"期间": {"type": 2, "value": [202604]}, "平台ID": "DY001"}}]

    records = fetch_period_baseline_records(
        FakeClient(),  # type: ignore[arg-type]
        app_token="app-token",
        table_id="table-id",
        period="202604",
        field_names=["平台ID"],
    )

    assert records == [{"期间": 202604, "平台ID": "DY001"}]


def test_fetch_period_baseline_records_rejects_invalid_period_token() -> None:
    """非法期间格式应尽早报错，而不是静默查空。"""

    class FakeClient:
        """这里不会真的被调用到远端。"""

        def list_fields(self, app_token: str, table_id: str) -> list[dict[str, object]]:
            return [{"field_name": "期间", "type": 1}]

    with pytest.raises(ValueError, match="6-digit YYYYMM"):
        fetch_period_baseline_records(
            FakeClient(),  # type: ignore[arg-type]
            app_token="app-token",
            table_id="table-id",
            period="2026-04",
            field_names=["平台ID"],
        )
