"""pytest 共享测试配置。"""

from __future__ import annotations

import sys
from pathlib import Path


def _inject_src_into_sys_path() -> None:
    """把 `src/` 和 `tests/` 注入 `sys.path`，便于导入项目包与测试辅助模块。"""

    src_path = Path(__file__).resolve().parents[1] / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    tests_path = Path(__file__).resolve().parents[0]
    if str(tests_path) not in sys.path:
        sys.path.insert(0, str(tests_path))


_inject_src_into_sys_path()
