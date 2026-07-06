"""`run_recog_rollup` CLI 入口。"""

from __future__ import annotations

from pathlib import Path

import typer

from cli.formatters import exit_with_json, handle_cli_execution_error
from core.catalog.project_catalog_repository import FeishuProjectCatalogRepository
from core.preview.preview_artifact_writer import PreviewArtifactWriter
from core.preview.preview_stage import PreviewStageImpl
from core.rules.rule_repository import FeishuRuleRepository
from core.run_recog_rollup_service import RunRecogRollupService
from core.upload.upload_stage import UploadStageImpl
from core.validation.validate_stage import ValidateStageImpl
from integrations.feishu_bitable.client import BitableApiClient, TenantAccessTokenProvider
from integrations.feishu_bitable.upload_repository import FeishuUploadRepository
from models.cli_results import CliExecutionError, ErrorResponse, ExitCode
from models.domain import RunMode, UploadStrategy
from utils.settings import load_settings

app = typer.Typer(add_completion=False, help="执行收入确认阶段一的结构检验、试算与上传。")


def build_service() -> RunRecogRollupService:
    """构造真实运行时依赖。"""

    settings = load_settings()
    token_provider = TenantAccessTokenProvider(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        timeout_seconds=settings.request_timeout_seconds,
        trust_env=settings.trust_env_proxies,
    )
    client = BitableApiClient(
        token_provider=token_provider,
        timeout_seconds=settings.request_timeout_seconds,
        trust_env=settings.trust_env_proxies,
    )
    catalog_repository = FeishuProjectCatalogRepository(client=client, settings=settings)
    rule_repository = FeishuRuleRepository(client=client, settings=settings)
    artifact_writer = PreviewArtifactWriter(output_root=settings.output_root)
    upload_repository = FeishuUploadRepository(client=client, result_bitable_app_token=settings.result_bitable_app_token)
    return RunRecogRollupService(
        catalog_repository=catalog_repository,
        validation_stage=ValidateStageImpl(
            catalog_repository=catalog_repository,
            rule_repository=rule_repository,
            bitable_client=client,
            settings=settings,
        ),
        preview_stage=PreviewStageImpl(
            rule_repository=rule_repository,
            artifact_writer=artifact_writer,
        ),
        upload_stage=UploadStageImpl(
            catalog_repository=catalog_repository,
            upload_repository=upload_repository,
            artifact_writer=artifact_writer,
        ),
    )


def _resolve_mode(validate: bool, preview: bool, upload: bool) -> RunMode:
    """解析本次调用的运行模式。"""

    enabled_count = sum([validate, preview, upload])
    if enabled_count > 1:
        raise CliExecutionError(
            exit_code=ExitCode.INVALID_ARGUMENT,
            response=ErrorResponse(
                stage="arguments",
                message="--validate, --preview, and --upload are mutually exclusive.",
                retryable=False,
            ),
        )
    if validate:
        return RunMode.VALIDATE
    if preview:
        return RunMode.PREVIEW
    if upload:
        return RunMode.UPLOAD
    return RunMode.FULL


def _resolve_upload_strategy(upload: bool, append: bool, upsert: bool) -> UploadStrategy:
    """解析上传冲突策略。"""

    if append and upsert:
        raise CliExecutionError(
            exit_code=ExitCode.INVALID_ARGUMENT,
            response=ErrorResponse(
                stage="arguments",
                message="--append and --upsert are mutually exclusive.",
                retryable=False,
            ),
        )
    if (append or upsert) and not upload:
        raise CliExecutionError(
            exit_code=ExitCode.INVALID_ARGUMENT,
            response=ErrorResponse(
                stage="arguments",
                message="--append and --upsert can only be used together with --upload.",
                retryable=False,
            ),
        )
    if append:
        return UploadStrategy.APPEND
    if upsert:
        return UploadStrategy.UPSERT
    return UploadStrategy.DEFAULT


def _require_option(value: str | Path | None, option_name: str, mode: RunMode) -> None:
    """确保模式所需参数已经提供。"""

    if value is not None:
        return
    raise CliExecutionError(
        exit_code=ExitCode.INVALID_ARGUMENT,
        response=ErrorResponse(
            stage="arguments",
            mode=mode.value,
            message=f"{option_name} is required in {mode.value} mode.",
            retryable=False,
        ),
    )


@app.command()
def run(
    validate: bool = typer.Option(False, "--validate", help="仅执行结构检验。"),
    preview: bool = typer.Option(False, "--preview", help="仅执行试算。"),
    upload: bool = typer.Option(False, "--upload", help="仅执行上传。"),
    append: bool = typer.Option(False, "--append", help="上传时采用追加策略。"),
    upsert: bool = typer.Option(False, "--upsert", help="上传时采用覆盖策略。"),
    recog_id: str | None = typer.Option(None, "--recog_id", help="确认项目主键。"),
    period: str | None = typer.Option(None, "--period", help="会计期间，格式 YYYYMM。"),
    source_file: Path | None = typer.Option(None, "--source_file", help="源文件路径。"),
    result_file: Path | None = typer.Option(None, "--result_file", help="preview 结果文件路径。"),
) -> None:
    """执行完整流程或单一环节。"""

    try:
        mode = _resolve_mode(validate=validate, preview=preview, upload=upload)
        strategy = _resolve_upload_strategy(upload=upload, append=append, upsert=upsert)
        _require_option(recog_id, "--recog_id", mode)

        service = build_service()
        if mode is RunMode.FULL:
            _require_option(period, "--period", mode)
            _require_option(source_file, "--source_file", mode)
            response = service.run_full(recog_id=recog_id or "", period=period or "", source_file=source_file or Path())
        elif mode is RunMode.VALIDATE:
            _require_option(source_file, "--source_file", mode)
            response = service.run_validate(recog_id=recog_id or "", source_file=source_file or Path())
        elif mode is RunMode.PREVIEW:
            _require_option(period, "--period", mode)
            _require_option(source_file, "--source_file", mode)
            response = service.run_preview(
                recog_id=recog_id or "",
                period=period or "",
                source_file=source_file or Path(),
                result_file=result_file,
            )
        else:
            _require_option(result_file, "--result_file", mode)
            response = service.run_upload(
                recog_id=recog_id or "",
                result_file=result_file or Path(),
                strategy=strategy,
            )

        exit_with_json(response)
    except Exception as exc:
        if isinstance(exc, typer.Exit):
            raise
        if hasattr(exc, "response") and hasattr(exc, "exit_code"):
            handle_cli_execution_error(exc)  # type: ignore[arg-type]
            return
        raise


def main() -> None:
    """命令行入口函数。"""

    app()


if __name__ == "__main__":
    main()
