"""pytest 共享测试配置。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _inject_src_into_sys_path() -> None:
    """把 `src/` 和 `tests/` 注入 `sys.path`，便于导入项目包与测试辅助模块。"""

    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    tests_path = repo_root / "tests"

    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    if str(tests_path) not in sys.path:
        sys.path.insert(0, str(tests_path))


_inject_src_into_sys_path()


@pytest.fixture(scope="session")
def tmp_path_factory(request: pytest.FixtureRequest) -> pytest.TempPathFactory:
    """把 pytest 临时目录固定到仓库内，避免落到系统受限目录。"""

    factory = request.config._tmp_path_factory  # type: ignore[attr-defined]
    base_temp = Path(__file__).resolve().parents[1] / "tests" / "_pytest_tmp"
    base_temp.mkdir(parents=True, exist_ok=True)
    factory._basetemp = base_temp.resolve()  # type: ignore[attr-defined]
    return factory
