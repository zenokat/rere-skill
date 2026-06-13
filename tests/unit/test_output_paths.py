"""输出路径工具单元测试。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from utils.output_paths import build_preview_output_path, sanitize_file_stem


def test_sanitize_file_stem_replaces_unsafe_characters() -> None:
    """文件名片段应替换掉不安全字符。"""

    assert sanitize_file_stem("wechat/pay:settlement") == "wechat_pay_settlement"


def test_build_preview_output_path_uses_period_recog_id_and_timestamp(tmp_path: Path) -> None:
    """preview 路径应包含期间、项目主键和时间戳。"""

    output_path = build_preview_output_path(
        period="202605",
        recog_id="wechat_pay_settlement",
        output_root=tmp_path,
        generated_at=datetime(2026, 6, 7, 12, 34, 56),
    )

    assert output_path == tmp_path / "202605_wechat_pay_settlement_20260607-123456.xlsx"

