"""case 筛选器。

批次运行可以执行全部 enabled case，也可以通过 `--case` 只跑指定 case。筛选器负责
在入口处给出清晰错误，避免悄悄漏跑。
"""

from __future__ import annotations

from evals.cases.manifest_models import EvalCase, EvalSuiteManifest


class CaseSelectionError(ValueError):
    """case 选择失败时抛出的错误。"""


def select_cases(manifest: EvalSuiteManifest, selected_case_ids: list[str] | None = None) -> list[EvalCase]:
    """选择本轮要运行的 case。

    Args:
        manifest: suite manifest。
        selected_case_ids: 可选 case ID 白名单。

    Returns:
        list[EvalCase]: 本轮 case 列表。

    Raises:
        CaseSelectionError: 指定 case 不存在或未启用。
    """

    enabled_cases = manifest.enabled_cases()
    if not selected_case_ids:
        return enabled_cases
    by_id = {case.case_id: case for case in enabled_cases}
    missing = [case_id for case_id in selected_case_ids if case_id not in by_id]
    if missing:
        raise CaseSelectionError(f"指定 case 不存在或未启用: {', '.join(missing)}")
    return [by_id[case_id] for case_id in selected_case_ids]

