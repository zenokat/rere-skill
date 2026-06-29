"""eval harness 首版仍需要跨模块共享的极少量枚举。"""

from __future__ import annotations

from enum import StrEnum


class OutputFormat(StrEnum):
    """底层 CLI 的结果输出格式。"""

    JSON = "json"


class WritePolicy(StrEnum):
    """批量评测的写入策略。"""

    READ_ONLY = "read_only"
