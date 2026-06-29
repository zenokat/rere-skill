"""项目的核心领域模型。

这些模型描述的是“项目目录、源文件结构、规则配置、试算产物、上传请求”等
跨 CLI、核心层、集成层都要共用的数据结构。
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_LOGICAL_SHEET = "DEFAULT"
PREVIEW_RESULTS_SHEET = "results"
PREVIEW_METADATA_SHEET = "__meta__"


class UploadStrategy(StrEnum):
    """上传冲突处理策略。"""

    DEFAULT = "default"
    APPEND = "append"
    UPSERT = "upsert"


class RunMode(StrEnum):
    """`run_recog_rollup` 的运行模式。"""

    FULL = "full"
    VALIDATE = "validate"
    PREVIEW = "preview"
    UPLOAD = "upload"


class RecognitionProject(BaseModel):
    """已注册的收入确认项目。"""

    recog_id: str
    recog_name: str
    bitable_table_id: str | None = None
    bitable_table_exists: bool = False


class SourceSheetSpec(BaseModel):
    """一个确认项目中某个源 sheet 的读取约定。"""

    recog_id: str
    sheet: str
    category_row: int | None = None
    field_row: int
    last_row: int
    optional: bool = False


class RollupRule(BaseModel):
    """一条汇总规则。"""

    recog_id: str
    bitable_field: str
    type: str
    sheet: str
    category: str | None = None
    field: str
    condition: str | None = None
    optional: bool = False


class PreviewArtifact(BaseModel):
    """`--preview` 生成的结果文件元数据。"""

    recog_id: str
    period: str
    result_file: Path
    row_count: int
    field_count: int
    generated_at: str
    group_fields: list[str] = Field(default_factory=list)


class UploadRequest(BaseModel):
    """上传阶段的输入。"""

    recog_id: str
    result_file: Path
    strategy: UploadStrategy = UploadStrategy.DEFAULT


class UploadOutcome(BaseModel):
    """上传动作的结果。"""

    recog_id: str
    result_file: Path
    target_table_id: str
    strategy: UploadStrategy
    row_count: int
    field_count: int
    status: str = "ok"
    message: str = "Upload completed."


class RuleBundle(BaseModel):
    """同一项目的源 sheet 结构与规则集合。"""

    recog_id: str
    source_sheets: list[SourceSheetSpec] = Field(default_factory=list)
    rollup_rules: list[RollupRule] = Field(default_factory=list)
