"""确认项目目录仓库。"""

from __future__ import annotations

from typing import Any, Protocol

from integrations.feishu_bitable.client import BitableApiClient
from models.domain import RecognitionProject
from utils.settings import AppSettings


class ProjectCatalogRepository(Protocol):
    """项目目录仓库协议。"""

    def list_projects(self) -> list[RecognitionProject]:
        """列出全部注册项目。"""

    def get_project(self, recog_id: str) -> RecognitionProject | None:
        """按业务主键读取单个项目。"""


def _extract_feishu_text(value: Any) -> str | None:
    """从飞书字段值中提取最合适的文本表示。"""

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


class FeishuProjectCatalogRepository:
    """基于飞书多维表的确认项目目录仓库。"""

    def __init__(self, client: BitableApiClient, settings: AppSettings) -> None:
        """初始化仓库。"""

        self._client = client
        self._settings = settings

    def list_projects(self) -> list[RecognitionProject]:
        """读取项目注册表并补充目标表存在性。"""

        records = self._client.list_records(
            app_token=self._settings.config_bitable_app_token,
            table_id=self._settings.project_catalog_table_id,
        )
        available_tables = {
            table.get("table_id")
            for table in self._client.list_tables(self._settings.result_bitable_app_token)
        }

        projects: list[RecognitionProject] = []
        for record in records:
            fields = record.get("fields", {})
            table_id = _extract_feishu_text(fields.get("bitable_table_id"))
            projects.append(
                RecognitionProject(
                    recog_id=_extract_feishu_text(fields.get("recog_id")) or "",
                    recog_name=_extract_feishu_text(fields.get("recog_name")) or "",
                    bitable_table_id=table_id,
                    bitable_table_exists=bool(table_id and table_id in available_tables),
                )
            )
        return projects

    def get_project(self, recog_id: str) -> RecognitionProject | None:
        """读取单个项目。"""

        for project in self.list_projects():
            if project.recog_id == recog_id:
                return project
        return None
