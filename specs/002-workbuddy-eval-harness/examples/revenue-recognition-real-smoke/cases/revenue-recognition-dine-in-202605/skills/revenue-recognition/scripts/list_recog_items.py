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
"""列出可用收入确认项目的 self-contained 入口脚本。

本脚本是 skill 的可交付产品入口：内联声明第三方依赖（PEP 723），把随包
``lib/`` 目录注入 ``sys.path``，直接挂载随包实现的项目列示 CLI。它不再转发到
系统 PATH 上的命令，也不再回指原始开发仓库，离开任何仓库都能独立运行。

调用方式：

    uv run scripts/list_recog_items.py

运行前需要通过环境变量或 skill 包根的 ``.env`` 提供飞书凭据（参考
``.env.example``）。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 把随包 lib/ 注入 sys.path 最前，使随包 import（from cli./core./...）
# 解析到 skill 包内代码，而非系统 PATH 或宿主 PYTHONPATH。
_LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from cli.list_recog_items import app  # noqa: E402


def main() -> None:
    """命令行入口函数。"""

    app()


if __name__ == "__main__":
    main()
