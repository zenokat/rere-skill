"""环境变量驱动的应用配置。

本项目不允许把飞书凭证、App Token、表 ID 等敏感或环境相关信息硬编码在代码里，
因此统一通过环境变量读取，再在这里做一次集中校验。
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from models.cli_results import CliExecutionError, ErrorResponse, ExitCode


class AppSettings(BaseModel):
    """应用运行所需配置。"""

    feishu_app_id: str
    feishu_app_secret: str
    config_bitable_app_token: str
    result_bitable_app_token: str
    project_catalog_table_id: str
    source_spec_table_id: str
    rollup_rule_table_id: str
    output_root: Path = Field(default=Path("/tmp/revenue-recognition/outputs"))
    request_timeout_seconds: int = 30
    trust_env_proxies: bool = False


def _load_dotenv_file(dotenv_path: Path) -> None:
    """从本地 `.env` 文件加载环境变量。

    约定：
    1. 仅处理 `KEY=VALUE` 的简单行
    2. 已经存在于进程环境中的变量不覆盖
    3. 允许使用单引号或双引号包裹值
    """

    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _build_settings_payload_from_env() -> dict[str, object]:
    """从环境变量组装配置字典。"""

    project_root = Path(__file__).resolve().parents[2]
    _load_dotenv_file(project_root / ".env")
    _load_dotenv_file(project_root / ".env.local")

    return {
        "feishu_app_id": os.getenv("RERE_FEISHU_APP_ID"),
        "feishu_app_secret": os.getenv("RERE_FEISHU_APP_SECRET"),
        "config_bitable_app_token": os.getenv("RERE_CONFIG_BITABLE_APP_TOKEN"),
        "result_bitable_app_token": os.getenv("RERE_RESULT_BITABLE_APP_TOKEN"),
        "project_catalog_table_id": os.getenv("RERE_PROJECT_CATALOG_TABLE_ID"),
        "source_spec_table_id": os.getenv("RERE_SOURCE_SPEC_TABLE_ID"),
        "rollup_rule_table_id": os.getenv("RERE_ROLLUP_RULE_TABLE_ID"),
        "output_root": os.getenv("RERE_OUTPUT_ROOT", "/tmp/revenue-recognition/outputs"),
        "request_timeout_seconds": int(os.getenv("RERE_REQUEST_TIMEOUT_SECONDS", "30")),
        "trust_env_proxies": os.getenv("RERE_TRUST_ENV_PROXIES", "false").strip().lower() in {"1", "true", "yes", "y"},
    }


def load_settings() -> AppSettings:
    """读取并校验应用配置。"""

    try:
        return AppSettings.model_validate(_build_settings_payload_from_env())
    except ValidationError as exc:
        raise CliExecutionError(
            exit_code=ExitCode.INVALID_ARGUMENT,
            response=ErrorResponse(
                stage="settings",
                message="Required environment variables are missing or invalid.",
                retryable=False,
                details=[{"error": error["msg"], "field": list(error["loc"])} for error in exc.errors()],
            ),
        ) from exc
