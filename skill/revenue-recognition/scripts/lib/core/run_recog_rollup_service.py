"""`run_recog_rollup` 的编排服务。

当前文件的职责是：
1. 统一校验模式组合与最基本的项目可用性
2. 负责完整流程的顺序编排和失败即停止
3. 将具体的“结构检验 / 试算 / 上传”实现解耦成可替换 stage
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from core.catalog.project_catalog_repository import ProjectCatalogRepository
from models.cli_results import (
    CliExecutionError,
    ErrorResponse,
    ExitCode,
    PreviewSuccessResponse,
    UploadSuccessResponse,
    ValidateSuccessResponse,
)
from models.domain import RecognitionProject, UploadStrategy


class ValidationStage(Protocol):
    """结构检验阶段协议。"""

    def run(self, recog_id: str, source_file: Path, *, project: RecognitionProject | None = None) -> ValidateSuccessResponse:
        """执行结构检验。"""


class PreviewStage(Protocol):
    """试算阶段协议。"""

    def run(self, recog_id: str, period: str, source_file: Path) -> PreviewSuccessResponse:
        """执行试算。"""


class UploadStage(Protocol):
    """上传阶段协议。"""

    def run(self, recog_id: str, result_file: Path, strategy: UploadStrategy) -> UploadSuccessResponse:
        """执行上传。"""


class UnsupportedStageRunner:
    """在阶段实现尚未落地前提供安全失败。"""

    def __init__(self, stage_name: str) -> None:
        """初始化占位阶段。"""

        self._stage_name = stage_name

    def run(self, *args: object, **kwargs: object) -> ValidateSuccessResponse | PreviewSuccessResponse | UploadSuccessResponse:
        """输出结构化的“尚未实现”错误。"""

        raise CliExecutionError(
            exit_code=ExitCode.INVALID_ARGUMENT,
            response=ErrorResponse(
                stage=self._stage_name,
                mode=self._stage_name,
                message=f"The {self._stage_name} stage is not implemented yet.",
                retryable=False,
            ),
        )


class RunRecogRollupService:
    """完整流程与单环节流程的统一编排服务。"""

    def __init__(
        self,
        catalog_repository: ProjectCatalogRepository,
        validation_stage: ValidationStage,
        preview_stage: PreviewStage,
        upload_stage: UploadStage,
    ) -> None:
        """初始化编排服务。"""

        self._catalog_repository = catalog_repository
        self._validation_stage = validation_stage
        self._preview_stage = preview_stage
        self._upload_stage = upload_stage

    def run_full(self, recog_id: str, period: str, source_file: Path) -> UploadSuccessResponse:
        """按固定顺序执行完整流程。"""

        project = self._require_project(recog_id)
        self._require_target_table(project)
        self._validation_stage.run(recog_id=recog_id, source_file=source_file, project=project)
        preview_response = self._preview_stage.run(recog_id=recog_id, period=period, source_file=source_file)
        return self._upload_stage.run(
            recog_id=recog_id,
            result_file=Path(preview_response.result_file),
            strategy=UploadStrategy.DEFAULT,
        )

    def run_validate(self, recog_id: str, source_file: Path) -> ValidateSuccessResponse:
        """只执行结构检验。"""

        project = self._require_project(recog_id)
        self._require_target_table(project)
        return self._validation_stage.run(recog_id=recog_id, source_file=source_file, project=project)

    def run_preview(self, recog_id: str, period: str, source_file: Path) -> PreviewSuccessResponse:
        """只执行试算。"""

        self._require_project(recog_id)
        return self._preview_stage.run(recog_id=recog_id, period=period, source_file=source_file)

    def run_upload(self, recog_id: str, result_file: Path, strategy: UploadStrategy) -> UploadSuccessResponse:
        """只执行上传。"""

        project = self._require_project(recog_id)
        self._require_target_table(project)
        return self._upload_stage.run(recog_id=recog_id, result_file=result_file, strategy=strategy)

    def _require_project(self, recog_id: str) -> RecognitionProject:
        """确保目标项目存在。"""

        project = self._catalog_repository.get_project(recog_id)
        if project is None:
            raise CliExecutionError(
                exit_code=ExitCode.CATALOG_FAILED,
                response=ErrorResponse(
                    stage="catalog",
                    message="Recognition project was not found in the catalog.",
                    recog_id=recog_id,
                    retryable=False,
                    details=[{"recog_id": recog_id}],
                ),
            )
        return project

    def _require_target_table(self, project: RecognitionProject) -> None:
        """确保目标飞书数据表可用。"""

        if project.bitable_table_exists:
            return
        raise CliExecutionError(
            exit_code=ExitCode.CATALOG_FAILED,
            response=ErrorResponse(
                stage="catalog",
                message="Target Bitable table is missing or inaccessible.",
                recog_id=project.recog_id,
                retryable=False,
                details=[
                    {
                        "recog_id": project.recog_id,
                        "bitable_table_id": project.bitable_table_id,
                        "bitable_table_exists": project.bitable_table_exists,
                    }
                ],
            ),
        )

