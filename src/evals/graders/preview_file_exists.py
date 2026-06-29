"""Binary grader that checks for a preview file in case `outputs/`.

The first release has no hidden default grader. This code grader is executed
only when the suite YAML declares `preview_file_exists`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def grade_preview_file_exists(*, outputs_dir: Path) -> dict[str, Any]:
    """Return score 1 when a preview-like Excel file exists in `outputs/`.

    Args:
        outputs_dir: Public case `outputs/` directory.

    Returns:
        Grader result for `result.json.graders[]`.
    """

    preview_file = _find_preview_file(outputs_dir)
    if preview_file is None:
        return {
            "id": "preview_file_exists",
            "type": "code",
            "score": 0,
            "summary": "未在 outputs/ 中找到 preview 文件。",
            "evidence": {"checked_dir": "outputs/"},
        }

    return {
        "id": "preview_file_exists",
        "type": "code",
        "score": 1,
        "summary": "已在 outputs/ 中找到本次 preview 文件。",
        "evidence": {
            "file": _outputs_relative_path(preview_file, outputs_dir),
            "size_bytes": preview_file.stat().st_size,
            "sha256": _sha256_file(preview_file),
        },
    }


def _find_preview_file(outputs_dir: Path) -> Path | None:
    """Find the first Excel preview artifact under `outputs/`.

    Args:
        outputs_dir: Public case `outputs/` directory.

    Returns:
        Matching file path, or None.
    """

    if not outputs_dir.exists():
        return None
    candidates = [
        path
        for path in sorted(outputs_dir.rglob("*"), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file() and path.suffix.lower() in {".xlsx", ".xls", ".csv", ".json"}
    ]
    if not candidates:
        return None
    preview_named = [path for path in candidates if "preview" in path.name.lower() or "预览" in path.name]
    return preview_named[0] if preview_named else candidates[0]


def _outputs_relative_path(path: Path, outputs_dir: Path) -> str:
    """Format an evidence path relative to the case result directory.

    Args:
        path: Matched output file.
        outputs_dir: Public `outputs/` directory.

    Returns:
        POSIX-style path such as `outputs/file.xlsx`.
    """

    return "outputs/" + path.relative_to(outputs_dir).as_posix()


def _sha256_file(path: Path) -> str:
    """Calculate the SHA-256 hash for a file.

    Args:
        path: File path.

    Returns:
        Hex digest.
    """

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
