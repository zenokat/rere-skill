"""Windows filesystem path helpers for the eval harness.

CodeBuddy stores project history under
``<config>/projects/<normalized-workspace-path>/<session>.jsonl``. On Windows,
that directory can cross the legacy ``MAX_PATH`` boundary even when the
workspace itself is reasonably short. These helpers keep public/logical paths
readable while using the extended-length path form for direct filesystem calls.
"""

from __future__ import annotations

import os
from pathlib import Path


def as_filesystem_path(path: Path) -> Path:
    """Return a path suitable for direct filesystem APIs.

    Args:
        path: Logical path used by harness code.

    Returns:
        On non-Windows platforms, the input path unchanged. On Windows, an
        absolute path with the ``\\?\\`` extended-length prefix, so operations
        such as ``exists()``, ``glob()``, ``stat()`` and ``read_bytes()`` keep
        working when the full path is longer than 260 characters.
    """

    if os.name != "nt":
        return path

    raw_path = str(path)
    if raw_path.startswith("\\\\?\\"):
        return path

    absolute_path = path if path.is_absolute() else path.resolve()
    absolute_text = str(absolute_path)
    if absolute_text.startswith("\\\\?\\"):
        return Path(absolute_text)
    if absolute_text.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute_text.lstrip("\\"))
    return Path("\\\\?\\" + absolute_text)


def without_windows_long_path_prefix(path: Path) -> Path:
    """Return a readable logical path without the Windows long-path prefix.

    Args:
        path: Path returned by filesystem enumeration or direct access.

    Returns:
        Path without ``\\?\\`` / ``\\?\\UNC\\`` prefixes. This keeps evidence
        and result payloads readable while callers can still convert the path
        back with ``as_filesystem_path`` before touching the filesystem.
    """

    text = str(path)
    if text.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + text[len("\\\\?\\UNC\\") :])
    if text.startswith("\\\\?\\"):
        return Path(text[len("\\\\?\\") :])
    return path
