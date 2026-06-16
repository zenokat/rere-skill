"""上传仓库的单元测试。"""

from __future__ import annotations

from integrations.feishu_bitable.upload_repository import FeishuUploadRepository


class _FakeClient:
    """最小化的飞书客户端替身。"""

    def __init__(self) -> None:
        self.list_fields_calls: list[tuple[str, str]] = []
        self.search_records_calls: list[tuple[str, str, object]] = []
        self.batch_create_payload: list[dict[str, object]] | None = None

    def list_fields(self, app_token: str, table_id: str) -> list[dict[str, object]]:
        self.list_fields_calls.append((app_token, table_id))
        return [
            {"field_name": "期间", "type": 2},
            {"field_name": "平台ID", "type": 1},
            {"field_name": "实际回款", "type": 2},
        ]

    def search_records(
        self,
        app_token: str,
        table_id: str,
        *,
        field_names=None,
        filter_info=None,
    ) -> list[dict[str, object]]:
        self.search_records_calls.append((app_token, table_id, filter_info))
        return []

    def batch_create_records(self, app_token: str, table_id: str, records: list[dict[str, object]]) -> dict[str, object]:
        self.batch_create_payload = records
        return {"records": records}


def test_upload_repository_reuses_field_metadata_for_same_table() -> None:
    """同一表连续查询期间并上传时，应复用一次字段元数据读取。"""

    client = _FakeClient()
    repository = FeishuUploadRepository(client=client, result_bitable_app_token="app-token")

    records = repository.search_period_records("tbl-demo", period="202605")
    create_result = repository.create_records(
        "tbl-demo",
        [{"期间": "202605", "平台ID": "1001", "实际回款": "12.50"}],
    )

    assert records == []
    assert create_result["records"] == client.batch_create_payload
    assert client.batch_create_payload == [
        {"fields": {"期间": 202605, "平台ID": "1001", "实际回款": 12.5}}
    ]
    assert client.list_fields_calls == [("app-token", "tbl-demo")]
