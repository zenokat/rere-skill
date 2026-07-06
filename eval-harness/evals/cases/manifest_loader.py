"""Load suite manifests and validate case folders.

The first release deliberately keeps the suite YAML small. It only declares the
suite id, grader ids, and case folder names. This loader then resolves those
folder names to concrete case materials under `cases/<case_id>/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.cases.manifest_models import EvalCase, EvalSuiteManifest
from evals.cases.model_config_file import resolve_model_config_file, validate_model_config_file


class ManifestLoadError(ValueError):
    """Raised when a suite manifest or referenced case folder is invalid."""


def load_suite_manifest(path: Path) -> EvalSuiteManifest:
    """Load a suite manifest from JSON or YAML.

    Args:
        path: Path to `suite.yaml` or an equivalent JSON file.

    Returns:
        A fully resolved `EvalSuiteManifest`.

    Raises:
        ManifestLoadError: If the file is missing, malformed, or references an
            invalid case folder.
    """

    if not path.exists():
        raise ManifestLoadError(f"manifest file does not exist: {path}")
    try:
        raw_text = path.read_text(encoding="utf-8").lstrip("\ufeff")
        payload = _load_mapping(raw_text, path.suffix.lower())
        resolved_payload = _resolve_suite_payload(payload, path.resolve())
        return EvalSuiteManifest.model_validate(resolved_payload)
    except ManifestLoadError:
        raise
    except Exception as exc:
        raise ManifestLoadError(f"manifest parse failed: {path}; {exc}") from exc


def _load_mapping(raw_text: str, suffix: str) -> dict[str, Any]:
    """Parse manifest text into a Python mapping.

    Args:
        raw_text: Raw file contents.
        suffix: Lower-cased file suffix.

    Returns:
        Parsed manifest dictionary.

    Raises:
        ManifestLoadError: If the top-level value is not a mapping.
    """

    if suffix == ".json":
        parsed = json.loads(raw_text)
    else:
        parsed = _load_yaml(raw_text)
    if not isinstance(parsed, dict):
        raise ManifestLoadError("manifest top-level value must be an object")
    return parsed


def _load_yaml(raw_text: str) -> Any:
    """Parse YAML using PyYAML when available, with a small fallback parser.

    Args:
        raw_text: YAML source text.

    Returns:
        Parsed Python object.
    """

    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(raw_text)
    except ModuleNotFoundError:
        return _load_simple_yaml(raw_text)


def _resolve_suite_payload(payload: dict[str, Any], suite_path: Path) -> dict[str, Any]:
    """Resolve raw suite fields into model-ready payload.

    Args:
        payload: Raw manifest dictionary.
        suite_path: Absolute path to the suite manifest.

    Returns:
        Dictionary accepted by `EvalSuiteManifest`.

    Raises:
        ManifestLoadError: If unsupported fields or invalid case folders exist.
    """

    allowed_keys = {"suite_id", "note", "graders", "cases", "input", "skills", "model"}
    extra_keys = sorted(set(payload) - allowed_keys)
    if extra_keys:
        raise ManifestLoadError(f"unsupported suite field(s): {', '.join(extra_keys)}")

    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ManifestLoadError("cases must be a non-empty list of case folder names")
    raw_graders = payload.get("graders")
    if not isinstance(raw_graders, list) or not raw_graders:
        raise ManifestLoadError("graders must be a non-empty list of grader ids")

    cases_root = suite_path.parent / "cases"

    # Parse suite-level shared resources.
    suite_shared_input = _resolve_shared_path(payload, "input", suite_path)
    suite_shared_skills = _resolve_shared_path(payload, "skills", suite_path)
    suite_model = _resolve_suite_model(payload.get("model"), suite_path)

    resolved_cases = [
        _load_case_folder(
            cases_root=cases_root,
            case_id=str(item),
            suite_shared_input=suite_shared_input,
            suite_shared_skills=suite_shared_skills,
        )
        for item in raw_cases
    ]
    return {
        "suite_id": payload.get("suite_id"),
        "model": suite_model,
        "graders": raw_graders,
        "cases": resolved_cases,
        "source_path": suite_path,
        "suite_shared_input": suite_shared_input,
        "suite_shared_skills": suite_shared_skills,
    }


def _resolve_suite_model(raw_model: object, suite_path: Path) -> dict[str, Any] | None:
    """Resolve optional suite-level model configuration.

    Args:
        raw_model: Raw ``model`` value from the suite manifest.
        suite_path: Absolute path to the suite manifest.

    Returns:
        Dictionary accepted by ``SuiteModelConfig``, or None when the suite does
        not request a model.

    Raises:
        ManifestLoadError: If the shape is invalid or ``config_file`` does not
            define the requested model id.
    """

    if raw_model is None:
        return None
    if not isinstance(raw_model, dict):
        raise ManifestLoadError("model must be an object with id and optional config_file")

    extra_keys = sorted(set(raw_model) - {"id", "config_file"})
    if extra_keys:
        raise ManifestLoadError(f"unsupported model field(s): {', '.join(extra_keys)}")

    model_id = str(raw_model.get("id") or "").strip()
    if not model_id:
        raise ManifestLoadError("model.id cannot be empty")

    resolved: dict[str, Any] = {"id": model_id}
    raw_config_file = raw_model.get("config_file")
    if raw_config_file is not None:
        try:
            config_file = resolve_model_config_file(raw_config_file, suite_path=suite_path)
            validate_model_config_file(config_file=config_file, model_id=model_id)
        except ValueError as exc:
            raise ManifestLoadError(str(exc)) from exc
        resolved["config_file"] = config_file
    return resolved


def _resolve_shared_path(payload: dict[str, Any], key: str, suite_path: Path) -> Path | None:
    """Resolve an optional suite-level shared resource path.

    Args:
        payload: Raw manifest dictionary.
        key: Field name (``"input"`` or ``"skills"``).
        suite_path: Absolute path to the suite manifest.

    Returns:
        Absolute Path if the field is present and non-empty; otherwise None.
    """

    raw = payload.get(key)
    if not raw or not isinstance(raw, str):
        return None
    resolved = Path(raw)
    if not resolved.is_absolute():
        resolved = (suite_path.parent / raw).resolve()
    if not resolved.is_dir():
        raise ManifestLoadError(f"suite {key} path does not exist: {raw}")
    return resolved


def _load_case_folder(*, cases_root: Path, case_id: str, suite_shared_input: Path | None = None, suite_shared_skills: Path | None = None) -> EvalCase:
    """Validate and load a single case folder.

    Args:
        cases_root: The `cases/` directory next to `suite.yaml`.
        case_id: Case folder name from the manifest.

    Returns:
        `EvalCase` with resolved paths and instruction text.

    Raises:
        ManifestLoadError: If any required file or directory is missing.
    """

    try:
        case_id = EvalCase.validate_case_id(case_id)
    except ValueError as exc:
        raise ManifestLoadError(f"invalid case id {case_id!r}: {exc}") from exc

    case_dir = (cases_root / case_id).resolve()
    cases_root_resolved = cases_root.resolve()
    if not _is_relative_to(case_dir, cases_root_resolved):
        raise ManifestLoadError(f"case folder escapes suite cases directory: {case_id}")
    if not case_dir.is_dir():
        raise ManifestLoadError(f"case folder does not exist: {case_dir}")

    instruction_path = case_dir / "instruction.md"
    skills_dir = case_dir / "skills"
    input_dir = case_dir / "input"
    missing = [
        str(path.relative_to(case_dir))
        for path in [instruction_path, skills_dir, input_dir]
        if not path.exists()
    ]
    if missing:
        raise ManifestLoadError(f"case {case_id} missing required path(s): {', '.join(missing)}")
    if not instruction_path.is_file():
        raise ManifestLoadError(f"case {case_id} instruction.md must be a file")
    if not skills_dir.is_dir() or not input_dir.is_dir():
        raise ManifestLoadError(f"case {case_id} skills/ and input/ must be directories")

    instruction = instruction_path.read_text(encoding="utf-8").strip()
    if not instruction:
        raise ManifestLoadError(f"case {case_id} instruction.md cannot be empty")

    return EvalCase(
        case_id=case_id,
        case_dir=case_dir,
        instruction_path=instruction_path,
        skills_dir=skills_dir,
        input_dir=input_dir,
        instruction=instruction,
        suite_shared_input=suite_shared_input,
        suite_shared_skills=suite_shared_skills,
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    """Check whether a path is inside another path.

    Args:
        path: Candidate child path.
        parent: Expected parent path.

    Returns:
        True if `path` is relative to `parent`; otherwise False.
    """

    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _load_simple_yaml(raw_text: str) -> Any:
    """Parse the small YAML subset used by first-release examples.

    Args:
        raw_text: YAML source text.

    Returns:
        Parsed Python object.
    """

    lines = _preprocess_yaml(raw_text)
    if not lines:
        return {}
    value, _ = _parse_block(lines, start=0, indent=lines[0][0])
    return value


def _preprocess_yaml(raw_text: str) -> list[tuple[int, str]]:
    """Remove comments and blank lines while keeping indentation.

    Args:
        raw_text: YAML source text.

    Returns:
        List of `(indent, content)` pairs.
    """

    result: list[tuple[int, str]] = []
    for raw_line in raw_text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        result.append((indent, raw_line.strip()))
    return result


def _parse_block(lines: list[tuple[int, str]], start: int, indent: int) -> tuple[Any, int]:
    """Parse a mapping or list block.

    Args:
        lines: Preprocessed YAML lines.
        start: Starting index.
        indent: Current indentation level.

    Returns:
        Parsed value and next unread index.
    """

    if lines[start][1].startswith("- "):
        return _parse_list(lines, start, indent)
    return _parse_mapping(lines, start, indent)


def _parse_mapping(lines: list[tuple[int, str]], start: int, indent: int) -> tuple[dict[str, Any], int]:
    """Parse a YAML mapping block.

    Args:
        lines: Preprocessed YAML lines.
        start: Starting index.
        indent: Current indentation level.

    Returns:
        Parsed mapping and next unread index.
    """

    mapping: dict[str, Any] = {}
    index = start
    while index < len(lines):
        line_indent, content = lines[index]
        if line_indent < indent:
            break
        if line_indent > indent:
            raise ManifestLoadError(f"unexpected YAML indentation: {content}")
        if content.startswith("- "):
            break
        key, value_text = _split_key_value(content)
        if value_text == "":
            if index + 1 >= len(lines) or lines[index + 1][0] <= indent:
                mapping[key] = {}
                index += 1
                continue
            child, next_index = _parse_block(lines, index + 1, lines[index + 1][0])
            mapping[key] = child
            index = next_index
        else:
            mapping[key] = _parse_scalar(value_text)
            index += 1
    return mapping, index


def _parse_list(lines: list[tuple[int, str]], start: int, indent: int) -> tuple[list[Any], int]:
    """Parse a YAML list block.

    Args:
        lines: Preprocessed YAML lines.
        start: Starting index.
        indent: Current indentation level.

    Returns:
        Parsed list and next unread index.
    """

    values: list[Any] = []
    index = start
    while index < len(lines):
        line_indent, content = lines[index]
        if line_indent < indent:
            break
        if line_indent != indent or not content.startswith("- "):
            break
        item_text = content[2:].strip()
        if item_text == "":
            child, next_index = _parse_block(lines, index + 1, lines[index + 1][0])
            values.append(child)
            index = next_index
            continue
        if ":" in item_text and not item_text.startswith(("'", '"')):
            key, value_text = _split_key_value(item_text)
            item: dict[str, Any] = {key: _parse_scalar(value_text) if value_text else {}}
            index += 1
            while index < len(lines) and lines[index][0] > indent:
                child_content = lines[index][1]
                if child_content.startswith("- "):
                    break
                child_key, child_value_text = _split_key_value(child_content)
                item[child_key] = _parse_scalar(child_value_text)
                index += 1
            values.append(item)
        else:
            values.append(_parse_scalar(item_text))
            index += 1
    return values, index


def _split_key_value(content: str) -> tuple[str, str]:
    """Split a `key: value` YAML line.

    Args:
        content: YAML line content.

    Returns:
        Key and value text.
    """

    if ":" not in content:
        raise ManifestLoadError(f"YAML line lacks colon: {content}")
    key, value = content.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> Any:
    """Parse a YAML scalar value.

    Args:
        value: Scalar source text.

    Returns:
        Parsed scalar.
    """

    if value == "":
        return ""
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
