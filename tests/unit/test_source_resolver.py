"""源文件解析缓存的单元测试。"""

from __future__ import annotations

from pathlib import Path

from core import source_resolver
from models.domain import SourceSheetSpec


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
