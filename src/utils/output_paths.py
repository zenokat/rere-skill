"""结果文件路径工具。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def sanitize_file_stem(value: str) -> str:
    """将业务标识转换成安全文件名片段。"""

    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)


def build_preview_output_path(
    period: str,
    recog_id: str,
    output_root: Path,
    generated_at: datetime | None = None,
) -> Path:
    """构造 preview 结果文件路径。"""

    timestamp = (generated_at or datetime.now()).strftime("%Y%m%d-%H%M%S")
    safe_recog_id = sanitize_file_stem(recog_id)
    return output_root / f"{period}_{safe_recog_id}_{timestamp}.xlsx"


def ensure_output_root(output_root: Path) -> Path:
    """确保输出目录存在。"""

    output_root.mkdir(parents=True, exist_ok=True)
    return output_root

