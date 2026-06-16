"""归一化工具单元测试。"""

from __future__ import annotations

from helpers.normalizers import normalize_record, normalize_scalar


def test_normalize_scalar_rounds_numbers() -> None:
    """数值应按约定精度归一化。"""

    assert normalize_scalar(12.3456) == 12.35


def test_normalize_scalar_parses_numeric_strings() -> None:
    """看起来是数字的字符串也应归一成数值。"""

    assert normalize_scalar(" 8,651.93 ") == 8651.93
    assert normalize_scalar("-148.07") == -148.07


def test_normalize_record_trims_strings_and_converts_blank_to_none() -> None:
    """字符串两端空白应被去掉，空串应归一成 None。"""

    normalized = normalize_record({"门店": " 武汉中南店 ", "备注": "  "})

    assert normalized["门店"] == "武汉中南店"
    assert normalized["备注"] is None


def test_normalize_record_unifies_fullwidth_parentheses() -> None:
    """全角/半角括号差异不应造成业务文本不一致。"""

    normalized = normalize_record({"门店": " 蔡林记（积玉桥店） "})

    assert normalized["门店"] == "蔡林记(积玉桥店)"
