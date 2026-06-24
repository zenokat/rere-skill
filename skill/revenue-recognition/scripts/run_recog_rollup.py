#!/usr/bin/env python3
"""执行收入确认汇总阶段的 skill 随包入口。

本脚本只包装 `run_recog_rollup` 工具调用，提供稳定、非交互的 skill 脚本入口。
实际结构检验、试算、上传和业务规则仍由底层汇总工具负责。
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
PERIOD_PATTERN = re.compile(r"^\d{6}$")


EXIT_CODE_LABELS = {
    2: "参数或环境配置错误",
    10: "结构检验失败",
    11: "试算预览失败",
    12: "上传重复期间冲突",
    13: "上传远端失败",
    14: "项目目录或规则配置读取失败",
    15: "本地文件读写失败",
    COMMAND_NOT_FOUND_EXIT_CODE: "命令不存在",
}


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
        "tool": "run_recog_rollup",
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

    parser = argparse.ArgumentParser(description="执行收入确认汇总阶段：结构检验、试算预览或受控上传。")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--validate", action="store_true", help="仅执行结构检验。")
    mode_group.add_argument("--preview", action="store_true", help="仅执行试算预览。")
    mode_group.add_argument("--upload", action="store_true", help="仅执行上传。")

    strategy_group = parser.add_mutually_exclusive_group()
    strategy_group.add_argument("--append", action="store_true", help="上传时采用追加策略。")
    strategy_group.add_argument("--upsert", action="store_true", help="上传时采用覆盖策略。")

    parser.add_argument("--recog_id", required=True, help="确认项目主键。")
    parser.add_argument("--period", help="会计期间，格式 YYYYMM。preview 或完整流程需要。")
    parser.add_argument("--source_file", help="已完成预处理的干净源文件或目录。validate、preview 或完整流程需要。")
    parser.add_argument("--result_file", help="preview 阶段生成的结果文件。upload 需要。")
    parser.add_argument(
        "--command",
        default=os.getenv("REVENUE_RECOGNITION_ROLLUP_COMMAND", "run_recog_rollup"),
        help="底层 run_recog_rollup 命令路径；默认使用 PATH 上的 run_recog_rollup。",
    )
    parser.add_argument("--tool-root", help="底层汇总工具源码根目录。提供后以 python -m cli.run_recog_rollup 调用。")
    parser.add_argument("--python", default=sys.executable, help="配合 --tool-root 使用的 Python 解释器。")
    parser.add_argument("--dry-run", action="store_true", help="只输出将要执行的命令，不真正调用底层工具。")
    return parser


def resolve_mode(args: argparse.Namespace) -> str:
    """解析当前运行模式。

    参数:
        args: 解析后的命令行参数。

    返回值:
        模式名称：validate、preview、upload 或 full。
    """

    if args.validate:
        return "validate"
    if args.preview:
        return "preview"
    if args.upload:
        return "upload"
    return "full"


def ensure_path(raw_path: str | None, parameter: str) -> int | None:
    """检查路径参数是否存在。

    参数:
        raw_path: 用户传入的路径字符串。
        parameter: 参数名称。

    返回值:
        成功返回 None；失败返回退出码。
    """

    if not raw_path:
        return fail(f"{parameter} 为必填参数。", parameter=parameter)
    path = Path(raw_path).expanduser()
    if not path.exists():
        return fail(f"{parameter} 不存在。请提供已存在的文件或目录。", parameter=parameter, path=str(path))
    return None


def validate_args(args: argparse.Namespace, mode: str) -> int | None:
    """校验包装脚本自身可以提前发现的问题。

    参数:
        args: 解析后的命令行参数。
        mode: 当前运行模式。

    返回值:
        成功返回 None；失败返回退出码。
    """

    if args.tool_root:
        tool_root = Path(args.tool_root).expanduser()
        if not tool_root.exists():
            return fail("--tool-root 不存在。", parameter="tool_root", path=str(tool_root))
        if not (tool_root / "src" / "cli" / "run_recog_rollup.py").exists():
            return fail("--tool-root 下未找到 src/cli/run_recog_rollup.py。", path=str(tool_root))
    elif shutil.which(args.command) is None and not Path(args.command).exists():
        return fail("找不到 run_recog_rollup 命令。请安装 CLI，或传入 --tool-root / --command。", exit_code=COMMAND_NOT_FOUND_EXIT_CODE)

    if args.append or args.upsert:
        if mode != "upload":
            return fail("--append 和 --upsert 只能与 --upload 一起使用。")

    if mode in {"preview", "full"}:
        if not args.period:
            return fail("--period 为必填参数。", parameter="period", mode=mode)
        if not PERIOD_PATTERN.match(args.period):
            return fail("--period 必须是 YYYYMM 格式。", parameter="period", received=args.period)

    if mode in {"validate", "preview", "full"}:
        path_exit_code = ensure_path(args.source_file, "source_file")
        if path_exit_code is not None:
            return path_exit_code

    if mode == "upload":
        path_exit_code = ensure_path(args.result_file, "result_file")
        if path_exit_code is not None:
            return path_exit_code

    return None


def build_command(args: argparse.Namespace, mode: str) -> tuple[list[str], Path | None, dict[str, str]]:
    """根据参数构造底层命令。

    参数:
        args: 解析后的命令行参数。
        mode: 当前运行模式。

    返回值:
        三元组：命令参数、工作目录、环境变量。
    """

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    cwd: Path | None = None
    if args.tool_root:
        cwd = Path(args.tool_root).expanduser().resolve()
        src_path = str(cwd / "src")
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = src_path if not existing_pythonpath else os.pathsep.join([src_path, existing_pythonpath])
        command = [args.python, "-m", "cli.run_recog_rollup"]
    else:
        command = [args.command]

    if mode == "validate":
        command.extend(["--validate", "--recog_id", args.recog_id, "--source_file", args.source_file])
    elif mode == "preview":
        command.extend(["--preview", "--recog_id", args.recog_id, "--period", args.period, "--source_file", args.source_file])
    elif mode == "upload":
        command.append("--upload")
        if args.append:
            command.append("--append")
        if args.upsert:
            command.append("--upsert")
        command.extend(["--recog_id", args.recog_id, "--result_file", args.result_file])
    else:
        command.extend(["--recog_id", args.recog_id, "--period", args.period, "--source_file", args.source_file])

    return command, cwd, env


def run_command(command: list[str], cwd: Path | None, env: dict[str, str], mode: str, dry_run: bool) -> int:
    """执行底层命令并输出结构化结果。

    参数:
        command: 底层命令参数。
        cwd: 工作目录。
        env: 环境变量。
        mode: 当前运行模式。
        dry_run: 为 True 时只输出命令。

    返回值:
        进程退出码。
    """

    if dry_run:
        write_json({"status": "dry_run", "tool": "run_recog_rollup", "mode": mode, "command": command, "cwd": str(cwd) if cwd else None})
        return 0

    try:
        completed = subprocess.run(command, cwd=str(cwd) if cwd else None, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
    except FileNotFoundError:
        return fail("底层 run_recog_rollup 命令不存在。", exit_code=COMMAND_NOT_FOUND_EXIT_CODE, command=command)

    payload: dict[str, Any] = {
        "status": "ok" if completed.returncode == 0 else "error",
        "tool": "run_recog_rollup",
        "mode": mode,
        "exit_code": completed.returncode,
        "tool_output": parse_output(completed.stdout),
    }
    if completed.stderr.strip():
        payload["stderr"] = completed.stderr.strip()
    if completed.returncode != 0:
        payload["failure_type"] = EXIT_CODE_LABELS.get(completed.returncode, "底层工具返回非零退出码")
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
    mode = resolve_mode(args)
    validation_exit_code = validate_args(args, mode)
    if validation_exit_code is not None:
        return validation_exit_code
    command, cwd, env = build_command(args, mode)
    return run_command(command, cwd, env, mode, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
