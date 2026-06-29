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


def _skill_root() -> Path:
    """返回 skill 包根目录。

    本文件位于 ``<skill>/scripts/lib/utils/settings.py``，向上两级到达 skill 包根。
    skill 是独立可交付产品，配置只从“进程环境变量 + skill 包根的 .env”读取，
    不回读原始开发仓库。
    """

    return Path(__file__).resolve().parents[2]


def _load_dotenv_to_dict(dotenv_path: Path) -> dict[str, str]:
    """把本地 ``.env`` 文件解析成字典。

    约定：
    1. 仅处理 ``KEY=VALUE`` 的简单行
    2. 允许使用单引号或双引号包裹值

    与历史实现不同，本函数把结果返回给调用方，**不写入 ``os.environ``**，
    避免在可交付的 skill 内部产生隐式的进程级副作用。
    """

    values: dict[str, str] = {}
    if not dotenv_path.exists():
        return values

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _merged_env() -> dict[str, str]:
    """合并配置来源：进程环境变量优先，其次 skill 包根的 ``.env``。

    返回值:
        合并后的变量字典。进程环境变量优先级最高，确保 eval harness 或
        最终用户显式注入的凭据覆盖包内 ``.env`` 的默认值。
    """

    dotenv_values: dict[str, str] = {}
    dotenv_values.update(_load_dotenv_to_dict(_skill_root() / ".env"))
    dotenv_values.update(_load_dotenv_to_dict(_skill_root() / ".env.local"))

    merged: dict[str, str] = dict(dotenv_values)
    for key, value in os.environ.items():
        merged[key] = value
    return merged


def _build_settings_payload_from_env() -> dict[str, object]:
    """从“进程环境变量 + skill 包根 .env”组装配置字典。"""

    env = _merged_env()
    return {
        "feishu_app_id": env.get("RERE_FEISHU_APP_ID"),
        "feishu_app_secret": env.get("RERE_FEISHU_APP_SECRET"),
        "config_bitable_app_token": env.get("RERE_CONFIG_BITABLE_APP_TOKEN"),
        "result_bitable_app_token": env.get("RERE_RESULT_BITABLE_APP_TOKEN"),
        "project_catalog_table_id": env.get("RERE_PROJECT_CATALOG_TABLE_ID"),
        "source_spec_table_id": env.get("RERE_SOURCE_SPEC_TABLE_ID"),
        "rollup_rule_table_id": env.get("RERE_ROLLUP_RULE_TABLE_ID"),
        "output_root": env.get("RERE_OUTPUT_ROOT", "/tmp/revenue-recognition/outputs"),
        "request_timeout_seconds": int(env.get("RERE_REQUEST_TIMEOUT_SECONDS", "30")),
        "trust_env_proxies": env.get("RERE_TRUST_ENV_PROXIES", "false").strip().lower() in {"1", "true", "yes", "y"},
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
