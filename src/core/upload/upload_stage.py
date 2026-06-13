"""上传阶段实现。"""

from __future__ import annotations

from pathlib import Path

from core.catalog.project_catalog_repository import ProjectCatalogRepository
from core.preview.preview_artifact_writer import PreviewArtifactWriter
from core.upload.upload_strategies import build_upsert_key, records_differ
from integrations.feishu_bitable.upload_repository import FeishuUploadRepository
from models.cli_results import CliExecutionError, ErrorResponse, ExitCode, UploadSuccessResponse
from models.domain import UploadStrategy

PERIOD_FIELD_NAME = "期间"


class UploadStageImpl:
    """执行 preview 结果上传。"""

    def __init__(
        self,
        catalog_repository: ProjectCatalogRepository,
        upload_repository: FeishuUploadRepository,
        artifact_writer: PreviewArtifactWriter,
    ) -> None:
        """初始化阶段依赖。"""

        self._catalog_repository = catalog_repository
        self._upload_repository = upload_repository
        self._artifact_writer = artifact_writer

    def run(self, recog_id: str, result_file: Path, strategy: UploadStrategy) -> UploadSuccessResponse:
        """执行上传。"""

        if not result_file.exists():
            raise CliExecutionError(
                exit_code=ExitCode.LOCAL_FILE_FAILED,
                response=ErrorResponse(
                    stage="upload",
                    mode="upload",
                    recog_id=recog_id,
                    message="The result_file does not exist.",
                    retryable=False,
                    details=[{"result_file": str(result_file)}],
                ),
            )

        records, metadata = self._artifact_writer.read(result_file)
        if metadata.get("recog_id") != recog_id:
            raise CliExecutionError(
                exit_code=ExitCode.LOCAL_FILE_FAILED,
                response=ErrorResponse(
                    stage="upload",
                    mode="upload",
                    recog_id=recog_id,
                    message="The result_file does not belong to the requested recog_id.",
                    retryable=False,
                    details=[{"result_file": str(result_file), "artifact_recog_id": metadata.get("recog_id")}],
                ),
            )

        project = self._catalog_repository.get_project(recog_id)
        if project is None or not project.bitable_table_id:
            raise CliExecutionError(
                exit_code=ExitCode.CATALOG_FAILED,
                response=ErrorResponse(
                    stage="upload",
                    mode="upload",
                    recog_id=recog_id,
                    message="Target Bitable table could not be resolved for upload.",
                    retryable=False,
                ),
            )

        period = metadata.get("period")
        group_fields = list(metadata.get("group_fields") or [])
        existing_period_records = self._upload_repository.search_period_records(
            project.bitable_table_id,
            period=period or "",
        )

        if existing_period_records and strategy is UploadStrategy.DEFAULT:
            raise CliExecutionError(
                exit_code=ExitCode.UPLOAD_CONFLICT,
                response=ErrorResponse(
                    stage="upload",
                    mode="upload",
                    recog_id=recog_id,
                    message="Records for the same period already exist in the target table.",
                    retryable=False,
                    details=[
                        {
                            "period": period,
                            "target_table_id": project.bitable_table_id,
                            "existing_count": len(existing_period_records),
                        }
                    ],
                ),
            )

        if strategy is UploadStrategy.APPEND:
            self._upload_repository.create_records(project.bitable_table_id, records)
        elif strategy is UploadStrategy.UPSERT:
            existing_key_to_record = {
                build_upsert_key(record.get("fields", {}), group_fields=group_fields): record
                for record in existing_period_records
            }
            update_payload = []
            create_payload = []
            for record in records:
                upsert_key = build_upsert_key(record, group_fields=group_fields)
                existing_record = existing_key_to_record.get(upsert_key)
                if existing_record:
                    existing_fields = existing_record.get("fields", {})
                    if records_differ(record, existing_fields):
                        update_payload.append({"record_id": existing_record.get("record_id"), "fields": record})
                else:
                    create_payload.append(record)
            self._upload_repository.update_records(project.bitable_table_id, update_payload)
            self._upload_repository.create_records(project.bitable_table_id, create_payload)
        else:
            self._upload_repository.create_records(project.bitable_table_id, records)

        row_count = len(records)
        field_count = len(records[0]) if records else len(group_fields) + 1
        return UploadSuccessResponse(
            recog_id=recog_id,
            result_file=str(result_file),
            target_table_id=project.bitable_table_id,
            upload_strategy=strategy.value,
            row_count=row_count,
            field_count=field_count,
        )
