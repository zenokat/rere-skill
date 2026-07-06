@echo off
setlocal

rem Repository-level launcher for project Python CLIs that need stable
rem allow-list matching plus repo-specific runtime setup.

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"
set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Python executable not found: "%PYTHON_EXE%"
    exit /b 1
)

if "%~1"=="" (
    echo Usage:
    echo   .\.codex\scripts\rere.cmd list_recog_items
    echo   .\.codex\scripts\rere.cmd run_recog_rollup [args...]
    echo   .\.codex\scripts\rere.cmd run_skill_eval_batch [args...]
    exit /b 1
)

set "ENTRYPOINT=%~1"
shift

if /I "%ENTRYPOINT%"=="list_recog_items" (
    set "MODULE=cli.list_recog_items"
) else if /I "%ENTRYPOINT%"=="run_recog_rollup" (
    set "MODULE=cli.run_recog_rollup"
) else if /I "%ENTRYPOINT%"=="run_skill_eval_batch" (
    set "MODULE=cli.run_skill_eval_batch"
) else (
    echo Unsupported entrypoint: "%ENTRYPOINT%"
    echo Supported entrypoints: list_recog_items, run_recog_rollup, run_skill_eval_batch
    exit /b 1
)

set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%REPO_ROOT%\eval-harness"

rem Repository `.env` is loaded by the Python entrypoint itself (see
rem `evals.shared.env`), so credentials and sandbox root reach the CLI without
rem fragile batch-side parsing.

rem `%*` always keeps the original arguments in batch files, even after
rem `shift`, so collect the remaining arguments explicitly.
set "CLI_ARGS="
:collect_args
if "%~1"=="" goto run_cli
set CLI_ARGS=%CLI_ARGS% "%~1"
shift
goto collect_args

:run_cli
pushd "%REPO_ROOT%"
"%PYTHON_EXE%" -m %MODULE% %CLI_ARGS%
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
