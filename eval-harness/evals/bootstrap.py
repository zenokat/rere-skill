"""eval harness 应用服务装配。

CLI 只负责解析参数；这里负责读取最小评测集并调用 BatchRunner。首版不再装配
profile、baseline、额外报告视图或 fake runner。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.cases.suite_repository import SuiteRepository
from evals.runners.batch_runner import BatchRunner


class EvalHarness:
    """评测底座应用服务。"""

    def __init__(self, repo_root: Path) -> None:
        """初始化应用服务。

        Args:
            repo_root: 仓库根目录。
        """

        self._repo_root = repo_root.resolve()
        self._suite_repository = SuiteRepository()
        self._batch_runner = BatchRunner(repo_root=self._repo_root)

    def run_batch(
        self,
        *,
        suite_path: Path,
        output_root: Path,
        selected_case_ids: list[str] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """运行一批评测 case。

        Args:
            suite_path: case manifest 路径。
            output_root: 输出根目录。
            selected_case_ids: 可选 case 白名单。
            model: 可选模型 ID 覆盖值；为空时使用 suite.yaml 的 `model`
                配置或 CodeBuddy 默认模型。

        Returns:
            dict[str, Any]: 批次结果。
        """

        manifest = self._suite_repository.load(suite_path)
        return self._batch_runner.run(
            manifest=manifest,
            output_root=output_root,
            selected_case_ids=selected_case_ids,
            model=model,
        )


def build_eval_harness(repo_root: Path | None = None) -> EvalHarness:
    """构造评测底座应用服务。

    Args:
        repo_root: 可选仓库根目录；为空时从当前文件向上推导。

    Returns:
        EvalHarness: 应用服务实例。
    """

    root = repo_root or Path(__file__).resolve().parents[2]
    return EvalHarness(repo_root=root)
