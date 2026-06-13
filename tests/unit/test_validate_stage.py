"""结构检验阶段中 condition 校验的单元测试。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from core.validation.validate_stage import ValidateStageImpl
from models.cli_results import CliExecutionError
from models.domain import RecognitionProject, RollupRule, RuleBundle, SourceSheetSpec


class _FakeCatalogRepository:
    """提供最小项目目录能力的测试替身。"""

    def __init__(self, project: RecognitionProject) -> None:
        """保存唯一测试项目。"""

        self._project = project

    def get_project(self, recog_id: str) -> RecognitionProject | None:
        """按 recog_id 返回测试项目。"""

        if recog_id == self._project.recog_id:
            return self._project
        return None


class _FakeRuleRepository:
    """返回固定 rule bundle 的测试替身。"""

    def __init__(self, bundle: RuleBundle) -> None:
        """保存测试规则。"""

        self._bundle = bundle

    def load_rule_bundle(self, recog_id: str) -> RuleBundle:
        """忽略传入 recog_id，直接返回固定 bundle。"""

        return self._bundle


class _FakeBitableClient:
    """提供最小字段列表能力的测试替身。"""

    def list_fields(self, app_token: str, table_id: str) -> list[dict[str, object]]:
        """返回 validate 通过所需的最小字段集合。"""

        return [
            {"field_name": "期间", "type": 2},
            {"field_name": "门店", "type": 1},
            {"field_name": "已结算金额", "type": 2},
        ]


class _FakeSettings:
    """只暴露 ValidateStageImpl 依赖的配置字段。"""

    result_bitable_app_token = "dummy-app-token"


def test_validate_stage_reports_condition_placeholder_with_structured_code() -> None:
    """condition 仍是占位符时，应返回清晰的结构化错误信息。"""

    tmp_dir = Path.cwd() / "tests" / "_tmp_validate_stage" / uuid4().hex
    tmp_dir.mkdir(parents=True, exist_ok=True)
    source_file = tmp_dir / "source.csv"
    source_file.write_text(
        "门店,结算时间,金额\n"
        "华北一店,2026-03-20,100\n",
        encoding="utf-8",
    )

    bundle = RuleBundle(
        recog_id="demo_recog",
        source_sheets=[
            SourceSheetSpec(
                recog_id="demo_recog",
                sheet="DEFAULT",
                field_row=1,
                last_row=-1,
            )
        ],
        rollup_rules=[
            RollupRule(
                recog_id="demo_recog",
                bitable_field="门店",
                type="GROUP",
                sheet="DEFAULT",
                field="门店",
            ),
            RollupRule(
                recog_id="demo_recog",
                bitable_field="已结算金额",
                type="SUM",
                sheet="DEFAULT",
                field="金额",
                condition="CONDITION",
            ),
        ],
    )

    service = ValidateStageImpl(
        catalog_repository=_FakeCatalogRepository(
            RecognitionProject(
                recog_id="demo_recog",
                recog_name="演示项目",
                bitable_table_id="tbl-demo",
                bitable_table_exists=True,
            )
        ),
        rule_repository=_FakeRuleRepository(bundle),
        bitable_client=_FakeBitableClient(),
        settings=_FakeSettings(),  # type: ignore[arg-type]
    )

    with pytest.raises(CliExecutionError) as exc_info:
        service.run("demo_recog", source_file)

    payload = exc_info.value.response.model_dump(mode="json")
    checks = payload["details"][0]["checks"]
    condition_failures = [check for check in checks if check["check_name"] == "condition_valid" and not check["passed"]]

    assert len(condition_failures) == 1
    assert condition_failures[0]["scope"] == "rule:已结算金额"
    assert condition_failures[0]["details"][0]["code"] == "condition_placeholder_detected"
