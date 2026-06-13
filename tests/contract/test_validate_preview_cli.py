"""`--validate` 与 `--preview` 的 CLI 契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cli import run_recog_rollup
from models.cli_results import PreviewSuccessResponse, ValidateSuccessResponse, ValidationCheckResult

runner = CliRunner()


def test_run_recog_rollup_validate_mode_returns_sampled_source_file(monkeypatch, tmp_path: Path) -> None:
    """目录模式下的 validate 应返回被抽检的代表文件。"""

    source_dir = tmp_path / "wechat"
    source_dir.mkdir()

    class FakeService:
        """用于验证 validate 模式分发的假服务。"""

        def run_validate(self, recog_id: str, source_file: Path) -> ValidateSuccessResponse:
            """模拟 validate 成功。"""

            assert recog_id == "wechat_pay_settlement"
            assert source_file.name == "wechat"
            return ValidateSuccessResponse(
                recog_id=recog_id,
                sampled_source_file=str(source_dir / "sample.csv"),
                checks=[
                    ValidationCheckResult(
                        check_name="sheet_exists",
                        scope="sheet:DEFAULT",
                        passed=True,
                        message="Sheet exists.",
                    )
                ],
                error_count=0,
            )

    monkeypatch.setattr(run_recog_rollup, "build_service", lambda: FakeService())

    result = runner.invoke(
        run_recog_rollup.app,
        [
            "--validate",
            "--recog_id",
            "wechat_pay_settlement",
            "--source_file",
            str(source_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "validate"
    assert payload["sampled_source_file"].endswith("sample.csv")


def test_run_recog_rollup_preview_mode_dispatches_directory_source(monkeypatch, tmp_path: Path) -> None:
    """目录模式下的 preview 应保留目录输入，并返回结果文件概览。"""

    source_dir = tmp_path / "wechat"
    source_dir.mkdir()

    class FakeService:
        """用于验证 preview 模式分发的假服务。"""

        def run_preview(self, recog_id: str, period: str, source_file: Path) -> PreviewSuccessResponse:
            """模拟 preview 成功。"""

            assert recog_id == "wechat_pay_settlement"
            assert period == "202605"
            assert source_file.name == "wechat"
            return PreviewSuccessResponse(
                recog_id=recog_id,
                period=period,
                result_file=str(tmp_path / "preview.xlsx"),
                row_count=12,
                field_count=9,
                warnings=[],
            )

    monkeypatch.setattr(run_recog_rollup, "build_service", lambda: FakeService())

    result = runner.invoke(
        run_recog_rollup.app,
        [
            "--preview",
            "--recog_id",
            "wechat_pay_settlement",
            "--period",
            "202605",
            "--source_file",
            str(source_dir),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "preview"
    assert payload["row_count"] == 12
    assert payload["field_count"] == 9

