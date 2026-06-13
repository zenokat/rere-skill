"""baseline 对比前的归一化工具。

该模块仅供开发/测试阶段使用，不属于 CLI 工具本体的一部分。
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def normalize_scalar(value: Any, digits: int = 2) -> Any:
    """归一化单个标量值，尽量消除格式噪声。"""

    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        parsed_numeric = _try_parse_decimal(stripped)
        if parsed_numeric is not None:
            quantized = parsed_numeric.quantize(Decimal("1." + "0" * digits), rounding=ROUND_HALF_UP)
            return float(quantized)
        return stripped
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        quantized = Decimal(str(value)).quantize(Decimal("1." + "0" * digits), rounding=ROUND_HALF_UP)
        return float(quantized)
    return value


def normalize_record(record: dict[str, Any], digits: int = 2) -> dict[str, Any]:
    """归一化一条记录。"""

    return {key: normalize_scalar(value, digits=digits) for key, value in record.items()}


def _try_parse_decimal(value: str) -> Decimal | None:
    """尝试把纯数字字符串解析成 Decimal。"""

    candidate = value.replace(",", "")
    if not candidate:
        return None
    try:
        return Decimal(candidate)
    except Exception:  # noqa: BLE001
        return None
