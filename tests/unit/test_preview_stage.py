"""preview 阶段辅助逻辑单元测试。"""

from __future__ import annotations

from core.preview.preview_stage import PreviewStageImpl


def test_fill_missing_group_values_uses_unique_candidate_per_source_group() -> None:
    """缺失 GROUP 值在同源维度下只有唯一候选时应自动补齐。"""

    records = [
        {
            "平台ID": "10004",
            "平台门店名称": "蔡林记襄阳白马广场店",
            "来源文件": "武汉市蔡林记餐饮发展有限公司",
            "订单金额": 100.0,
        },
        {
            "平台ID": None,
            "平台门店名称": "蔡林记襄阳白马广场店",
            "来源文件": "武汉市蔡林记餐饮发展有限公司",
            "订单金额": 4.0,
        },
    ]

    PreviewStageImpl._fill_missing_group_values(records, ["平台ID", "平台门店名称", "来源文件"])

    assert records[1]["平台ID"] == "10004"


def test_merge_records_after_group_value_backfill_combines_numeric_fields() -> None:
    """回填缺失 GROUP 值后，应把同键记录重新合并。"""

    records = [
        {
            "期间": "202605",
            "平台ID": "10004",
            "平台门店名称": "蔡林记襄阳白马广场店",
            "来源文件": "武汉市蔡林记餐饮发展有限公司",
            "订单金额": 62114.3,
            "退款金额": 152.5,
            "手续费": 157.58,
        },
        {
            "期间": "202605",
            "平台ID": None,
            "平台门店名称": "蔡林记襄阳白马广场店",
            "来源文件": "武汉市蔡林记餐饮发展有限公司",
            "订单金额": 4.0,
            "退款金额": 0.0,
            "手续费": 0.01,
        },
    ]

    merged = PreviewStageImpl._normalize_and_merge_group_records(records, ["平台ID", "平台门店名称", "来源文件"])

    assert merged == [
        {
            "期间": "202605",
            "平台ID": "10004",
            "平台门店名称": "蔡林记襄阳白马广场店",
            "来源文件": "武汉市蔡林记餐饮发展有限公司",
            "订单金额": 62118.3,
            "退款金额": 152.5,
            "手续费": 157.59,
        }
    ]
