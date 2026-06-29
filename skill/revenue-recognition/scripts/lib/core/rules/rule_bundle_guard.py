"""规则集合语义护栏。

该模块只负责检查“规则表本身是否满足汇总引擎的语义边界”，
避免把本应属于下游字段间运算的逻辑偷偷塞回步骤 3 的汇总阶段。
"""

from __future__ import annotations

from collections import defaultdict

from models.cli_results import CliExecutionError, ErrorResponse, ExitCode
from models.domain import RollupRule, RuleBundle


def ensure_rule_bundle_supported(rule_bundle: RuleBundle) -> RuleBundle:
    """确保规则集合没有超出当前汇总引擎语义边界。

    参数:
        rule_bundle: 某个 recog_id 对应的完整规则集合。

    返回:
        原样返回传入的 rule_bundle，方便调用方在加载后继续链式使用。

    异常:
        CliExecutionError: 当发现当前规则集合试图让同一 SUM 输出字段
        由多条规则共同累加时抛出。该模式会把“基础事实汇总”和“字段间派生计算”
        混在一起，不再符合本 feature 的职责边界。
    """

    duplicate_sum_rules = _collect_duplicate_sum_rules(rule_bundle.rollup_rules)
    if not duplicate_sum_rules:
        return rule_bundle

    details = [
        {
            "bitable_field": bitable_field,
            "rule_count": len(rules),
            "rules": [
                {
                    "sheet": rule.sheet,
                    "category": rule.category,
                    "field": rule.field,
                    "condition": rule.condition,
                    "optional": rule.optional,
                }
                for rule in rules
            ],
        }
        for bitable_field, rules in duplicate_sum_rules.items()
    ]

    raise CliExecutionError(
        exit_code=ExitCode.VALIDATION_FAILED,
        response=ErrorResponse(
            stage="validate",
            mode="validate",
            recog_id=rule_bundle.recog_id,
            message="同一 SUM 输出字段不允许对应多条汇总规则；请改为多个基础事实字段，并在下游做字段间运算。",
            retryable=False,
            details=details,
        ),
    )


def _collect_duplicate_sum_rules(rollup_rules: list[RollupRule]) -> dict[str, list[RollupRule]]:
    """收集同一 SUM 输出字段对应多条规则的冲突项。"""

    rules_by_field: dict[str, list[RollupRule]] = defaultdict(list)
    for rule in rollup_rules:
        if rule.type != "SUM":
            continue
        rules_by_field[rule.bitable_field].append(rule)

    return {
        bitable_field: rules
        for bitable_field, rules in rules_by_field.items()
        if len(rules) > 1
    }
