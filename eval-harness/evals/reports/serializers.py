"""JSON 序列化辅助函数。

评测产物需要被 Agent 稳定读取，因此所有 JSON 都统一使用 UTF-8、缩进和排序策略。
这里也处理 Path、枚举和 Pydantic 对象，避免业务模块重复写转换代码。
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    """把常见 Python 对象转成 JSON 可写结构。

    Args:
        value: 原始对象。

    Returns:
        Any: 可被 json.dumps 处理的对象。
    """

    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value


def dumps_json(value: Any) -> str:
    """序列化为稳定 JSON 字符串。

    Args:
        value: 原始对象。

    Returns:
        str: UTF-8 友好的 JSON 文本。
    """

    return json.dumps(to_jsonable(value), ensure_ascii=False, indent=2, sort_keys=True)


def write_json(path: Path, value: Any) -> None:
    """把对象写入 JSON 文件。

    Args:
        path: 目标文件路径。
        value: 原始对象。

    Returns:
        None
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_json(value) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    """读取 JSON 对象文件。

    Args:
        path: JSON 文件路径。

    Returns:
        dict[str, Any]: JSON 对象。
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return payload

