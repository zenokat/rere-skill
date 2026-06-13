"""源文件解析缓存的单元测试。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from core import source_resolver
from models.domain import SourceSheetSpec

TMP_ROOT = Path.cwd() / "tests" / "_tmp_source_resolver"


def _make_tmp_dir() -> Path:
    """在仓库内创建可写临时目录，避免系统临时目录权限问题。"""

    tmp_dir = TMP_ROOT / uuid4().hex
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


def test_build_sheet_dataset_reuses_workbook_snapshot_for_same_file(monkeypatch) -> None:
    """同一工作簿解析多个 sheet 时应复用一次加载结果。"""

    target_file = Path("demo.xlsx")
    load_cache = source_resolver.SourceFileLoadCache()
    snapshot_calls: list[Path] = []

    def fake_build_workbook_snapshot(source_file: Path) -> source_resolver.WorkbookSnapshot:
        """返回固定快照，并记录被调用次数。"""

        snapshot_calls.append(source_file)
        return source_resolver.WorkbookSnapshot(
            sheet_names=("SheetA", "SheetB"),
            raw_rows_by_sheet={
                "SheetA": [["门店", "金额"], ["A店", "10"]],
                "SheetB": [["门店", "金额"], ["B店", "20"]],
            },
        )

    monkeypatch.setattr(source_resolver, "_build_workbook_snapshot", fake_build_workbook_snapshot)

    source_resolver.build_sheet_dataset(
        target_file,
        SourceSheetSpec(recog_id="demo", sheet="SheetA", field_row=1, last_row=-1),
        load_cache=load_cache,
    )
    source_resolver.build_sheet_dataset(
        target_file,
        SourceSheetSpec(recog_id="demo", sheet="SheetB", field_row=1, last_row=-1),
        load_cache=load_cache,
    )

    assert snapshot_calls == [target_file]


def test_build_sheet_dataset_injects_file_name_virtual_column() -> None:
    """CSV 数据集应自动提供 `FILE_NAME` 虚拟列。"""

    tmp_dir = _make_tmp_dir()
    source_file = tmp_dir / "wechat-demo.csv"
    source_file.write_text(
        "门店,金额\n"
        "A店,10\n",
        encoding="utf-8",
    )

    dataset = source_resolver.build_sheet_dataset(
        source_file,
        SourceSheetSpec(recog_id="demo", sheet="DEFAULT", field_row=1, last_row=-1),
    )

    assert any(column.field == "FILE_NAME" for column in dataset.columns)
    assert dataset.data_rows[0][("", "FILE_NAME")] == "wechat-demo"


def test_build_sheet_dataset_strips_backtick_prefix_from_csv_values() -> None:
    """CSV 单元格中的前缀反引号应被清理。"""

    tmp_dir = _make_tmp_dir()
    source_file = tmp_dir / "wechat-demo.csv"
    source_file.write_text(
        "平台ID,平台门店名称,订单金额\n"
        "`1001,`蔡林记中南店,`12.50\n",
        encoding="utf-8",
    )

    dataset = source_resolver.build_sheet_dataset(
        source_file,
        SourceSheetSpec(recog_id="demo", sheet="DEFAULT", field_row=1, last_row=-1),
    )

    row = dataset.data_rows[0]
    assert row[("", "平台ID")] == "1001"
    assert row[("", "平台门店名称")] == "蔡林记中南店"
    assert row[("", "订单金额")] == "12.50"


def test_build_sheet_dataset_skips_blank_csv_rows() -> None:
    """CSV 中的全空白行不应占用 `field_row` 计数。"""

    tmp_dir = _make_tmp_dir()
    source_file = tmp_dir / "alipay-demo.csv"
    source_file.write_text(
        "#标题\n"
        "\n"
        "#账号\n"
        "\n"
        "#日期\n"
        "\n"
        "#列表\n"
        "\n"
        "门店编号,商家实收（元）,服务费（元）\n"
        "1001,12.50,-0.03\n",
        encoding="utf-8",
    )

    dataset = source_resolver.build_sheet_dataset(
        source_file,
        SourceSheetSpec(recog_id="demo", sheet="DEFAULT", field_row=5, last_row=-1),
    )

    fields = [column.field for column in dataset.columns]
    assert "门店编号" in fields
    assert "商家实收（元）" in fields
    assert dataset.data_rows[0][("", "门店编号")] == "1001"
