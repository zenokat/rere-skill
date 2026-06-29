# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "openpyxl>=3.1,<4.0",
#     "pydantic>=2.8,<3.0",
#     "requests>=2.32,<3.0",
#     "typer>=0.12,<1.0",
# ]
# ///
#!/usr/bin/env python3
"""收入确认汇总阶段的 self-contained 入口脚本。

本脚本是 skill 的可交付产品入口：内联声明第三方依赖（PEP 723），把随包
``lib/`` 目录注入 ``sys.path``，直接挂载随包实现的汇总 CLI。它不再转发到
系统 PATH 上的命令，也不再回指原始开发仓库，离开任何仓库都能独立运行。

业务逻辑（结构检验、试算预览、受控上传、飞书 Bitable 调用）全部在随包
``lib/`` 内实现，连真实飞书远端。运行前需要通过环境变量或 skill 包根的
``.env`` 提供飞书凭据（参考 ``.env.example``）。

调用方式：

    uv run scripts/run_recog_rollup.py --validate --recog_id <id> --source_file <path>
    uv run scripts/run_recog_rollup.py --preview --recog_id <id> --period <YYYYMM> --source_file <path>
    uv run scripts/run_recog_rollup.py --upload --recog_id <id> --result_file <path>
"""

from __future__ import annotations

import sys
from pathlib import Path

# 把随包 lib/ 注入 sys.path 最前，使随包 import（from cli./core./...）
# 解析到 skill 包内代码，而非系统 PATH 或宿主 PYTHONPATH。
_LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from cli.run_recog_rollup import app  # noqa: E402


def main() -> None:
    """命令行入口函数。"""

    app()


if __name__ == "__main__":
    main()
