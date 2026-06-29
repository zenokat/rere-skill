"""评测批次 ID 生成工具。"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
_SLUG_PATTERN = re.compile(r"[^a-zA-Z0-9_-]+")

# 评测面向本地使用者，batch_id 时间戳用北京时间（UTC+8）记录，便于按本地时间检索。
BEIJING_TZ = timezone(timedelta(hours=8))


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。

    Returns:
        datetime: 当前 UTC 时间，后续统一用 ISO 格式写入 JSON。
    """

    return datetime.now(timezone.utc)


def beijing_now() -> datetime:
    """返回带北京时区（UTC+8）的当前时间。

    Returns:
        datetime: 当前北京时间，用于生成面向本地使用者的时间戳。
    """

    return datetime.now(BEIJING_TZ)


def slugify(value: str) -> str:
    """把任意名称转换成适合路径和 ID 的短标识。

    Args:
        value: 原始名称。

    Returns:
        str: 小写、仅包含字母数字、下划线和短横线的标识。
    """

    slug = _SLUG_PATTERN.sub("-", value.strip()).strip("-").lower()
    return slug or "unnamed"


def make_batch_id(suite_id: str, now: datetime | None = None) -> str:
    """生成批次 ID。

    Args:
        suite_id: case 集主键。
        now: 可选时间，测试中可传入固定值。时间戳按北京时间（UTC+8）格式化。

    Returns:
        str: 批次 ID，例如 `20260626-181530-rollup-smoke`（北京本地时间）。
    """

    selected = now or beijing_now()
    timestamp = selected.astimezone(BEIJING_TZ).strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{slugify(suite_id)}"
