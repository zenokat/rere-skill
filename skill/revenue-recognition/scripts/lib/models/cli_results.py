"""CLI 输出模型与错误模型。

该文件统一定义：
1. CLI 面向 Agent 输出的 JSON 结构
2. 命令退出码
3. 在核心层和 CLI 层之间传递的结构化异常
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from models.domain import RecognitionProject


class ExitCode(IntEnum):
    """CLI 约定的退出码。"""

    OK = 0
    INVALID_ARGUMENT = 2
    VALIDATION_FAILED = 10
    PREVIEW_FAILED = 11
    UPLOAD_CONFLICT = 12
    UPLOAD_REMOTE_FAILED = 13
    CATALOG_FAILED = 14
    LOCAL_FILE_FAILED = 15


class ValidationCheckResult(BaseModel):
    """单条结构检验结果。"""

    check_name: str
    scope: str
    passed: bool
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class PreviewIssue(BaseModel):
    """试算阶段的错误定位信息。"""

    source_file: str
    sheet: str | None = None
    row: int | None = None
    field: str | None = None
    message: str


class CatalogSuccessResponse(BaseModel):
    """`list_recog_items` 成功输出。"""

    status: Literal["ok"] = "ok"
    projects: list[RecognitionProject] = Field(default_factory=list)
    count: int = 0


class ValidateSuccessResponse(BaseModel):
    """`--validate` 成功输出。"""

    status: Literal["ok"] = "ok"
    mode: Literal["validate"] = "validate"
    recog_id: str
    checks: list[ValidationCheckResult] = Field(default_factory=list)
    sampled_source_file: str | None = None
    error_count: int = 0


class PreviewSuccessResponse(BaseModel):
    """`--preview` 成功输出。"""

    status: Literal["ok"] = "ok"
    mode: Literal["preview"] = "preview"
    recog_id: str
    period: str
    result_file: str
    row_count: int
    field_count: int
    warnings: list[str] = Field(default_factory=list)


class UploadSuccessResponse(BaseModel):
    """`--upload` 或默认完整流程成功输出。"""

    status: Literal["ok"] = "ok"
    mode: Literal["upload"] = "upload"
    recog_id: str
    result_file: str
    target_table_id: str
    upload_strategy: str
    row_count: int
    field_count: int


class ErrorResponse(BaseModel):
    """通用错误输出。"""

    status: Literal["error"] = "error"
    stage: str
    message: str
    mode: str | None = None
    recog_id: str | None = None
    retryable: bool = False
    details: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[PreviewIssue] = Field(default_factory=list)


class CliExecutionError(Exception):
    """携带结构化 JSON 输出和退出码的异常。"""

    def __init__(self, exit_code: ExitCode, response: ErrorResponse) -> None:
        """初始化结构化 CLI 异常。"""

        super().__init__(response.message)
        self.exit_code = exit_code
        self.response = response
