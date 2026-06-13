"""项目补丁注册器单元测试。"""

from __future__ import annotations

from core.rules.project_patches import apply_project_patches, register_project_patch
from models.domain import RollupRule, RuleBundle, SourceSheetSpec


def test_apply_project_patches_runs_registered_patch_in_order() -> None:
    """补丁应能按注册顺序修改 rule bundle。"""

    bundle = RuleBundle(
        recog_id="wechat_pay_settlement",
        source_sheets=[
            SourceSheetSpec(
                recog_id="wechat_pay_settlement",
                sheet="DEFAULT",
                category_row=1,
                field_row=2,
                last_row=10,
            )
        ],
        rollup_rules=[],
    )

    def add_group_rule(rule_bundle: RuleBundle) -> RuleBundle:
        rule_bundle.rollup_rules.append(
            RollupRule(
                recog_id=rule_bundle.recog_id,
                bitable_field="门店",
                type="GROUP",
                sheet="DEFAULT",
                field="门店",
            )
        )
        return rule_bundle

    register_project_patch("wechat_pay_settlement", add_group_rule)
    patched = apply_project_patches(bundle)

    assert len(patched.rollup_rules) == 1
    assert patched.rollup_rules[0].bitable_field == "门店"

