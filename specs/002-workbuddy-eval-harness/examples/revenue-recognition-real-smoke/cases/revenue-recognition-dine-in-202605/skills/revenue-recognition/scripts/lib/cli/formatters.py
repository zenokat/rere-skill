"""CLI 输出格式化工具。"""

from __future__ import annotations

import json
from typing import Any

import typer
from pydantic import BaseModel

from models.cli_results import CliExecutionError, ExitCode


def emit_json(payload: BaseModel | dict[str, Any]) -> None:
    """将结构化对象输出为 JSON。"""

    serializable = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    typer.echo(json.dumps(serializable, ensure_ascii=False, indent=2))


def exit_with_json(payload: BaseModel | dict[str, Any], exit_code: int = ExitCode.OK) -> None:
    """输出 JSON 并以指定退出码结束。"""

    emit_json(payload)
    raise typer.Exit(code=int(exit_code))


def handle_cli_execution_error(error: CliExecutionError) -> None:
    """统一处理结构化 CLI 异常。"""

    exit_with_json(error.response, error.exit_code)

