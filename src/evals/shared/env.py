"""Load repository ``.env`` into the process environment.

The eval harness reads runtime config (sandbox root, credentials) from the
process environment. This loader makes a repository-root ``.env`` file the
single source of truth for that config, so the launcher does not need fragile
platform-specific env-file parsing. It only fills in variables that are not
already set, so explicit process overrides always win.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_repo_dotenv(repo_root: Path | None = None) -> None:
    """Load ``.env`` / ``.env.local`` from the repository root into ``os.environ``.

    Args:
        repo_root: Optional repository root. Defaults to the directory three
            levels above this file (``<repo>/src/evals/shared/env.py``).

    Returns:
        None. Only ``KEY=VALUE`` lines are processed; comments (``#``) and
        blank lines are skipped. Variables already present in the environment
        are never overwritten, so explicit caller overrides take precedence.
    """

    root = (repo_root or _default_repo_root()).resolve()
    for dotenv_path in (root / ".env", root / ".env.local"):
        _apply_dotenv(dotenv_path)


def _default_repo_root() -> Path:
    """Return the repository root inferred from this file's location.

    Args:
        None.

    Returns:
        Repository root path. ``env.py`` lives in ``<repo>/src/evals/shared/``.
    """

    return Path(__file__).resolve().parents[3]


def _apply_dotenv(dotenv_path: Path) -> None:
    """Parse one dotenv file and set missing environment variables.

    Args:
        dotenv_path: Path to a dotenv file.

    Returns:
        None. Supports single- and double-quoted values.
    """

    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
