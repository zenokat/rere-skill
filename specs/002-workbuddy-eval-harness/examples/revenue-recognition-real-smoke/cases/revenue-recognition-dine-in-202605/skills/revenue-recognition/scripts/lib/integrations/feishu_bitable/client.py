"""飞书多维表 HTTP 客户端。

当前适配层只负责和飞书 API 对话，不参与业务判断：
1. 获取 tenant access token
2. 发起 Bitable 读写请求
3. 处理分页与基础错误
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests

from models.cli_results import CliExecutionError, ErrorResponse, ExitCode


@dataclass
class TenantAccessTokenCache:
    """缓存一次 tenant access token。"""

    token: str
    expires_at: datetime


class TenantAccessTokenProvider:
    """飞书 tenant access token 提供器。"""

    def __init__(self, app_id: str, app_secret: str, timeout_seconds: int = 30, trust_env: bool = False) -> None:
        """初始化 provider。"""

        self._app_id = app_id
        self._app_secret = app_secret
        self._timeout_seconds = timeout_seconds
        self._cache: TenantAccessTokenCache | None = None
        self._session = requests.Session()
        self._session.trust_env = trust_env

    def get_token(self) -> str:
        """获取可用 token，必要时自动刷新。"""

        if self._cache and datetime.now() < self._cache.expires_at:
            return self._cache.token

        response = self._session.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self._app_id, "app_secret": self._app_secret},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise CliExecutionError(
                exit_code=ExitCode.CATALOG_FAILED,
                response=ErrorResponse(
                    stage="auth",
                    message="Failed to get Feishu tenant access token.",
                    retryable=True,
                    details=[payload],
                ),
            )

        token = payload["tenant_access_token"]
        expire_seconds = int(payload.get("expire", 7200))
        self._cache = TenantAccessTokenCache(
            token=token,
            expires_at=datetime.now() + timedelta(seconds=max(expire_seconds - 60, 60)),
        )
        return token


class BitableApiClient:
    """飞书多维表 API 客户端。"""

    def __init__(self, token_provider: TenantAccessTokenProvider, timeout_seconds: int = 30, trust_env: bool = False) -> None:
        """初始化客户端。"""

        self._token_provider = token_provider
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()
        self._session.trust_env = trust_env

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        """执行一次飞书 API 请求。"""

        url = f"https://open.feishu.cn{path}"
        headers = {
            "Authorization": f"Bearer {self._token_provider.get_token()}",
            "Content-Type": "application/json; charset=utf-8",
        }
        response = self._session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise CliExecutionError(
                exit_code=ExitCode.CATALOG_FAILED,
                response=ErrorResponse(
                    stage="feishu_api",
                    message="Feishu Bitable API returned an error.",
                    retryable=True,
                    details=[payload],
                ),
            )
        return payload["data"]

    def list_tables(self, app_token: str) -> list[dict[str, Any]]:
        """列出某个 Bitable App 下的全部数据表。"""

        return self._paginate(
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables",
            list_key="items",
        )

    def list_fields(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        """列出某张数据表的全部字段。"""

        return self._paginate(
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            list_key="items",
        )

    def list_records(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        """列出某张数据表的全部记录。"""

        return self._paginate(
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            list_key="items",
        )

    def search_records(
        self,
        app_token: str,
        table_id: str,
        *,
        field_names: list[str] | None = None,
        filter_info: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """按条件查询某张数据表的记录。"""

        return self._paginate_with_body(
            path=f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
            list_key="items",
            body_builder=lambda page_token: {
                **({"field_names": field_names} if field_names else {}),
                **({"filter": filter_info} if filter_info else {}),
                **({"page_token": page_token} if page_token else {}),
            },
        )

    def batch_create_records(self, app_token: str, table_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        """批量创建记录。"""

        return self._request(
            "POST",
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            json_body={"records": records},
        )

    def batch_update_records(self, app_token: str, table_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        """批量更新记录。"""

        return self._request(
            "POST",
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
            json_body={"records": records},
        )

    def table_exists(self, app_token: str, table_id: str) -> bool:
        """判断某个目标表是否存在。"""

        return any(table.get("table_id") == table_id for table in self.list_tables(app_token))

    def _paginate(self, path: str, list_key: str) -> list[dict[str, Any]]:
        """处理飞书标准分页读取。"""

        items: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            data = self._request("GET", path, params=params)
            items.extend(data.get(list_key, []))

            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

        return items

    def _paginate_with_body(
        self,
        path: str,
        list_key: str,
        body_builder,
    ) -> list[dict[str, Any]]:
        """处理需要 POST body 的飞书标准分页读取。"""

        items: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            data = self._request(
                "POST",
                path,
                params={"page_size": 500},
                json_body=body_builder(page_token),
            )
            items.extend(data.get(list_key, []))

            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

        return items
