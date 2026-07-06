"""Tests for batch runner grader dispatch."""

from __future__ import annotations

from pathlib import Path

from evals.cases.manifest_models import EvalCase, EvalSuiteManifest
from evals.runners.background_tasks import PendingBackgroundTasks
from evals.runners.batch_runner import (
    BackgroundOutputWaitResult,
    BatchRunner,
    RuntimeModelRequest,
    _wait_for_background_outputs_if_needed,
)
from evals.shared.output_layout import CaseArtifactLayout
from integrations.codebuddy_cli.headless_runner import HeadlessRunResult


def test_batch_runner_dispatches_preview_matches_baseline(tmp_path: Path, monkeypatch) -> None:
    """Suite grader id ``preview_matches_baseline`` should call the new grader."""

    captured_outputs: list[Path] = []

    def fake_grade_preview_matches_baseline(*, outputs_dir: Path) -> dict[str, object]:
        """Record the dispatched outputs directory and return a passing score.

        Args:
            outputs_dir: Public case outputs directory.

        Returns:
            Synthetic grader result.
        """

        captured_outputs.append(outputs_dir)
        return {
            "id": "preview_matches_baseline",
            "type": "code",
            "score": 1,
            "summary": "matched",
            "evidence": {"checked_dir": "outputs/"},
        }

    monkeypatch.setattr(
        "evals.runners.batch_runner.grade_preview_matches_baseline",
        fake_grade_preview_matches_baseline,
    )
    manifest = EvalSuiteManifest(
        suite_id="suite",
        graders=["preview_matches_baseline"],
        cases=[
            EvalCase(
                case_id="case-a",
                case_dir=tmp_path / "case-a",
                instruction_path=tmp_path / "case-a" / "instruction.md",
                skills_dir=tmp_path / "case-a" / "skills",
                input_dir=tmp_path / "case-a" / "input",
                instruction="run",
            )
        ],
    )
    case_layout = CaseArtifactLayout(
        case_dir=tmp_path / "result" / "case-a",
        result_json=tmp_path / "result" / "case-a" / "result.json",
        session_jsonl=tmp_path / "result" / "case-a" / "session.jsonl",
        outputs_dir=tmp_path / "result" / "case-a" / "outputs",
        sandbox_dir=tmp_path / "runtime" / "workspace",
        codebuddy_config_dir=tmp_path / "runtime" / "codebuddy-state",
    )

    graders = BatchRunner(repo_root=tmp_path)._run_graders(manifest=manifest, case_layout=case_layout)

    assert graders[0]["id"] == "preview_matches_baseline"
    assert captured_outputs == [case_layout.outputs_dir]


def test_batch_runner_dispatches_skill_script_called(tmp_path: Path, monkeypatch) -> None:
    """Suite grader id ``skill_script_called:<name>`` should dispatch to the script grader."""

    captured_calls: list[dict[str, object]] = []

    def fake_grade_skill_script_called(*, session_jsonl: Path, script_name: str) -> dict[str, object]:
        """Record the dispatched arguments and return a passing score.

        Args:
            session_jsonl: Public case session JSONL path.
            script_name: Script name extracted from the grader id.

        Returns:
            Synthetic grader result.
        """

        captured_calls.append({"session_jsonl": session_jsonl, "script_name": script_name})
        return {
            "id": f"skill_script_called:{script_name}",
            "type": "code",
            "score": 1,
            "summary": "called",
            "evidence": {"script_name": script_name, "match_count": 1},
        }

    monkeypatch.setattr(
        "evals.runners.batch_runner.grade_skill_script_called",
        fake_grade_skill_script_called,
    )
    manifest = EvalSuiteManifest(
        suite_id="suite",
        graders=["skill_script_called:list_recog_items"],
        cases=[
            EvalCase(
                case_id="case-a",
                case_dir=tmp_path / "case-a",
                instruction_path=tmp_path / "case-a" / "instruction.md",
                skills_dir=tmp_path / "case-a" / "skills",
                input_dir=tmp_path / "case-a" / "input",
                instruction="run",
            )
        ],
    )
    case_layout = CaseArtifactLayout(
        case_dir=tmp_path / "result" / "case-a",
        result_json=tmp_path / "result" / "case-a" / "result.json",
        session_jsonl=tmp_path / "result" / "case-a" / "session.jsonl",
        outputs_dir=tmp_path / "result" / "case-a" / "outputs",
        sandbox_dir=tmp_path / "runtime" / "workspace",
        codebuddy_config_dir=tmp_path / "runtime" / "codebuddy-state",
    )

    graders = BatchRunner(repo_root=tmp_path)._run_graders(manifest=manifest, case_layout=case_layout)

    assert len(captured_calls) == 1
    assert captured_calls[0]["session_jsonl"] == case_layout.session_jsonl
    assert captured_calls[0]["script_name"] == "list_recog_items"
    assert graders[0]["id"] == "skill_script_called:list_recog_items"
    assert graders[0]["score"] == 1


def test_batch_runner_dispatches_skill_script_args(tmp_path: Path, monkeypatch) -> None:
    """Suite grader id ``skill_script_args:<name>:<arg>`` should dispatch with both parts."""

    captured_calls: list[dict[str, object]] = []

    def fake_grade_skill_script_args(
        *, session_jsonl: Path, script_name: str, arg_pattern: str,
    ) -> dict[str, object]:
        """Record the dispatched arguments and return a passing score.

        Args:
            session_jsonl: Public case session JSONL path.
            script_name: Script name extracted from the grader id.
            arg_pattern: Argument pattern extracted from the grader id.

        Returns:
            Synthetic grader result.
        """

        captured_calls.append({
            "session_jsonl": session_jsonl,
            "script_name": script_name,
            "arg_pattern": arg_pattern,
        })
        return {
            "id": f"skill_script_args:{script_name}:{arg_pattern}",
            "type": "code",
            "score": 1,
            "summary": "args matched",
            "evidence": {"script_name": script_name, "arg_pattern": arg_pattern, "match_count": 1},
        }

    monkeypatch.setattr(
        "evals.runners.batch_runner.grade_skill_script_args",
        fake_grade_skill_script_args,
    )
    manifest = EvalSuiteManifest(
        suite_id="suite",
        graders=["skill_script_args:run_recog_rollup:--validate"],
        cases=[
            EvalCase(
                case_id="case-a",
                case_dir=tmp_path / "case-a",
                instruction_path=tmp_path / "case-a" / "instruction.md",
                skills_dir=tmp_path / "case-a" / "skills",
                input_dir=tmp_path / "case-a" / "input",
                instruction="run",
            )
        ],
    )
    case_layout = CaseArtifactLayout(
        case_dir=tmp_path / "result" / "case-a",
        result_json=tmp_path / "result" / "case-a" / "result.json",
        session_jsonl=tmp_path / "result" / "case-a" / "session.jsonl",
        outputs_dir=tmp_path / "result" / "case-a" / "outputs",
        sandbox_dir=tmp_path / "runtime" / "workspace",
        codebuddy_config_dir=tmp_path / "runtime" / "codebuddy-state",
    )

    graders = BatchRunner(repo_root=tmp_path)._run_graders(manifest=manifest, case_layout=case_layout)

    assert len(captured_calls) == 1
    assert captured_calls[0]["session_jsonl"] == case_layout.session_jsonl
    assert captured_calls[0]["script_name"] == "run_recog_rollup"
    assert captured_calls[0]["arg_pattern"] == "--validate"
    assert graders[0]["id"] == "skill_script_args:run_recog_rollup:--validate"
    assert graders[0]["score"] == 1


def test_case_max_duration_grader_reads_pre_grader_result_json(tmp_path: Path) -> None:
    """``case_max_duration`` should see duration before final result is written."""

    case, manifest, case_layout = _minimal_case_context(tmp_path, graders=["case_max_duration:900"])
    runner_result = _successful_runner_result()

    result = BatchRunner(repo_root=tmp_path)._build_result_payload(
        manifest=manifest,
        case=case,
        case_layout=case_layout,
        runner_result=runner_result,
        duration_ms=1000,
        model_request=RuntimeModelRequest(id=None),
        missing_evidence=[],
        background_wait=BackgroundOutputWaitResult(),
    )

    assert result["status"] == "completed"
    assert result["graders"][0]["id"] == "case_max_duration:900"
    assert result["graders"][0]["score"] == 1
    assert result["verdict"] == "pass"


def test_background_task_timeout_marks_case_failed(tmp_path: Path) -> None:
    """A background timeout should prevent a case from being completed."""

    case, manifest, case_layout = _minimal_case_context(tmp_path, graders=["preview_file_exists"])
    runner_result = _successful_runner_result(final_message="Preview 仍在进行中，等待完成通知。")

    result = BatchRunner(repo_root=tmp_path)._build_result_payload(
        manifest=manifest,
        case=case,
        case_layout=case_layout,
        runner_result=runner_result,
        duration_ms=1000,
        model_request=RuntimeModelRequest(id=None),
        missing_evidence=["background_task_timeout: task_ids=t1; waited_s=0.0"],
        background_wait=BackgroundOutputWaitResult(task_ids=("t1",), timed_out=True),
    )

    assert result["status"] == "failed"
    assert result["score"] == 0
    assert result["evidence"]["background_tasks"]["timed_out"] is True
    assert "background_task_timeout" in result["evidence"]["missing"][0]


def test_background_output_wait_times_out_without_outputs(tmp_path: Path, monkeypatch) -> None:
    """Waiting for a pending task should time out when no output appears."""

    monkeypatch.setenv("RERE_EVAL_BACKGROUND_WAIT_SECONDS", "0")

    result = _wait_for_background_outputs_if_needed(
        output_dir=tmp_path / "output",
        pending_tasks=PendingBackgroundTasks(task_ids=("t1",)),
    )

    assert result.timed_out is True
    assert result.task_ids == ("t1",)


def _minimal_case_context(
    tmp_path: Path,
    *,
    graders: list[str],
) -> tuple[EvalCase, EvalSuiteManifest, CaseArtifactLayout]:
    """Build the minimum objects needed to call the batch payload helper.

    Args:
        tmp_path: Temporary directory supplied by pytest.
        graders: Grader ids for the manifest.

    Returns:
        Tuple of case, manifest, and case layout.
    """

    case_dir = tmp_path / "case-a"
    case_dir.mkdir()
    case = EvalCase(
        case_id="case-a",
        case_dir=case_dir,
        instruction_path=case_dir / "instruction.md",
        skills_dir=case_dir / "skills",
        input_dir=case_dir / "input",
        instruction="run",
    )
    manifest = EvalSuiteManifest(suite_id="suite", graders=graders, cases=[case])
    result_dir = tmp_path / "result" / "case-a"
    result_dir.mkdir(parents=True)
    outputs_dir = result_dir / "outputs"
    outputs_dir.mkdir()
    case_layout = CaseArtifactLayout(
        case_dir=result_dir,
        result_json=result_dir / "result.json",
        session_jsonl=result_dir / "session.jsonl",
        outputs_dir=outputs_dir,
        sandbox_dir=tmp_path / "runtime" / "workspace",
        codebuddy_config_dir=tmp_path / "runtime" / "codebuddy-state",
    )
    return case, manifest, case_layout


def _successful_runner_result(*, final_message: str = "done") -> HeadlessRunResult:
    """Build a minimal successful runner result for payload tests.

    Args:
        final_message: Assistant answer to place in the result.

    Returns:
        Synthetic HeadlessRunResult.
    """

    return HeadlessRunResult(
        exit_code=0,
        stdout="",
        stderr="",
        final_json={"status": "ok", "message": final_message},
        session_id="session-test",
        command_line="codebuddy -p <prompt> --output-format json",
        permission_mode="bypassPermissions",
        final_message=final_message,
    )
