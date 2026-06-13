"""结构检验阶段实现。"""

from __future__ import annotations

from pathlib import Path

from core.catalog.project_catalog_repository import ProjectCatalogRepository
from core.rules.project_patches import apply_project_patches
from core.rules.rule_engine import (
    ConditionEvaluationError,
    build_prepared_condition,
    evaluate_condition,
)
from core.rules.rule_repository import FeishuRuleRepository
from core.source_resolver import (
    SourceFileLoadCache,
    build_sheet_dataset,
    choose_validation_sample,
    discover_source_files,
    find_rule_matches,
    rule_applies_to_sheet,
)
from integrations.feishu_bitable.client import BitableApiClient
from models.cli_results import (
    CliExecutionError,
    ErrorResponse,
    ExitCode,
    ValidateSuccessResponse,
    ValidationCheckResult,
)
from models.domain import RuleBundle
from utils.settings import AppSettings

PERIOD_FIELD_NAME = "期间"

# 数值 / 文本类型做宽松推断，避免把飞书字段配置细节硬编码成过度刚性的规则。
NUMERIC_FIELD_TYPES = {2}
TEXTUAL_FIELD_TYPES = {1, 3}
PERIOD_ALLOWED_FIELD_TYPES = {1, 2}


class ValidateStageImpl:
    """执行结构检验。"""

    def __init__(
        self,
        catalog_repository: ProjectCatalogRepository,
        rule_repository: FeishuRuleRepository,
        bitable_client: BitableApiClient,
        settings: AppSettings,
    ) -> None:
        """初始化阶段依赖。"""

        self._catalog_repository = catalog_repository
        self._rule_repository = rule_repository
        self._bitable_client = bitable_client
        self._settings = settings

    def run(self, recog_id: str, source_file: Path) -> ValidateSuccessResponse:
        """执行结构检验。"""

        source_files = discover_source_files(source_file)
        sampled_source_file = choose_validation_sample(source_files=source_files, seed_key=f"{recog_id}:{source_file}")
        rule_bundle = apply_project_patches(self._rule_repository.load_rule_bundle(recog_id))
        project = self._catalog_repository.get_project(recog_id)
        if project is None or not project.bitable_table_id:
            raise CliExecutionError(
                exit_code=ExitCode.CATALOG_FAILED,
                response=ErrorResponse(
                    stage="catalog",
                    message="Target project or bitable table was not found during validation.",
                    recog_id=recog_id,
                    retryable=False,
                ),
            )

        checks: list[ValidationCheckResult] = []
        checks.extend(self._validate_source_sheet_specs(rule_bundle=rule_bundle, sampled_source_file=sampled_source_file))
        checks.extend(self._validate_target_fields(rule_bundle=rule_bundle, target_table_id=project.bitable_table_id))

        error_count = sum(0 if check.passed else 1 for check in checks)
        if error_count:
            raise CliExecutionError(
                exit_code=ExitCode.VALIDATION_FAILED,
                response=ErrorResponse(
                    stage="validate",
                    mode="validate",
                    recog_id=recog_id,
                    message="Validation failed.",
                    retryable=False,
                    details=[
                        {
                            "sampled_source_file": str(sampled_source_file),
                            "checks": [check.model_dump(mode="json") for check in checks],
                        }
                    ],
                ),
            )

        return ValidateSuccessResponse(
            recog_id=recog_id,
            checks=checks,
            sampled_source_file=str(sampled_source_file),
            error_count=0,
        )

    def _validate_source_sheet_specs(
        self,
        rule_bundle: RuleBundle,
        sampled_source_file: Path,
    ) -> list[ValidationCheckResult]:
        """检查源文件结构、字段和 condition。"""

        checks: list[ValidationCheckResult] = []
        load_cache = SourceFileLoadCache()
        for source_spec in rule_bundle.source_sheets:
            sheet_scope = f"sheet:{source_spec.sheet}"
            try:
                dataset = build_sheet_dataset(sampled_source_file, source_spec, load_cache=load_cache)
                checks.append(
                    ValidationCheckResult(
                        check_name="sheet_exists",
                        scope=sheet_scope,
                        passed=True,
                        message="Sheet exists.",
                    )
                )
                checks.append(
                    ValidationCheckResult(
                        check_name="data_range",
                        scope=sheet_scope,
                        passed=True,
                        message="The configured data range is valid.",
                        details=[
                            {
                                "sampled_source_file": str(sampled_source_file),
                                "physical_sheet": dataset.physical_sheet,
                                "resolved_last_row": dataset.resolved_last_row,
                            }
                        ],
                    )
                )
            except KeyError:
                checks.append(
                    ValidationCheckResult(
                        check_name="sheet_exists",
                        scope=sheet_scope,
                        passed=source_spec.optional,
                        message="Optional sheet is missing." if source_spec.optional else "Required sheet is missing.",
                        details=[{"sampled_source_file": str(sampled_source_file)}],
                    )
                )
                if source_spec.optional:
                    continue
                checks.append(
                    ValidationCheckResult(
                        check_name="data_range",
                        scope=sheet_scope,
                        passed=False,
                        message="The data range cannot be validated because the required sheet is missing.",
                        details=[{"sampled_source_file": str(sampled_source_file)}],
                    )
                )
                continue
            except ValueError as exc:
                checks.append(
                    ValidationCheckResult(
                        check_name="data_range",
                        scope=sheet_scope,
                        passed=False,
                        message=str(exc),
                        details=[{"sampled_source_file": str(sampled_source_file)}],
                    )
                )
                continue

            applicable_rules = [
                rule for rule in rule_bundle.rollup_rules if rule_applies_to_sheet(rule.sheet, source_spec.sheet)
            ]
            for rule in applicable_rules:
                matches = find_rule_matches(dataset=dataset, category=rule.category, field=rule.field)
                is_optional_group = rule.type == "GROUP" and rule.optional
                is_optional_sum = rule.type == "SUM" and rule.optional
                if not matches:
                    checks.append(
                        ValidationCheckResult(
                            check_name="field_exists",
                            scope=f"rule:{rule.bitable_field}",
                            passed=bool(is_optional_group or is_optional_sum),
                            message="Optional field is missing." if (is_optional_group or is_optional_sum) else "Required field is missing.",
                            details=[
                                {
                                    "sampled_source_file": str(sampled_source_file),
                                    "category": rule.category,
                                    "field": rule.field,
                                    "bitable_field": rule.bitable_field,
                                    "optional": rule.optional,
                                }
                            ],
                        )
                    )
                    continue
                if len(matches) > 1:
                    checks.append(
                        ValidationCheckResult(
                            check_name="field_exists",
                            scope=f"rule:{rule.bitable_field}",
                            passed=False,
                            message="The field mapping is duplicated in the sampled source file.",
                            details=[
                                {
                                    "sampled_source_file": str(sampled_source_file),
                                    "category": rule.category,
                                    "field": rule.field,
                                    "bitable_field": rule.bitable_field,
                                    "matched_columns": [column.column_index + 1 for column in matches],
                                }
                            ],
                        )
                    )
                    continue
                checks.append(
                    ValidationCheckResult(
                        check_name="field_exists",
                        scope=f"rule:{rule.bitable_field}",
                        passed=True,
                        message="Field exists.",
                        details=[
                            {
                                "sampled_source_file": str(sampled_source_file),
                                "sheet": source_spec.sheet,
                                "category": rule.category,
                                "field": rule.field,
                                "bitable_field": rule.bitable_field,
                                "matched_column": matches[0].column_index + 1,
                                "optional": rule.optional,
                            }
                        ],
                    )
                )

                if rule.condition:
                    try:
                        row_values = dataset.sample_row_values()
                        prepared = build_prepared_condition(
                            expression=rule.condition,
                            dataset=dataset,
                            row_values=row_values,
                        )
                        evaluate_condition(expression=rule.condition, prepared=prepared)
                        checks.append(
                            ValidationCheckResult(
                                check_name="condition_valid",
                                scope=f"rule:{rule.bitable_field}",
                                passed=True,
                                message="Condition can be evaluated.",
                                details=[
                                    {
                                        "sampled_source_file": str(sampled_source_file),
                                        "sheet": source_spec.sheet,
                                        "bitable_field": rule.bitable_field,
                                        "condition": rule.condition,
                                    }
                                ],
                            )
                        )
                    except ConditionEvaluationError as exc:
                        checks.append(
                            ValidationCheckResult(
                                check_name="condition_valid",
                                scope=f"rule:{rule.bitable_field}",
                                passed=False,
                                message=str(exc),
                                details=[
                                    {
                                        "sampled_source_file": str(sampled_source_file),
                                        "sheet": source_spec.sheet,
                                        "bitable_field": rule.bitable_field,
                                        "condition": rule.condition,
                                        "code": exc.code,
                                        "exception_type": type(exc).__name__,
                                    }
                                ],
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        checks.append(
                            ValidationCheckResult(
                                check_name="condition_valid",
                                scope=f"rule:{rule.bitable_field}",
                                passed=False,
                                message="condition 执行失败。",
                                details=[
                                    {
                                        "sampled_source_file": str(sampled_source_file),
                                        "sheet": source_spec.sheet,
                                        "bitable_field": rule.bitable_field,
                                        "condition": rule.condition,
                                        "code": "condition_runtime_error",
                                        "exception_type": type(exc).__name__,
                                    }
                                ],
                            )
                        )
        return checks

    def _validate_target_fields(self, rule_bundle: RuleBundle, target_table_id: str) -> list[ValidationCheckResult]:
        """检查目标飞书表字段是否存在，并做宽松类型校验。"""

        checks: list[ValidationCheckResult] = []
        field_items = self._bitable_client.list_fields(self._settings.result_bitable_app_token, target_table_id)
        field_name_to_type = {field_item.get("field_name"): field_item.get("type") for field_item in field_items}

        expected_fields: list[tuple[str, set[int]]] = [(PERIOD_FIELD_NAME, PERIOD_ALLOWED_FIELD_TYPES)]
        for rule in rule_bundle.rollup_rules:
            if rule.type == "SUM":
                expected_fields.append((rule.bitable_field, NUMERIC_FIELD_TYPES))
            elif rule.type == "GROUP":
                expected_fields.append((rule.bitable_field, TEXTUAL_FIELD_TYPES))

        seen_fields: set[str] = set()
        for field_name, allowed_types in expected_fields:
            if field_name in seen_fields:
                continue
            seen_fields.add(field_name)
            actual_type = field_name_to_type.get(field_name)
            if actual_type is None:
                checks.append(
                    ValidationCheckResult(
                        check_name="target_field_exists",
                        scope=f"bitable_field:{field_name}",
                        passed=False,
                        message="Target field is missing in the Bitable table.",
                        details=[{"target_table_id": target_table_id}],
                    )
                )
                continue

            checks.append(
                ValidationCheckResult(
                    check_name="target_field_exists",
                    scope=f"bitable_field:{field_name}",
                    passed=True,
                    message="Target field exists in the Bitable table.",
                )
            )

            if allowed_types and actual_type not in allowed_types:
                checks.append(
                    ValidationCheckResult(
                        check_name="target_field_type",
                        scope=f"bitable_field:{field_name}",
                        passed=False,
                        message="Target field type does not match the inferred expectation.",
                        details=[
                            {
                                "target_table_id": target_table_id,
                                "actual_type": actual_type,
                                "allowed_types": sorted(allowed_types),
                            }
                        ],
                    )
                )
            else:
                checks.append(
                    ValidationCheckResult(
                        check_name="target_field_type",
                        scope=f"bitable_field:{field_name}",
                        passed=True,
                        message="Target field type is compatible with the inferred expectation.",
                    )
                )
        return checks
