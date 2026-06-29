"""试算阶段实现。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.rules.project_patches import apply_project_patches
from core.rules.rule_bundle_guard import ensure_rule_bundle_supported
from core.rules.rule_engine import build_prepared_condition, coerce_numeric_value, evaluate_condition, prepare_compiled_condition
from core.rules.rule_repository import FeishuRuleRepository
from core.source_resolver import (
    SourceFileLoadCache,
    build_sheet_dataset,
    discover_source_files,
    find_rule_matches,
    rule_applies_to_sheet,
)
from models.cli_results import CliExecutionError, ErrorResponse, ExitCode, PreviewIssue, PreviewSuccessResponse
from models.domain import RollupRule

from .preview_artifact_writer import PreviewArtifactWriter

PERIOD_FIELD_NAME = "期间"


@dataclass(frozen=True)
class SumExecutionPlan:
    """单个 SUM 规则在当前 sheet 上的执行计划。"""

    rule: RollupRule
    column: Any
    compiled_condition: Any | None = None


class PreviewStageImpl:
    """执行规则驱动试算。"""

    def __init__(self, rule_repository: FeishuRuleRepository, artifact_writer: PreviewArtifactWriter) -> None:
        """初始化阶段依赖。"""

        self._rule_repository = rule_repository
        self._artifact_writer = artifact_writer

    def run(self, recog_id: str, period: str, source_file: Path) -> PreviewSuccessResponse:
        """执行试算。"""

        source_files = discover_source_files(source_file)
        rule_bundle = ensure_rule_bundle_supported(
            apply_project_patches(self._rule_repository.load_rule_bundle(recog_id))
        )
        group_rules = self._dedupe_output_rules([rule for rule in rule_bundle.rollup_rules if rule.type == "GROUP"])
        sum_rules = [rule for rule in rule_bundle.rollup_rules if rule.type == "SUM"]
        group_fields = [rule.bitable_field for rule in group_rules]

        aggregates: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
        issues: list[PreviewIssue] = []
        load_cache = SourceFileLoadCache()

        for current_file in source_files:
            for source_spec in rule_bundle.source_sheets:
                try:
                    dataset = build_sheet_dataset(
                        current_file,
                        source_spec,
                        load_cache=load_cache,
                        stream_to_end=True,
                    )
                except KeyError:
                    if source_spec.optional:
                        continue
                    issues.append(
                        PreviewIssue(
                            source_file=str(current_file),
                            sheet=source_spec.sheet,
                            message="Required sheet is missing.",
                        )
                    )
                    continue
                except ValueError as exc:
                    issues.append(
                        PreviewIssue(
                            source_file=str(current_file),
                            sheet=source_spec.sheet,
                            message=str(exc),
                        )
                    )
                    continue

                applicable_group_rules = [
                    rule for rule in group_rules if rule_applies_to_sheet(rule.sheet, source_spec.sheet)
                ]
                applicable_sum_rules = [
                    rule for rule in sum_rules if rule_applies_to_sheet(rule.sheet, source_spec.sheet)
                ]
                rule_columns = self._resolve_rule_columns(dataset, applicable_group_rules + applicable_sum_rules, issues)
                sum_execution_plans = self._build_sum_execution_plans(
                    dataset=dataset,
                    applicable_sum_rules=applicable_sum_rules,
                    rule_columns=rule_columns,
                    current_period=period,
                )

                for row_number, row_values in dataset.iter_data_rows():
                    try:
                        row_group_values = self._compute_row_group_values(
                            dataset=dataset,
                            row_values=row_values,
                            group_rules=applicable_group_rules,
                            rule_columns=rule_columns,
                        )
                        group_key = tuple(row_group_values.get(field_name) for field_name in group_fields)
                        aggregate_record = aggregates.setdefault(
                            group_key,
                            {PERIOD_FIELD_NAME: period, **{field_name: row_group_values.get(field_name) for field_name in group_fields}},
                        )
                        for field_name, field_value in row_group_values.items():
                            if field_value is not None:
                                aggregate_record[field_name] = field_value

                        row_condition_context = None

                        for plan in sum_execution_plans:
                            if plan.column is None:
                                aggregate_record[plan.rule.bitable_field] = float(
                                    aggregate_record.get(plan.rule.bitable_field, 0.0)
                                )
                                continue
                            if plan.rule.condition:
                                if row_condition_context is None:
                                    row_condition_context = build_prepared_condition(
                                        expression="",
                                        dataset=dataset,
                                        row_values=row_values,
                                        current_period=period,
                                    )
                                row_condition_context.expression = plan.rule.condition
                                row_condition_context.compiled_code = plan.compiled_condition
                                row_condition_context.compiled_expression = plan.rule.condition
                                row_condition_context.validated = True
                                if not evaluate_condition(plan.rule.condition, row_condition_context):
                                    continue
                            numeric_value = coerce_numeric_value(
                                rule=plan.rule,
                                value=row_values[(plan.column.category or "", plan.column.field)],
                            )
                            aggregate_record[plan.rule.bitable_field] = (
                                float(aggregate_record.get(plan.rule.bitable_field, 0.0)) + numeric_value
                            )
                    except Exception as exc:  # noqa: BLE001
                        issues.append(
                            PreviewIssue(
                                source_file=str(current_file),
                                sheet=source_spec.sheet,
                                row=row_number,
                                field=getattr(exc, "field", None),
                                message=str(exc),
                            )
                        )

        if issues:
            raise CliExecutionError(
                exit_code=ExitCode.PREVIEW_FAILED,
                response=ErrorResponse(
                    stage="preview",
                    mode="preview",
                    recog_id=recog_id,
                    message="Preview failed.",
                    retryable=False,
                    errors=issues,
                ),
            )

        records = list(aggregates.values())
        normalized_records = self._normalize_and_merge_group_records(records, group_fields)
        ordered_records = self._order_records(records=normalized_records, group_fields=group_fields, sum_rules=sum_rules)
        artifact = self._artifact_writer.write(recog_id=recog_id, period=period, records=ordered_records, group_fields=group_fields)
        return PreviewSuccessResponse(
            recog_id=recog_id,
            period=period,
            result_file=str(artifact.result_file),
            row_count=artifact.row_count,
            field_count=artifact.field_count,
            warnings=[],
        )

    @staticmethod
    def _dedupe_output_rules(rules: list[RollupRule]) -> list[RollupRule]:
        """按输出字段名去重，保留首次出现顺序。"""

        ordered: OrderedDict[str, RollupRule] = OrderedDict()
        for rule in rules:
            ordered.setdefault(rule.bitable_field, rule)
        return list(ordered.values())

    @staticmethod
    def _resolve_rule_columns(
        dataset,
        rules: list[RollupRule],
        issues: list[PreviewIssue],
    ):
        """为当前数据集解析每条规则对应的源列。"""

        rule_columns = {}
        for rule in rules:
            matches = find_rule_matches(dataset=dataset, category=rule.category, field=rule.field)
            if not matches:
                if rule.optional:
                    rule_columns[_rule_column_key(rule)] = None
                    continue
                issues.append(
                    PreviewIssue(
                        source_file=str(dataset.source_file),
                        sheet=dataset.logical_sheet,
                        field=rule.field,
                        message="Required field is missing.",
                    )
                )
                continue
            if len(matches) > 1:
                issues.append(
                    PreviewIssue(
                        source_file=str(dataset.source_file),
                        sheet=dataset.logical_sheet,
                        field=rule.field,
                        message="The field mapping is duplicated in the source file.",
                    )
                )
                continue
            rule_columns[_rule_column_key(rule)] = matches[0]
        return rule_columns

    @staticmethod
    def _build_sum_execution_plans(
        dataset,
        applicable_sum_rules,
        rule_columns,
        current_period: str,
    ) -> list[SumExecutionPlan]:
        """把当前 sheet 的 SUM 规则整理成更紧凑的执行计划。"""

        sample_row_values = dataset.sample_row_values()
        execution_plans: list[SumExecutionPlan] = []
        for rule in applicable_sum_rules:
            compiled_condition = None
            if rule.condition:
                prepared_condition = build_prepared_condition(
                    expression=rule.condition,
                    dataset=dataset,
                    row_values=sample_row_values,
                    current_period=current_period,
                )
                compiled_condition = prepare_compiled_condition(rule.condition, prepared_condition)
            execution_plans.append(
                SumExecutionPlan(
                    rule=rule,
                    column=rule_columns.get(_rule_column_key(rule)),
                    compiled_condition=compiled_condition,
                )
            )
        return execution_plans

    @staticmethod
    def _compute_row_group_values(dataset, row_values, group_rules, rule_columns):
        """计算当前行的全部 GROUP 输出字段。"""

        row_group_values: dict[str, Any] = {}
        for rule in group_rules:
            column = rule_columns.get(_rule_column_key(rule))
            if column is None:
                row_group_values[rule.bitable_field] = None
                continue
            raw_value = row_values[(column.category or "", column.field)]
            normalized_value = None if raw_value in (None, "") else raw_value
            row_group_values[rule.bitable_field] = normalized_value
        return row_group_values

    @staticmethod
    def _order_records(records: list[dict[str, Any]], group_fields: list[str], sum_rules: list[RollupRule]) -> list[dict[str, Any]]:
        """按约定输出字段顺序整理结果。"""

        sum_field_names = []
        for rule in sum_rules:
            if rule.bitable_field not in sum_field_names:
                sum_field_names.append(rule.bitable_field)

        ordered_records: list[dict[str, Any]] = []
        for record in records:
            ordered_record = {PERIOD_FIELD_NAME: record.get(PERIOD_FIELD_NAME)}
            for group_field in group_fields:
                ordered_record[group_field] = record.get(group_field)
            for sum_field_name in sum_field_names:
                ordered_record[sum_field_name] = round(float(record.get(sum_field_name, 0.0)), 2)
            ordered_records.append(ordered_record)
        return ordered_records

    @staticmethod
    def _fill_missing_group_values(records: list[dict[str, Any]], group_fields: list[str]) -> None:
        """用同源唯一候选回填缺失的 GROUP 值。"""

        for target_field in group_fields:
            other_group_fields = [field_name for field_name in group_fields if field_name != target_field]
            if target_field == "平台ID":
                prioritized_fields = [field_name for field_name in ["平台门店名称", "来源文件"] if field_name in other_group_fields]
                other_group_fields = prioritized_fields + [field_name for field_name in other_group_fields if field_name not in prioritized_fields]
            candidates_by_group: dict[tuple[Any, ...], set[Any]] = {}

            for record in records:
                candidate_value = record.get(target_field)
                if candidate_value in (None, ""):
                    continue
                group_key = tuple(record.get(field_name) for field_name in other_group_fields)
                candidates_by_group.setdefault(group_key, set()).add(candidate_value)

            for record in records:
                if record.get(target_field) not in (None, ""):
                    continue
                group_key = tuple(record.get(field_name) for field_name in other_group_fields)
                candidates = candidates_by_group.get(group_key, set())
                if len(candidates) == 1:
                    record[target_field] = next(iter(candidates))

    @classmethod
    def _normalize_and_merge_group_records(cls, records: list[dict[str, Any]], group_fields: list[str]) -> list[dict[str, Any]]:
        """回填缺失 GROUP 值后，重新按联合键合并记录。"""

        cls._fill_missing_group_values(records, group_fields)
        merged_records: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()

        for record in records:
            group_key = tuple(record.get(field_name) for field_name in group_fields)
            current = merged_records.get(group_key)
            if current is None:
                merged_records[group_key] = dict(record)
                continue

            for field_name, value in record.items():
                if field_name == PERIOD_FIELD_NAME or field_name in group_fields:
                    if current.get(field_name) in (None, "") and value not in (None, ""):
                        current[field_name] = value
                    continue
                current[field_name] = float(current.get(field_name, 0.0)) + float(value or 0.0)

        return list(merged_records.values())


def _rule_column_key(rule: RollupRule) -> tuple[str, str, str]:
    """为规则命中的源列生成稳定键。"""

    return (rule.type, rule.sheet, rule.bitable_field)
