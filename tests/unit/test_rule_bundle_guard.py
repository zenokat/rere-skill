"""规则集合语义护栏单元测试。"""

from __future__ import annotations

import pytest

from core.rules.rule_bundle_guard import ensure_rule_bundle_supported
from models.cli_results import CliExecutionError
from models.domain import RollupRule, RuleBundle


def test_rule_bundle_guard_rejects_duplicate_sum_output_fields() -> None:
    """同一 SUM 输出字段对应多条规则时，应直接阻断。"""

    bundle = RuleBundle(
        recog_id="meituan_delivery_revenue",
        rollup_rules=[
            RollupRule(
                recog_id="meituan_delivery_revenue",
                bitable_field="平台服务费",
                type="SUM",
                sheet="DEFAULT",
                field="佣金",
            ),
            RollupRule(
                recog_id="meituan_delivery_revenue",
                bitable_field="平台服务费",
                type="SUM",
                sheet="DEFAULT",
                field="配送服务费",
            ),
        ],
    )

    with pytest.raises(CliExecutionError) as exc_info:
        ensure_rule_bundle_supported(bundle)

    payload = exc_info.value.response.model_dump(mode="json")
    assert payload["stage"] == "validate"
    assert payload["recog_id"] == "meituan_delivery_revenue"
    assert payload["details"][0]["bitable_field"] == "平台服务费"
    assert payload["details"][0]["rule_count"] == 2
