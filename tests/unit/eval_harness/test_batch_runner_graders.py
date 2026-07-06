"""Tests for batch runner grader dispatch."""

from __future__ import annotations

from pathlib import Path

from evals.cases.manifest_models import EvalCase, EvalSuiteManifest
from evals.runners.batch_runner import BatchRunner
from evals.shared.output_layout import CaseArtifactLayout


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
