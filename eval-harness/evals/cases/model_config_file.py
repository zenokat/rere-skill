"""Utilities for suite-level CodeBuddy model configuration files.

Eval suites may point to a local ``models.json`` so CodeBuddy can run a
requested model through the evaluator's own API credentials while the case
still executes inside an isolated CodeBuddy config directory. This module keeps
that handling small and explicit: resolve the path, verify the requested model
exists, copy the file into the runtime config directory, and expose only a
fingerprint for result evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


_ENV_REF_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|%([A-Za-z_][A-Za-z0-9_]*)%")


def resolve_model_config_file(raw_path: object, *, suite_path: Path) -> Path:
    """Resolve a suite ``model.config_file`` value to an existing file.

    Args:
        raw_path: Raw YAML value from ``model.config_file``.
        suite_path: Absolute path to the suite manifest. Relative config paths
            are resolved against this file's parent directory.

    Returns:
        Absolute path to the model configuration file.

    Raises:
        ValueError: If the path is empty, contains unresolved environment
            variables, or does not point to a file.
    """

    text = str(raw_path or "").strip()
    if not text:
        raise ValueError("model.config_file cannot be empty")

    expanded = os.path.expandvars(text)
    missing_refs = _unresolved_env_refs(expanded)
    if missing_refs:
        names = ", ".join(sorted(missing_refs))
        raise ValueError(f"model.config_file references missing environment variable(s): {names}")

    path = Path(expanded).expanduser()
    if not path.is_absolute():
        path = (suite_path.parent / path).resolve()
    else:
        path = path.resolve()
    if not path.is_file():
        raise ValueError(f"model.config_file does not exist or is not a file: {text}")
    return path


def validate_model_config_file(*, config_file: Path, model_id: str) -> None:
    """Verify that a ``models.json`` file defines the requested model id.

    Args:
        config_file: Resolved CodeBuddy ``models.json`` path.
        model_id: Suite-requested model id.

    Returns:
        None.

    Raises:
        ValueError: If the file cannot be parsed, has an unsupported shape, or
            does not define / expose the requested model id.
    """

    payload = _load_json(config_file)
    model_ids = _extract_model_ids(payload)
    if model_id not in model_ids:
        raise ValueError(f"model.config_file does not define model id: {model_id}")

    available = _extract_available_models(payload)
    if available and model_id not in available:
        raise ValueError(f"model.config_file availableModels does not include model id: {model_id}")


def copy_model_config_file(*, source: Path, destination_dir: Path) -> Path:
    """Copy a suite model config into CodeBuddy's isolated config directory.

    Args:
        source: Resolved suite ``models.json`` file.
        destination_dir: Runtime CodeBuddy config directory for one case.

    Returns:
        Path to the copied ``models.json`` file.
    """

    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / "models.json"
    destination.write_bytes(source.read_bytes())
    return destination


def fingerprint_model_config_file(config_file: Path) -> str:
    """Return a short, non-secret fingerprint for a model config file.

    Args:
        config_file: Resolved ``models.json`` path.

    Returns:
        A stable ``sha256:<prefix>`` fingerprint. The result bundle records this
        instead of the file contents or API key.
    """

    digest = hashlib.sha256(config_file.read_bytes()).hexdigest()
    return f"sha256:{digest[:16]}"


def _unresolved_env_refs(text: str) -> set[str]:
    """Find unresolved ``${VAR}`` or ``%VAR%`` references in a path string.

    Args:
        text: Expanded path text.

    Returns:
        Set of environment variable names still present in the text.
    """

    names: set[str] = set()
    for match in _ENV_REF_PATTERN.finditer(text):
        names.add(next(group for group in match.groups() if group))
    return names


def _load_json(config_file: Path) -> Any:
    """Load a JSON configuration file.

    Args:
        config_file: Path to the JSON file.

    Returns:
        Parsed JSON payload.

    Raises:
        ValueError: If the file is not valid JSON.
    """

    try:
        return json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"model.config_file is not valid JSON: {config_file}") from exc


def _extract_model_ids(payload: Any) -> set[str]:
    """Extract model ids from CodeBuddy's supported ``models.json`` shapes.

    Args:
        payload: Parsed JSON payload. CodeBuddy supports either a top-level
            array or an object with a ``models`` array.

    Returns:
        Set of model ids defined by the file.

    Raises:
        ValueError: If the payload does not contain a models array.
    """

    models = payload if isinstance(payload, list) else payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise ValueError("model.config_file must be a models array or contain a models array")

    model_ids: set[str] = set()
    for item in models:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id.strip():
            model_ids.add(model_id.strip())
    return model_ids


def _extract_available_models(payload: Any) -> set[str]:
    """Extract ``availableModels`` when present.

    Args:
        payload: Parsed JSON payload.

    Returns:
        Set of available model ids. Empty means the file does not restrict the
        list or uses the top-level array shorthand.
    """

    if not isinstance(payload, dict):
        return set()
    available = payload.get("availableModels")
    if not isinstance(available, list):
        return set()
    return {item.strip() for item in available if isinstance(item, str) and item.strip()}
