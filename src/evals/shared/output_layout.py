"""Output layout for the minimal eval result bundle.

Public result files are limited to `batch.json`, one `result.json` per case,
one `session.jsonl` per case, and one `outputs/` directory per case. Runtime
sandboxes are internal and are removed after evidence collection.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path


def _runtime_sandbox_root(batch_id: str) -> Path:
    """Return the external runtime sandbox root for one batch.

    Args:
        batch_id: Current batch id.

    Returns:
        Batch-specific runtime sandbox directory outside the public result
        bundle. `RERE_EVAL_SANDBOX_ROOT` can override the base directory.
    """

    configured_root = os.getenv("RERE_EVAL_SANDBOX_ROOT")
    base_root = Path(configured_root) if configured_root else Path(tempfile.gettempdir()) / "rere-agent-eval-sandboxes"
    return base_root.resolve() / batch_id


def _short_internal_name(value: str) -> str:
    """Return a short, stable directory name for internal runtime paths.

    Args:
        value: Human-readable id such as a case id.

    Returns:
        A filesystem-safe name with a short hash suffix. Public result paths keep
        the full case id; only hidden runtime directories use this shortened name
        to avoid Windows MAX_PATH failures.
    """

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    prefix = (cleaned or "case")[:24]
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{digest}"


@dataclass(frozen=True)
class CaseArtifactLayout:
    """Paths for one case's public result files and internal sandbox.

    Args:
        case_dir: Public case result directory.
        result_json: Public single-case result file.
        session_jsonl: Public raw CodeBuddy session JSONL file (the single
            source of truth for the agent trajectory).
        outputs_dir: Public business outputs directory.
        sandbox_dir: Internal disposable runtime sandbox.
        codebuddy_config_dir: Internal CodeBuddy state directory outside the case workspace.

    Returns:
        Immutable path bundle for one case.
    """

    case_dir: Path
    result_json: Path
    session_jsonl: Path
    outputs_dir: Path
    sandbox_dir: Path
    codebuddy_config_dir: Path


@dataclass(frozen=True)
class BatchArtifactLayout:
    """Paths for one batch.

    Args:
        batch_dir: Public batch result directory.
        cases_dir: Public cases directory.
        sandboxes_dir: Internal disposable sandbox root outside the public result bundle.
        batch_json: Public batch result file.

    Returns:
        Immutable path bundle for one batch.
    """

    batch_dir: Path
    cases_dir: Path
    sandboxes_dir: Path
    batch_json: Path


class OutputLayout:
    """Generate paths from the output root and batch id.

    Args:
        output_root: Evaluator-provided output root.
        batch_id: Current batch id.

    Returns:
        OutputLayout instance.
    """

    def __init__(self, output_root: Path, batch_id: str) -> None:
        """Initialize the layout.

        Args:
            output_root: Evaluator-provided output root.
            batch_id: Current batch id.

        Returns:
            None.
        """

        self.output_root = output_root
        self.batch_id = batch_id
        batch_dir = output_root / batch_id
        self.batch = BatchArtifactLayout(
            batch_dir=batch_dir,
            cases_dir=batch_dir / "cases",
            sandboxes_dir=_runtime_sandbox_root(batch_id),
            batch_json=batch_dir / "batch.json",
        )

    def ensure_batch_dirs(self) -> None:
        """Create batch-level directories.

        Args:
            None.

        Returns:
            None.
        """

        self.batch.cases_dir.mkdir(parents=True, exist_ok=True)
        self.batch.sandboxes_dir.mkdir(parents=True, exist_ok=True)

    def case_layout(self, case_id: str) -> CaseArtifactLayout:
        """Return paths for one case.

        Args:
            case_id: Stable case id.

        Returns:
            CaseArtifactLayout for the case.
        """

        case_dir = self.batch.cases_dir / case_id
        internal_name = _short_internal_name(case_id)
        return CaseArtifactLayout(
            case_dir=case_dir,
            result_json=case_dir / "result.json",
            session_jsonl=case_dir / "session.jsonl",
            outputs_dir=case_dir / "outputs",
            sandbox_dir=self.batch.sandboxes_dir / "workspaces" / internal_name,
            codebuddy_config_dir=self.batch.sandboxes_dir / "codebuddy-state" / internal_name,
        )

    def ensure_case_dirs(self, case_id: str) -> CaseArtifactLayout:
        """Create public case directories and the internal sandbox root.

        Args:
            case_id: Stable case id.

        Returns:
            Created CaseArtifactLayout.
        """

        layout = self.case_layout(case_id)
        layout.case_dir.mkdir(parents=True, exist_ok=True)
        layout.outputs_dir.mkdir(parents=True, exist_ok=True)
        layout.sandbox_dir.mkdir(parents=True, exist_ok=True)
        return layout

