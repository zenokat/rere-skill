"""镜像表上传与重复数据处理的最小集成测试。"""

from __future__ import annotations

from pathlib import Path

from core.preview.preview_artifact_writer import PreviewArtifactWriter
from core.upload.upload_stage import UploadStageImpl
from models.cli_results import CliExecutionError
from models.domain import RecognitionProject, UploadStrategy


class _FakeCatalogRepository:
    """提供最小项目目录能力。"""

    def get_project(self, recog_id: str) -> RecognitionProject | None:
        """返回固定项目。"""

        if recog_id != "upload_demo":
            return None
        return RecognitionProject(
            recog_id="upload_demo",
            recog_name="镜像表上传项目",
            bitable_table_id="tbl-upload-demo",
            bitable_table_exists=True,
        )


class _FakeUploadRepository:
    """提供最小镜像表搜索、创建、更新行为。"""

    def __init__(self, existing_records: list[dict[str, object]] | None = None) -> None:
        self._existing_records = existing_records or []
        self.created_records: list[dict[str, object]] = []
        self.updated_records: list[dict[str, object]] = []

    def search_period_records(self, table_id: str, *, period: int | str) -> list[dict[str, object]]:
        """返回固定期间记录。"""

        return list(self._existing_records)

    def create_records(self, table_id: str, records: list[dict[str, object]]) -> dict[str, object]:
        """记录创建请求。"""

        self.created_records.extend(records)
        return {"records": records}

    def update_records(self, table_id: str, records: list[dict[str, object]]) -> dict[str, object]:
        """记录更新请求。"""

        self.updated_records.extend(records)
        return {"records": records}


def _build_preview_file(work_dir: Path) -> Path:
    """构造可被 upload 阶段消费的 preview 结果文件。"""

    writer = PreviewArtifactWriter(output_root=work_dir)
    artifact = writer.write(
        recog_id="upload_demo",
        period="202605",
        records=[
            {
                "期间": "202605",
                "平台ID": "163007972",
                "商品金额": 25455.5,
            }
        ],
        group_fields=["平台ID"],
    )
    return artifact.result_file


def test_upload_mirror_table_rejects_default_conflict() -> None:
    """默认上传策略命中同期间冲突时应直接阻断。"""

    work_dir = Path("tests") / "_tmp_integration" / "upload_conflict"
    work_dir.mkdir(parents=True, exist_ok=True)
    result_file = _build_preview_file(work_dir)

    repository = _FakeUploadRepository(
        existing_records=[
            {
                "record_id": "rec_existing",
                "fields": {"期间": 202605, "平台ID": "163007972", "商品金额": 25455.5},
            }
        ]
    )
    stage = UploadStageImpl(
        catalog_repository=_FakeCatalogRepository(),
        upload_repository=repository,  # type: ignore[arg-type]
        artifact_writer=PreviewArtifactWriter(output_root=work_dir),
    )

    try:
        stage.run(recog_id="upload_demo", result_file=result_file, strategy=UploadStrategy.DEFAULT)
        assert False, "expected CliExecutionError"
    except CliExecutionError as exc:
        assert exc.exit_code == 12
        assert exc.response.stage == "upload"
        assert "same period already exist" in exc.response.message


def test_upload_mirror_table_upsert_updates_conflicting_record() -> None:
    """upsert 应更新命中的联合键记录，而不是重复创建。"""

    work_dir = Path("tests") / "_tmp_integration" / "upload_upsert"
    work_dir.mkdir(parents=True, exist_ok=True)
    result_file = _build_preview_file(work_dir)

    repository = _FakeUploadRepository(
        existing_records=[
            {
                "record_id": "rec_existing",
                "fields": {"期间": 202605, "平台ID": "163007972", "商品金额": 25000.0},
            }
        ]
    )
    stage = UploadStageImpl(
        catalog_repository=_FakeCatalogRepository(),
        upload_repository=repository,  # type: ignore[arg-type]
        artifact_writer=PreviewArtifactWriter(output_root=work_dir),
    )

    response = stage.run(recog_id="upload_demo", result_file=result_file, strategy=UploadStrategy.UPSERT)

    assert response.upload_strategy == "upsert"
    assert repository.created_records == []
    assert repository.updated_records == [
        {
            "record_id": "rec_existing",
            "fields": {"期间": "202605", "平台ID": "163007972", "商品金额": 25455.5},
        }
    ]
