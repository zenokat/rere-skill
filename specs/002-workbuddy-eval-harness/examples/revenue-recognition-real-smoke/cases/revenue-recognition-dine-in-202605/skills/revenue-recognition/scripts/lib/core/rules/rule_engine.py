"""规则求值引擎。

本模块负责两件核心事情：
1. 把配置表里的 `condition` 校验为“可安全执行的单行布尔表达式”
2. 在 preview 阶段基于当前行数据和运行期上下文实际计算条件真假

首版只开放文档中约定的最小 helper 集合，统一要求通过 `F("字段名")`
访问源字段，不再允许直接把字段名当成自由变量写进表达式。
"""

from __future__ import annotations

import ast
import re
from functools import lru_cache
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from core.source_resolver import ColumnDescriptor, SheetDataset, extract_rule_value
from models.domain import RollupRule

DEFAULT_VALIDATION_PERIOD = "200001"
PLACEHOLDER_CONDITION_TOKENS = {"CONDITION"}
ALLOWED_RUNTIME_NAMES = {"current_period"}
CONDITION_HELPER_NAMES = {
    "F",
    "is_blank",
    "has_value",
    "as_number",
    "period_of",
    "add_months",
}

ALLOWED_AST_NODES = (
    ast.Add,
    ast.And,
    ast.BinOp,
    ast.BoolOp,
    ast.Call,
    ast.Compare,
    ast.Constant,
    ast.Div,
    ast.Eq,
    ast.Expression,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.Is,
    ast.IsNot,
    ast.List,
    ast.Load,
    ast.Lt,
    ast.LtE,
    ast.Mod,
    ast.Mult,
    ast.Name,
    ast.Not,
    ast.NotEq,
    ast.NotIn,
    ast.Or,
    ast.Set,
    ast.Sub,
    ast.Tuple,
    ast.UAdd,
    ast.UnaryOp,
    ast.USub,
)


@dataclass
class PreparedCondition:
    """条件表达式的可执行形态。"""

    expression: str
    context: dict[str, Any]
    available_fields: set[str]
    ambiguous_fields: set[str]
    compiled_code: Any | None = None
    compiled_expression: str | None = None
    validated: bool = False


class ConditionEvaluationError(ValueError):
    """condition 校验或执行失败时抛出的结构化异常。"""

    code = "condition_runtime_error"

    def __init__(self, message: str, *, field: str | None = None) -> None:
        """初始化带错误码的 condition 异常。"""

        super().__init__(message)
        self.field = field


class ConditionPlaceholderError(ConditionEvaluationError):
    """condition 仍然是占位符。"""

    code = "condition_placeholder_detected"


class ConditionParseError(ConditionEvaluationError):
    """condition 语法无法解析。"""

    code = "condition_parse_failed"


class ConditionAstNotAllowedError(ConditionEvaluationError):
    """condition 使用了未开放的 AST 节点。"""

    code = "condition_ast_not_allowed"


class ConditionFunctionNotAllowedError(ConditionEvaluationError):
    """condition 调用了白名单外函数。"""

    code = "condition_function_not_allowed"


class ConditionInvalidFCallError(ConditionEvaluationError):
    """condition 中的 F(...) 用法不符合约束。"""

    code = "condition_invalid_f_call"


class ConditionIdentifierUnresolvedError(ConditionEvaluationError):
    """condition 引用了无法解析的标识。"""

    code = "condition_identifier_unresolved"


class ConditionRuntimeExecutionError(ConditionEvaluationError):
    """condition 在运行时执行失败。"""

    code = "condition_runtime_error"


def validate_condition_expression(expression: str, prepared: PreparedCondition) -> None:
    """校验一个条件表达式是否能被安全执行。"""

    normalized_expression = expression.strip()
    _raise_if_placeholder_condition(normalized_expression)
    try:
        tree = _parse_condition_expression(normalized_expression)
    except SyntaxError as exc:
        raise ConditionParseError("condition 语法无法解析。") from exc
    _ConditionValidator(prepared).visit(tree)


def evaluate_condition(expression: str | None, prepared: PreparedCondition) -> bool:
    """计算单行数据是否满足某条条件。"""

    if not expression:
        return True
    compiled = prepare_compiled_condition(expression, prepared)
    try:
        return bool(eval(compiled, {"__builtins__": {}}, prepared.context))
    except ConditionEvaluationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ConditionRuntimeExecutionError("condition 执行失败。") from exc


def prepare_compiled_condition(expression: str, prepared: PreparedCondition) -> Any:
    """校验并编译 condition，供 preview 复用。"""

    normalized_expression = expression.strip()
    if not prepared.validated or prepared.compiled_expression != normalized_expression:
        validate_condition_expression(expression, prepared)
        prepared.validated = True
        prepared.compiled_expression = normalized_expression
        if prepared.expression != normalized_expression:
            prepared.expression = normalized_expression
        prepared.compiled_code = None
    if prepared.compiled_code is None:
        prepared.compiled_code = compile(prepared.expression, "<condition>", "eval")
    return prepared.compiled_code


def prepare_condition_context(
    dataset: SheetDataset,
    row_values: dict[tuple[str, str], Any],
    *,
    current_period: str | None,
) -> PreparedCondition:
    """为条件表达式构造运行期上下文。"""

    field_values, ambiguous_fields = _build_field_value_lookup(dataset=dataset, row_values=row_values)
    normalized_current_period = _normalize_current_period(current_period)
    context: dict[str, Any] = {
        "current_period": normalized_current_period,
        "F": lambda field_name: _resolve_field_value(
            field_name=field_name,
            field_values=field_values,
            ambiguous_fields=ambiguous_fields,
        ),
        "is_blank": is_blank,
        "has_value": has_value,
        "as_number": as_number,
        "period_of": period_of,
        "add_months": add_months,
    }
    return PreparedCondition(
        expression="",
        context=context,
        available_fields=set(field_values),
        ambiguous_fields=ambiguous_fields,
    )


def build_prepared_condition(
    expression: str,
    dataset: SheetDataset,
    row_values: dict[tuple[str, str], Any],
    *,
    current_period: str | None = None,
) -> PreparedCondition:
    """将原始条件表达式转换成安全可执行形式。"""

    prepared = prepare_condition_context(
        dataset=dataset,
        row_values=row_values,
        current_period=current_period,
    )
    prepared.expression = expression.strip()
    return prepared


def coerce_numeric_value(rule: RollupRule, value: Any) -> float:
    """将 SUM 字段值转成可汇总数字。"""

    if value in (None, ""):
        if rule.optional:
            return 0.0
        raise ValueError(f"SUM field '{rule.field}' is empty.")
    if isinstance(value, (int, float)):
        return float(value)

    normalized = _normalize_numeric_text(value)
    if not normalized:
        if rule.optional:
            return 0.0
        raise ValueError(f"SUM field '{rule.field}' is empty.")
    return float(normalized)


def is_blank(value: Any) -> bool:
    """判断一个值是否应被视为空。"""

    return value is None or (isinstance(value, str) and value.strip() == "")


def has_value(value: Any) -> bool:
    """判断一个值是否为非空。"""

    return not is_blank(value)


def as_number(value: Any) -> float | None:
    """把常见文本/数值格式归一化成 float。"""

    if is_blank(value):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)

    normalized = _normalize_numeric_text(value)
    if not normalized:
        return None
    try:
        return float(Decimal(normalized))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Cannot convert value to number: {value!r}") from exc


def _normalize_numeric_text(value: Any) -> str:
    """规范化常见财务文本数值格式。"""

    normalized = str(value).replace(",", "").replace("`", "").strip()
    if re.fullmatch(r"[-—–－]+", normalized):
        return "0"
    return normalized


def period_of(value: Any) -> str | None:
    """从日期/时间/期间文本中提取 YYYYMM。"""

    if is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y%m")
    if isinstance(value, date):
        return value.strftime("%Y%m")

    normalized = str(value).strip()
    if not normalized:
        return None

    digits_only = re.sub(r"\D", "", normalized)
    if len(digits_only) == 6:
        return _validate_period_token(digits_only)
    if len(digits_only) >= 8:
        candidate = digits_only[:6]
        validated = _validate_period_token(candidate)
        if validated:
            return validated

    match = re.search(r"(?P<year>\d{4})\D*(?P<month>0?[1-9]|1[0-2])", normalized)
    if match:
        candidate = f"{match.group('year')}{int(match.group('month')):02d}"
        return _validate_period_token(candidate)
    return None


def add_months(period: Any, offset: Any) -> str:
    """对 YYYYMM 期间做月偏移。"""

    normalized_period = _normalize_current_period(period)
    try:
        month_offset = int(offset)
    except (TypeError, ValueError) as exc:
        raise ValueError("The offset passed to add_months must be an integer.") from exc

    year = int(normalized_period[:4])
    month = int(normalized_period[4:])
    total_months = year * 12 + (month - 1) + month_offset
    shifted_year = total_months // 12
    shifted_month = total_months % 12 + 1
    return f"{shifted_year:04d}{shifted_month:02d}"


def _build_field_value_lookup(
    dataset: SheetDataset,
    row_values: dict[tuple[str, str], Any],
) -> tuple[dict[str, Any], set[str]]:
    """构造 `F("字段名")` 使用的字段值字典。

    这里同时保留两种命名：
    1. 原始字段名，例如 `订单类型`
    2. 分类+字段名，例如 `实收组成_人民币`

    如果同一个名字映射到多列，则把它记为歧义字段，后续 `F(...)` 会显式报错。
    """

    field_values: dict[str, Any] = {}
    ambiguous_fields: set[str] = set()

    for column in dataset.columns:
        value = extract_rule_value(row_values, column)
        candidate_names = [column.field]
        if column.category:
            candidate_names.append(f"{column.category}_{column.field}")

        for field_name in candidate_names:
            normalized_name = field_name.strip()
            if not normalized_name:
                continue
            if normalized_name in ambiguous_fields:
                continue
            if normalized_name in field_values:
                ambiguous_fields.add(normalized_name)
                field_values.pop(normalized_name, None)
                continue
            field_values[normalized_name] = value
    return field_values, ambiguous_fields


def _resolve_field_value(
    *,
    field_name: Any,
    field_values: dict[str, Any],
    ambiguous_fields: set[str],
) -> Any:
    """按 `F("字段名")` 的固定语义精确读取当前行字段值。"""

    if not isinstance(field_name, str) or not field_name.strip():
        raise ConditionInvalidFCallError("F 只允许接收一个非空字符串字段名。")

    normalized_field_name = field_name.strip()
    if normalized_field_name in ambiguous_fields or normalized_field_name not in field_values:
        raise ConditionIdentifierUnresolvedError(
            f"condition 引用了无法解析的字段：{normalized_field_name}",
            field=normalized_field_name,
        )
    return field_values[normalized_field_name]


def _normalize_current_period(current_period: Any) -> str:
    """把运行期 current_period 规范成 YYYYMM。"""

    if current_period is None:
        return DEFAULT_VALIDATION_PERIOD

    normalized_period = period_of(current_period)
    if normalized_period is None:
        raise ConditionRuntimeExecutionError("current_period 必须能解析成 YYYYMM 期间。")
    return normalized_period


def _validate_period_token(candidate: str) -> str | None:
    """校验候选 YYYYMM 是否是合法期间。"""

    if not re.fullmatch(r"\d{6}", candidate):
        return None
    month = int(candidate[4:])
    if 1 <= month <= 12:
        return candidate
    return None


def _raise_if_placeholder_condition(expression: str) -> None:
    """拦截明显的占位符 condition。"""

    if expression.strip().upper() in PLACEHOLDER_CONDITION_TOKENS:
        raise ConditionPlaceholderError("condition 仍是占位符，尚未补成真实表达式。")


@lru_cache(maxsize=256)
def _parse_condition_expression(expression: str) -> ast.Expression:
    """缓存表达式解析结果，避免在大批量 preview 时反复 parse/校验 AST。"""

    tree = ast.parse(expression, mode="eval")
    _attach_parent_references(tree)
    return tree


def _attach_parent_references(tree: ast.AST) -> None:
    """为 AST 节点补 parent 引用，便于做结构校验。"""

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_condition_parent", parent)


class _ConditionValidator(ast.NodeVisitor):
    """对 condition AST 做首版白名单校验。"""

    def __init__(self, prepared: PreparedCondition) -> None:
        """保存运行期上下文，便于校验 `F("字段名")`。"""

        self._prepared = prepared

    def generic_visit(self, node: ast.AST) -> None:
        """先做节点白名单判断，再递归访问子节点。"""

        if not isinstance(node, ALLOWED_AST_NODES):
            raise ConditionAstNotAllowedError("condition 使用了不被允许的语法节点。")
        super().generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """校验 helper 调用是否合法。"""

        if not isinstance(node.func, ast.Name):
            raise ConditionFunctionNotAllowedError("condition 调用了不被允许的函数。")

        function_name = node.func.id
        if function_name not in CONDITION_HELPER_NAMES:
            raise ConditionFunctionNotAllowedError("condition 调用了不被允许的函数。")

        if function_name == "F":
            self._validate_f_call(node)

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """只允许运行时变量和 helper 名称出现在固定位置。"""

        parent = getattr(node, "_condition_parent", None)
        if isinstance(parent, ast.Call) and parent.func is node:
            return
        if node.id in ALLOWED_RUNTIME_NAMES:
            return
        raise ConditionIdentifierUnresolvedError(
            f"condition 引用了无法解析的字段：{node.id}",
            field=node.id,
        )

    def _validate_f_call(self, node: ast.Call) -> None:
        """校验 `F("字段名")` 的固定写法。"""

        if len(node.args) != 1 or node.keywords:
            raise ConditionInvalidFCallError("F 只允许接收一个字符串字面量参数。")

        argument = node.args[0]
        if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
            raise ConditionInvalidFCallError("F 只允许接收一个字符串字面量参数。")

        field_name = argument.value.strip()
        if not field_name:
            raise ConditionInvalidFCallError("F 只允许接收一个非空字符串字段名。")

        if field_name in self._prepared.ambiguous_fields or field_name not in self._prepared.available_fields:
            raise ConditionIdentifierUnresolvedError(
                f"condition 引用了无法解析的字段：{field_name}",
                field=field_name,
            )
