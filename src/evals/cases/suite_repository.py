"""suite manifest 仓储。

仓储层很薄，只负责从路径读取 suite。保留这个层是为了后续可以平滑接入远端 case
仓库或版本化 case registry，而不改 runner 主流程。
"""

from __future__ import annotations

from pathlib import Path

from evals.cases.manifest_loader import load_suite_manifest
from evals.cases.manifest_models import EvalSuiteManifest


class SuiteRepository:
    """从本地文件系统读取评测 suite。"""

    def load(self, path: Path) -> EvalSuiteManifest:
        """加载 suite manifest。

        Args:
            path: manifest 路径。

        Returns:
            EvalSuiteManifest: 结构化 suite。
        """

        return load_suite_manifest(path)

