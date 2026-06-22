"""端到端完整流程的最小冒烟测试。"""

from __future__ import annotations

from pathlib import Path

from core.run_recog_rollup_service import RunRecogRollupService
from models.cli_results import PreviewSuccessResponse, UploadSuccessResponse, ValidateSuccessResponse
from models.domain import RecognitionProject, UploadStrategy


class _FakeCatalogRepository:
    """提供最小项目目录能力。"""

    def get_project(self, recog_id: str) -> RecognitionProject | None:
        """返回固定测试项目。"""

        if recog_id != "wave1_demo":
            return None
        return RecognitionProject(
            recog_id="wave1_demo",
            recog_name="首波冒烟项目",
            bitable_table_id="tbl-wave1",
            bitable_table_exists=True,
        )


class _RecordingValidationStage:
    """记录 validate 调用。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    def run(self, recog_id: str, source_file: Path) -> ValidateSuccessResponse:
        """模拟 validate 成功。"""

        self.calls.append((recog_id, source_file))
        return ValidateSuccessResponse(recog_id=recog_id, sampled_source_file=str(source_file), checks=[], error_count=0)


class _RecordingPreviewStage:
    """记录 preview 调用并产出假结果文件。"""

    def __init__(self, result_file: Path) -> None:
        self.calls: list[tuple[str, str, Path]] = []
        self._result_file = result_file

    def run(self, recog_id: str, period: str, source_file: Path) -> PreviewSuccessResponse:
        """模拟 preview 成功。"""

        self.calls.append((recog_id, period, source_file))
        return PreviewSuccessResponse(
            recog_id=recog_id,
            period=period,
            result_file=str(self._result_file),
            row_count=2,
            field_count=4,
            warnings=[],
        )


class _RecordingUploadStage:
    """记录 upload 调用。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Path, UploadStrategy]] = []

    def run(self, recog_id: str, result_file: Path, strategy: UploadStrategy) -> UploadSuccessResponse:
        """模拟 upload 成功。"""

        self.calls.append((recog_id, result_file, strategy))
        return UploadSuccessResponse(
            recog_id=recog_id,
            result_file=str(result_file),
            target_table_id="tbl-wave1",
            upload_strategy=strategy.value,
            row_count=2,
            field_count=4,
        )


def test_full_flow_wave1_smoke_runs_validate_preview_upload_in_order() -> None:
    """完整流程应按 validate -> preview -> upload 顺序串起。"""

    work_dir = Path("tests") / "_tmp_integration" / "full_flow_wave1"
    work_dir.mkdir(parents=True, exist_ok=True)
    source_file = work_dir / "source.csv"
    result_file = work_dir / "preview.xlsx"
    source_file.write_text("门店,金额\n华北一店,100\n", encoding="utf-8")
    result_file.write_text("placeholder", encoding="utf-8")

    validation_stage = _RecordingValidationStage()
    preview_stage = _RecordingPreviewStage(result_file=result_file)
    upload_stage = _RecordingUploadStage()
    service = RunRecogRollupService(
        catalog_repository=_FakeCatalogRepository(),
        validation_stage=validation_stage,
        preview_stage=preview_stage,
        upload_stage=upload_stage,
    )

    response = service.run_full(
        recog_id="wave1_demo",
        period="202605",
        source_file=source_file,
    )

    assert validation_stage.calls == [("wave1_demo", source_file)]
    assert preview_stage.calls == [("wave1_demo", "202605", source_file)]
    assert upload_stage.calls == [("wave1_demo", result_file, UploadStrategy.DEFAULT)]
    assert response.target_table_id == "tbl-wave1"
