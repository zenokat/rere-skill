"""Binary grader that checks whether a case finished within a time budget.

This grader reads ``result.json`` (which is written by the harness before any
graders run) and compares ``metrics.duration_ms`` against a configurable
threshold.  It is useful for setting iteration-level performance targets: as
rollup scripts get faster, the threshold can be tightened.

Usage in ``suite.yaml``::

    graders:
      - case_max_duration:600   # 600 seconds = 10 minutes
      - case_max_duration:900   # 900 seconds = 15 minutes
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def grade_case_max_duration(*, result_json: Path, max_seconds: int) -> dict[str, Any]:
    """Return score 1 when the case completed within the time budget.

    Args:
        result_json: Path to the case ``result.json`` written by the batch
            runner.  This file is guaranteed to exist when the grader is
            invoked because the runner writes it before dispatching graders.
        max_seconds: Maximum allowed wall-clock duration in seconds.

    Returns:
        Grader result for ``result.json.graders[]``.
    """

    if not result_json.exists():
        return {
            "id": f"case_max_duration:{max_seconds}",
            "type": "code",
            "score": 0,
            "summary": f"result.json 不存在，无法评估用时。",
            "evidence": {"max_seconds": max_seconds, "error": "result_json_not_found"},
        }

    try:
        data = json.loads(result_json.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {
            "id": f"case_max_duration:{max_seconds}",
            "type": "code",
            "score": 0,
            "summary": f"读取 result.json 时出错。",
            "evidence": {
                "max_seconds": max_seconds,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        }

    duration_ms = data.get("metrics", {}).get("duration_ms")
    if duration_ms is None:
        return {
            "id": f"case_max_duration:{max_seconds}",
            "type": "code",
            "score": 0,
            "summary": "result.json 中缺少 metrics.duration_ms 字段。",
            "evidence": {"max_seconds": max_seconds, "error": "duration_ms_missing"},
        }

    duration_s = duration_ms / 1000
    passed = duration_s <= max_seconds

    return {
        "id": f"case_max_duration:{max_seconds}",
        "type": "code",
        "score": 1 if passed else 0,
        "summary": (
            f"Case 用时 {duration_s:.1f}s，"
            f"阈值 {max_seconds}s — "
            f"{'通过' if passed else '超出阈值'}。"
        ),
        "evidence": {
            "duration_ms": duration_ms,
            "duration_s": round(duration_s, 1),
            "max_seconds": max_seconds,
            "margin_s": round(max_seconds - duration_s, 1),
        },
    }
