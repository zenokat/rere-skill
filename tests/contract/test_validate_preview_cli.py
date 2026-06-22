"""`--validate` 与 `--preview` 的 CLI 契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cli import run_recog_rollup
from models.cli_results import (
    CliExecutionError,
    ErrorResponse,
    PreviewSuccessResponse,
    ValidateSuccessResponse,
    ValidationCheckResult,
)
from models.domain import RunMode

runner = CliRunner()


def _make_test_dir(name: str) -> Path:
    """为契约测试创建仓库内可写的临时目录。"""

    target_dir = Path("tests") / "_tmp_contract" / name
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir.resolve()


def test_run_recog_rollup_validate_mode_returns_sampled_source_file(monkeypatch) -> None:
    """目录模式下的 validate 应返回被抽检的代表文件。"""

    source_dir = _make_test_dir("validate_sample")
    (source_dir / "placeholder.txt").write_text("placeholder", encoding="utf-8")

    class FakeService:
        """用于验证 validate 模式分发的假服务。"""

        def run_validate(self, recog_id: str, source_file: Path) -> ValidateSuccessResponse:
            """模拟 validate 成功。"""

            assert recog_id == "wechat_pay_settlement"
            assert source_file.name == source_dir.name
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


def test_run_recog_rollup_preview_mode_dispatches_directory_source(monkeypatch) -> None:
    """目录模式下的 preview 应保留目录输入，并返回结果文件概览。"""

    source_dir = _make_test_dir("preview_directory")
    (source_dir / "placeholder.txt").write_text("placeholder", encoding="utf-8")

    class FakeService:
        """用于验证 preview 模式分发的假服务。"""

        def run_preview(self, recog_id: str, period: str, source_file: Path) -> PreviewSuccessResponse:
            """模拟 preview 成功。"""

            assert recog_id == "wechat_pay_settlement"
            assert period == "202605"
            assert source_file.name == source_dir.name
            return PreviewSuccessResponse(
                recog_id=recog_id,
                period=period,
                result_file=str(source_dir / "preview.xlsx"),
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


def test_run_recog_rollup_validate_mode_reports_condition_boundary_guidance(monkeypatch) -> None:
    """condition 越界时，CLI 应返回稳定错误码与联系开发者指引。"""

    source_dir = _make_test_dir("validate_boundary")
    (source_dir / "source.csv").write_text("placeholder", encoding="utf-8")

    class FakeService:
        """用于模拟 validate 阶段命中 condition 能力边界。"""

        def run_validate(self, recog_id: str, source_file: Path) -> ValidateSuccessResponse:
            """直接抛出结构化 validate 错误。"""

            raise CliExecutionError(
                exit_code=10,
                response=ErrorResponse(
                    stage="validate",
                    mode=RunMode.VALIDATE.value,
                    recog_id=recog_id,
                    message="Validation failed.",
                    retryable=False,
                    details=[
                        {
                            "sampled_source_file": str(source_file / "sample.csv"),
                            "checks": [
                                {
                                    "check_name": "condition_valid",
                                    "scope": "rule:已结算金额",
                                    "passed": False,
                                    "message": "condition 调用了不被允许的函数。",
                                    "details": [
                                        {
                                            "code": "condition_function_not_allowed",
                                            "agent_action": "contact_developer_for_condition_extension",
                                            "guidance": "当前 condition 超出首版能力边界，请联系开发者扩展内置 helper 或 condition 能力。",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                ),
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

    assert result.exit_code == 10
    payload = json.loads(result.stdout)
    assert payload["stage"] == "validate"
    check = payload["details"][0]["checks"][0]
    assert check["details"][0]["code"] == "condition_function_not_allowed"
    assert check["details"][0]["agent_action"] == "contact_developer_for_condition_extension"
    assert "联系开发者扩展" in check["details"][0]["guidance"]
