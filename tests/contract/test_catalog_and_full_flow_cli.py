"""CLI 契约测试。

当前这一版先锁定两件事：
1. `list_recog_items` 的结构化输出契约
2. `run_recog_rollup` 参数解析与完整流程分发契约
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cli import list_recog_items, run_recog_rollup
from models.cli_results import CatalogSuccessResponse, UploadSuccessResponse
from models.domain import RecognitionProject, UploadStrategy

runner = CliRunner()


def test_list_recog_items_outputs_contract(monkeypatch) -> None:
    """`list_recog_items` 应按约定输出 `recog_id` 与 `recog_name`。"""

    class FakeUseCase:
        """用于替代真实仓库调用的假用例。"""

        def execute(self) -> CatalogSuccessResponse:
            """返回固定项目列表。"""

            return CatalogSuccessResponse(
                projects=[
                    RecognitionProject(
                        recog_id="wechat_pay_settlement",
                        recog_name="微信回款汇总",
                        bitable_table_id="tblxxxx",
                        bitable_table_exists=True,
                    )
                ],
                count=1,
            )

    monkeypatch.setattr(list_recog_items, "build_use_case", lambda: FakeUseCase())

    result = runner.invoke(list_recog_items.app, [])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["count"] == 1
    assert payload["projects"][0]["recog_id"] == "wechat_pay_settlement"
    assert payload["projects"][0]["recog_name"] == "微信回款汇总"


def test_run_recog_rollup_full_mode_dispatches_to_service(monkeypatch, tmp_path: Path) -> None:
    """默认模式应分发到完整流程，并保留 CLI 契约中的参数命名。"""

    source_file = tmp_path / "source.xlsx"
    source_file.write_text("placeholder", encoding="utf-8")

    class FakeService:
        """用于验证参数分发的假服务。"""

        def run_full(self, recog_id: str, period: str, source_file: Path) -> UploadSuccessResponse:
            """模拟完整流程成功。"""

            assert recog_id == "wechat_pay_settlement"
            assert period == "202605"
            assert source_file.name == "source.xlsx"
            return UploadSuccessResponse(
                recog_id=recog_id,
                result_file=str(tmp_path / "result.xlsx"),
                target_table_id="tblyOiWLnWW4QiYO",
                upload_strategy=UploadStrategy.DEFAULT.value,
                row_count=10,
                field_count=8,
            )

    monkeypatch.setattr(run_recog_rollup, "build_service", lambda: FakeService())

    result = runner.invoke(
        run_recog_rollup.app,
        [
            "--recog_id",
            "wechat_pay_settlement",
            "--period",
            "202605",
            "--source_file",
            str(source_file),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["mode"] == "upload"
    assert payload["recog_id"] == "wechat_pay_settlement"

