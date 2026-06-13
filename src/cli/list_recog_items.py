"""`list_recog_items` CLI 入口。"""

from __future__ import annotations

import typer

from cli.formatters import exit_with_json, handle_cli_execution_error
from core.catalog.list_projects_use_case import ListProjectsUseCase
from core.catalog.project_catalog_repository import FeishuProjectCatalogRepository
from integrations.feishu_bitable.client import BitableApiClient, TenantAccessTokenProvider
from utils.settings import load_settings

app = typer.Typer(add_completion=False, help="列出全部已注册的收入确认项目。")


def build_use_case() -> ListProjectsUseCase:
    """构造真实运行时依赖。"""

    settings = load_settings()
    token_provider = TenantAccessTokenProvider(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        timeout_seconds=settings.request_timeout_seconds,
        trust_env=settings.trust_env_proxies,
    )
    client = BitableApiClient(
        token_provider=token_provider,
        timeout_seconds=settings.request_timeout_seconds,
        trust_env=settings.trust_env_proxies,
    )
    repository = FeishuProjectCatalogRepository(client=client, settings=settings)
    return ListProjectsUseCase(repository=repository)


@app.command()
def list_projects() -> None:
    """执行项目目录列示。"""

    try:
        response = build_use_case().execute()
        exit_with_json(response)
    except Exception as exc:
        if isinstance(exc, typer.Exit):
            raise
        if hasattr(exc, "response") and hasattr(exc, "exit_code"):
            handle_cli_execution_error(exc)  # type: ignore[arg-type]
            return
        raise


def main() -> None:
    """命令行入口函数。"""

    app()


if __name__ == "__main__":
    main()
