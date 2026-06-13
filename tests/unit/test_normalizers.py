"""归一化工具单元测试。"""

from __future__ import annotations

from helpers.normalizers import normalize_record, normalize_scalar


def test_normalize_scalar_rounds_numbers() -> None:
    """数值应按约定精度归一化。"""

    assert normalize_scalar(12.3456) == 12.35


def test_normalize_record_trims_strings_and_converts_blank_to_none() -> None:
    """字符串两端空白应被去掉，空串应归一成 None。"""

    normalized = normalize_record({"门店": " 武汉中南店 ", "备注": "  "})

    assert normalized["门店"] == "武汉中南店"
    assert normalized["备注"] is None
