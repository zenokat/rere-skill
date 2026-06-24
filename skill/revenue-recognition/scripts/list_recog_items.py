#!/usr/bin/env python3
"""列出收入确认项目的 skill 随包入口。

本脚本只包装 `list_recog_items` 工具调用，方便 skill 作为压缩包交付后仍有稳定、
非交互的脚本入口。业务规则仍由底层汇总工具负责。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
from pathlib import Path
from typing import Any, Sequence

COMMAND_NOT_FOUND_EXIT_CODE = 127


def write_json(payload: dict[str, Any]) -> None:
    """把结构化结果写到标准输出。

    参数:
        payload: 需要输出的 JSON 对象。

    返回值:
        无。函数直接写 stdout。
    """

    print(json.dumps(payload, ensure_ascii=False, indent=2))


def fail(message: str, exit_code: int = 2, **extra: Any) -> int:
    """输出结构化失败结果并返回退出码。

    参数:
        message: 失败说明。
        exit_code: 进程退出码。
        **extra: 额外上下文。

    返回值:
        应作为进程退出码返回的整数。
    """

    payload: dict[str, Any] = {
        "status": "error",
        "tool": "list_recog_items",
        "message": message,
        "exit_code": exit_code,
    }
    payload.update(extra)
    write_json(payload)
    return exit_code


def parse_output(value: str) -> Any:
    """尽量把底层工具输出解析为 JSON。

    参数:
        value: 底层工具 stdout。

    返回值:
        JSON 对象；若不是 JSON，则返回原文。
    """

    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。

    参数:
        无。

    返回值:
        argparse.ArgumentParser 实例。
    """

    parser = argparse.ArgumentParser(description="列出可用收入确认项目。")
    parser.add_argument(
        "--command",
        default=os.getenv("REVENUE_RECOGNITION_LIST_COMMAND", "list_recog_items"),
        help="底层 list_recog_items 命令路径；默认使用 PATH 上的 list_recog_items。",
    )
    parser.add_argument("--tool-root", help="底层汇总工具源码根目录。提供后以 python -m cli.list_recog_items 调用。")
    parser.add_argument("--python", default=sys.executable, help="配合 --tool-root 使用的 Python 解释器。")
    parser.add_argument("--dry-run", action="store_true", help="只输出将要执行的命令，不真正调用底层工具。")
    return parser


def build_command(args: argparse.Namespace) -> tuple[list[str], Path | None, dict[str, str]]:
    """根据参数构造底层命令。

    参数:
        args: 解析后的命令行参数。

    返回值:
        三元组：命令参数、工作目录、环境变量。
    """

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if args.tool_root:
        tool_root = Path(args.tool_root).expanduser().resolve()
        existing_pythonpath = env.get("PYTHONPATH")
        src_path = str(tool_root / "src")
        env["PYTHONPATH"] = src_path if not existing_pythonpath else os.pathsep.join([src_path, existing_pythonpath])
        return [args.python, "-m", "cli.list_recog_items"], tool_root, env
    return [args.command], None, env


def validate_args(args: argparse.Namespace) -> int | None:
    """校验脚本自身可以提前发现的问题。

    参数:
        args: 解析后的命令行参数。

    返回值:
        成功返回 None；失败返回退出码。
    """

    if args.tool_root:
        tool_root = Path(args.tool_root).expanduser()
        if not tool_root.exists():
            return fail("--tool-root 不存在。", parameter="tool_root", path=str(tool_root))
        if not (tool_root / "src" / "cli" / "list_recog_items.py").exists():
            return fail("--tool-root 下未找到 src/cli/list_recog_items.py。", path=str(tool_root))
        return None

    if shutil.which(args.command) is None and not Path(args.command).exists():
        return fail("找不到 list_recog_items 命令。请安装 CLI，或传入 --tool-root / --command。", exit_code=COMMAND_NOT_FOUND_EXIT_CODE)
    return None


def run_command(command: list[str], cwd: Path | None, env: dict[str, str], dry_run: bool) -> int:
    """执行底层命令并输出结构化结果。

    参数:
        command: 底层命令参数。
        cwd: 工作目录。
        env: 环境变量。
        dry_run: 为 True 时只输出命令。

    返回值:
        进程退出码。
    """

    if dry_run:
        write_json({"status": "dry_run", "tool": "list_recog_items", "command": command, "cwd": str(cwd) if cwd else None})
        return 0

    try:
        completed = subprocess.run(command, cwd=str(cwd) if cwd else None, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
    except FileNotFoundError:
        return fail("底层 list_recog_items 命令不存在。", exit_code=COMMAND_NOT_FOUND_EXIT_CODE, command=command)

    payload: dict[str, Any] = {
        "status": "ok" if completed.returncode == 0 else "error",
        "tool": "list_recog_items",
        "exit_code": completed.returncode,
        "tool_output": parse_output(completed.stdout),
    }
    if completed.stderr.strip():
        payload["stderr"] = completed.stderr.strip()
    write_json(payload)
    return completed.returncode


def main(argv: Sequence[str] | None = None) -> int:
    """脚本主入口。

    参数:
        argv: 可选命令行参数；为空时读取 sys.argv。

    返回值:
        进程退出码。
    """

    parser = build_parser()
    args = parser.parse_args(argv)
    validation_exit_code = validate_args(args)
    if validation_exit_code is not None:
        return validation_exit_code
    command, cwd, env = build_command(args)
    return run_command(command, cwd, env, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
