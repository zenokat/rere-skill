"""Tests for the eval runner environment passed to CodeBuddy.

The harness must provide a predictable child-process environment so real evals
are not affected by machine-local proxy traps or host user state locations.
"""

from pathlib import Path

from evals.shared.windows_paths import as_filesystem_path
from evals.runners.batch_runner import _copy_session_raw, _default_codebuddy_env
from evals.shared.output_layout import CaseArtifactLayout


def test_default_codebuddy_env_isolated_and_proxy_clean(tmp_path):
    """CodeBuddy child process should use isolated state and no broken proxy.

    Args:
        tmp_path: Temporary directory used to build a synthetic case layout.

    Returns:
        None. Assertions verify the environment contract.
    """

    case_layout = CaseArtifactLayout(
        case_dir=tmp_path / "case",
        result_json=tmp_path / "case" / "result.json",
        session_jsonl=tmp_path / "case" / "session.jsonl",
        outputs_dir=tmp_path / "case" / "outputs",
        sandbox_dir=tmp_path / "runtime" / "workspace",
        codebuddy_config_dir=tmp_path / "runtime" / "codebuddy-state",
    )

    env = _default_codebuddy_env(case_layout=case_layout)

    assert env["CODEBUDDY_CONFIG_DIR"] == str(case_layout.codebuddy_config_dir)
    assert env["RERE_OUTPUT_ROOT"] == str(case_layout.sandbox_dir / "output")
    assert case_layout.codebuddy_config_dir.exists()
    assert env["HTTP_PROXY"] == ""
    assert env["HTTPS_PROXY"] == ""
    assert env["http_proxy"] == ""
    assert env["https_proxy"] == ""
    assert env["ALL_PROXY"] == ""
    assert env["all_proxy"] == ""
    assert env["NO_PROXY"] == "localhost,127.0.0.1,::1"
    assert env["no_proxy"] == "localhost,127.0.0.1,::1"


def test_copy_session_raw_reads_windows_long_paths(tmp_path: Path):
    """Raw session copying should read long CodeBuddy paths on Windows.

    Args:
        tmp_path: Temporary directory used to build synthetic input and result
            paths.

    Returns:
        None. Assertions verify that the source session is copied verbatim.
    """

    case_layout = CaseArtifactLayout(
        case_dir=tmp_path / "case",
        result_json=tmp_path / "case" / "result.json",
        session_jsonl=tmp_path / "case" / "session.jsonl",
        outputs_dir=tmp_path / "case" / "outputs",
        sandbox_dir=tmp_path / "runtime" / "workspace",
        codebuddy_config_dir=tmp_path / "runtime" / "codebuddy-state",
    )
    case_layout.case_dir.mkdir(parents=True)
    session_dir = tmp_path / ("codebuddy-state-" + "s" * 70) / "projects" / ("project-" + "p" * 110)
    as_filesystem_path(session_dir).mkdir(parents=True)
    session_file = session_dir / "session-long.jsonl"
    session_text = '{"type":"message","sessionId":"long-copy"}\n'
    as_filesystem_path(session_file).write_text(session_text, encoding="utf-8")

    missing = _copy_session_raw(case_layout=case_layout, session_file=str(session_file))

    assert missing == []
    assert case_layout.session_jsonl.read_text(encoding="utf-8") == session_text
