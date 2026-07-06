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
