"""规则引擎单元测试。"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.rules.rule_engine import (
    ConditionIdentifierUnresolvedError,
    ConditionInvalidFCallError,
    ConditionPlaceholderError,
    build_prepared_condition,
    coerce_numeric_value,
    evaluate_condition,
)
from core.source_resolver import ColumnDescriptor, SheetDataset
from models.domain import RollupRule


def _build_dataset() -> SheetDataset:
    """构造一个最小数据集供条件表达式测试。"""

    columns = [
        ColumnDescriptor(column_index=0, category=None, field="订单类型"),
        ColumnDescriptor(column_index=1, category=None, field="金额"),
        ColumnDescriptor(column_index=2, category=None, field="结算时间"),
        ColumnDescriptor(column_index=3, category="实收组成", field="人民币"),
    ]
    return SheetDataset(
        source_file=None,  # type: ignore[arg-type]
        logical_sheet="DEFAULT",
        physical_sheet="DEFAULT",
        total_rows=3,
        resolved_last_row=3,
        columns=columns,
        duplicate_columns={},
        data_rows=[
            {
                ("", "订单类型"): "索赔单",
                ("", "金额"): "12.5",
                ("", "结算时间"): datetime(2026, 3, 20, 12, 30, 0),
                ("实收组成", "人民币"): "10.00",
            }
        ],
        data_row_numbers=[3],
    )


def test_evaluate_condition_supports_f_helper_for_group_filter() -> None:
    """首版应支持通过 `F("字段名")` 判断单个枚举字段。"""

    dataset = _build_dataset()
    prepared = build_prepared_condition('F("订单类型") == "索赔单"', dataset, dataset.data_rows[0])

    assert evaluate_condition('F("订单类型") == "索赔单"', prepared) is True


def test_evaluate_condition_supports_period_helpers() -> None:
    """首版应支持通过 `period_of` 和 `current_period` 做期间过滤。"""

    dataset = _build_dataset()
    expression = 'period_of(F("结算时间")) == current_period'
    prepared = build_prepared_condition(expression, dataset, dataset.data_rows[0], current_period="202603")

    assert evaluate_condition(expression, prepared) is True


def test_evaluate_condition_supports_add_months_helper() -> None:
    """应支持对期间做月偏移判断。"""

    dataset = _build_dataset()
    expression = 'period_of(F("结算时间")) == add_months(current_period, 1)'
    prepared = build_prepared_condition(expression, dataset, dataset.data_rows[0], current_period="202602")

    assert evaluate_condition(expression, prepared) is True


def test_evaluate_condition_supports_category_prefixed_field_lookup() -> None:
    """带分类的字段应能通过 `分类_字段名` 精确访问。"""

    dataset = _build_dataset()
    expression = 'as_number(F("实收组成_人民币")) == 10'
    prepared = build_prepared_condition(expression, dataset, dataset.data_rows[0])

    assert evaluate_condition(expression, prepared) is True


def test_evaluate_condition_rejects_placeholder_expression() -> None:
    """占位符 condition 应被明确拦截。"""

    dataset = _build_dataset()
    prepared = build_prepared_condition("CONDITION", dataset, dataset.data_rows[0])

    with pytest.raises(ConditionPlaceholderError):
        evaluate_condition("CONDITION", prepared)


def test_evaluate_condition_rejects_non_literal_f_argument() -> None:
    """`F(...)` 只允许接收字符串字面量。"""

    dataset = _build_dataset()
    expression = 'F(订单类型) == "索赔单"'
    prepared = build_prepared_condition(expression, dataset, dataset.data_rows[0])

    with pytest.raises(ConditionInvalidFCallError):
        evaluate_condition(expression, prepared)


def test_evaluate_condition_rejects_unknown_field_name() -> None:
    """`F("字段名")` 引用不到字段时应明确报错。"""

    dataset = _build_dataset()
    expression = 'F("不存在字段") == "foo"'
    prepared = build_prepared_condition(expression, dataset, dataset.data_rows[0])

    with pytest.raises(ConditionIdentifierUnresolvedError):
        evaluate_condition(expression, prepared)


def test_coerce_numeric_value_returns_zero_for_optional_empty_sum() -> None:
    """可选 SUM 字段缺失时应按 0 处理。"""

    rule = RollupRule(
        recog_id="wechat_pay_settlement",
        bitable_field="服务费",
        type="SUM",
        sheet="DEFAULT",
        field="服务费",
        optional=True,
    )

    assert coerce_numeric_value(rule, "") == 0.0


def test_coerce_numeric_value_accepts_backtick_prefixed_numeric_string() -> None:
    """CSV 中带前缀反引号的数字文本应能被正确解析。"""

    rule = RollupRule(
        recog_id="wechat_pay_settlement",
        bitable_field="订单金额",
        type="SUM",
        sheet="DEFAULT",
        field="订单金额",
        optional=False,
    )

    assert coerce_numeric_value(rule, "`157.80") == 157.8
