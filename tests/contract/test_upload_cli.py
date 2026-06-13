"""`--upload`、`--append` 与 `--upsert` 的 CLI 契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cli import run_recog_rollup
from models.cli_results import UploadSuccessResponse

runner = CliRunner()


def test_run_recog_rollup_upload_append_dispatches_strategy(monkeypatch, tmp_path: Path) -> None:
    """`--upload --append` 应分发为 append 策略。"""

    result_file = tmp_path / "preview.xlsx"
    result_file.write_text("placeholder", encoding="utf-8")

    class FakeService:
        """用于验证 upload append 分发的假服务。"""

        def run_upload(self, recog_id: str, result_file: Path, strategy) -> UploadSuccessResponse:
            """模拟 upload 成功。"""

            assert recog_id == "wechat_pay_settlement"
            assert result_file.name == "preview.xlsx"
            assert getattr(strategy, "value", str(strategy)) == "append"
            return UploadSuccessResponse(
                recog_id=recog_id,
                result_file=str(result_file),
                target_table_id="tblyOiWLnWW4QiYO",
                upload_strategy="append",
                row_count=5,
                field_count=4,
            )

    monkeypatch.setattr(run_recog_rollup, "build_service", lambda: FakeService())

    result = runner.invoke(
        run_recog_rollup.app,
        [
            "--upload",
            "--append",
            "--recog_id",
            "wechat_pay_settlement",
            "--result_file",
            str(result_file),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "upload"
    assert payload["upload_strategy"] == "append"


def test_run_recog_rollup_upload_upsert_dispatches_strategy(monkeypatch, tmp_path: Path) -> None:
    """`--upload --upsert` 应分发为 upsert 策略。"""

    result_file = tmp_path / "preview.xlsx"
    result_file.write_text("placeholder", encoding="utf-8")

    class FakeService:
        """用于验证 upload upsert 分发的假服务。"""

        def run_upload(self, recog_id: str, result_file: Path, strategy) -> UploadSuccessResponse:
            """模拟 upload 成功。"""

            assert recog_id == "wechat_pay_settlement"
            assert result_file.name == "preview.xlsx"
            assert getattr(strategy, "value", str(strategy)) == "upsert"
            return UploadSuccessResponse(
                recog_id=recog_id,
                result_file=str(result_file),
                target_table_id="tblyOiWLnWW4QiYO",
                upload_strategy="upsert",
                row_count=5,
                field_count=4,
            )

    monkeypatch.setattr(run_recog_rollup, "build_service", lambda: FakeService())

    result = runner.invoke(
        run_recog_rollup.app,
        [
            "--upload",
            "--upsert",
            "--recog_id",
            "wechat_pay_settlement",
            "--result_file",
            str(result_file),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "upload"
    assert payload["upload_strategy"] == "upsert"
