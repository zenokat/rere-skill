"""Secret redaction utilities for eval harness artifacts.

The harness records CodeBuddy session events as evidence.  Those events may
contain tool output from files such as ``.env`` or ``models.json``.  This module
keeps the evidence structure intact while replacing sensitive values with stable
placeholders before the result bundle is written to disk.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping


REDACTED_PREFIX = "<redacted:"
REDACTED_SUFFIX = ">"


_SENSITIVE_KEY_WORDS = (
    "authorization",
    "api_key",
    "apikey",
    "app_secret",
    "access_token",
    "refresh_token",
    "secret",
    "token",
    "password",
)

_SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<name_quote>['\"]?)"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)"
    r"(?P=name_quote)"
    r"(?P<space_before>\s*[:=]\s*)"
    r"(?P<quote>['\"]?)"
    r"(?P<value>[^'\"\s,;}\]]+)"
    r"(?P=quote)",
    re.IGNORECASE,
)
_BEARER_TOKEN_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_MIN_KNOWN_SECRET_LENGTH = 8


@dataclass
class RedactionReport:
    """Track how much redaction happened while one artifact is being written.

    Args:
        replacement_count: Number of text replacements made.
        labels: Human-readable labels for redaction rules or known secret names.

    Returns:
        Mutable report object that can be serialized through ``to_payload``.
    """

    replacement_count: int = 0
    labels: set[str] = field(default_factory=set)

    def record(self, *, label: str, count: int = 1) -> None:
        """Record replacements for one redaction label.

        Args:
            label: Rule name or known secret label.
            count: Number of replacements made for this label.

        Returns:
            None.
        """

        if count <= 0:
            return
        self.replacement_count += count
        self.labels.add(label)

    def to_payload(self) -> dict[str, Any]:
        """Convert the report into public ``result.json`` metadata.

        Args:
            None.

        Returns:
            JSON-ready dictionary describing the redaction status.
        """

        return {
            "enabled": True,
            "replacement_count": self.replacement_count,
            "labels": sorted(self.labels),
        }


class SecretRedactor:
    """Redact known secret values and common secret-shaped fields.

    Args:
        known_secrets: Optional mapping from stable labels to concrete secret
            values.  Values that are too short or empty are ignored to reduce
            false positives.

    Returns:
        Reusable redactor instance.  It is stateless; callers pass a
        ``RedactionReport`` when they want metadata.
    """

    def __init__(self, known_secrets: Mapping[str, str] | None = None) -> None:
        """Initialize the redactor.

        Args:
            known_secrets: Labels and concrete values that must be removed from
                any text or JSON field where they appear.

        Returns:
            None.
        """

        self._known_secret_pairs = _normalize_known_secret_pairs(known_secrets or {})

    def redact_jsonable(self, value: Any, report: RedactionReport | None = None) -> Any:
        """Redact a parsed JSON-like Python value.

        Args:
            value: Parsed JSON-compatible value such as dict, list, string, or
                number.
            report: Optional report updated with replacement metadata.

        Returns:
            Redacted value with the same broad structure.  Sensitive scalar
            fields become placeholder strings.
        """

        active_report = report or RedactionReport()
        return self._redact_jsonable(value=value, report=active_report, parent_key=None)

    def redact_text(self, text: str, report: RedactionReport | None = None) -> str:
        """Redact secrets from a plain text blob.

        Args:
            text: Raw text that may include command output, dotenv content, or
                serialized JSON fragments.
            report: Optional report updated with replacement metadata.

        Returns:
            Text with known secret values and secret-shaped assignments replaced
            by placeholders.
        """

        active_report = report or RedactionReport()
        redacted = text
        for label, secret_value in self._known_secret_pairs:
            placeholder = _placeholder(label)
            redacted, count = _replace_literal(redacted, secret_value, placeholder)
            active_report.record(label=label, count=count)

        redacted, count = _replace_pattern(
            pattern=_BEARER_TOKEN_PATTERN,
            text=redacted,
            replacement="Bearer " + _placeholder("bearer_token"),
        )
        active_report.record(label="bearer_token", count=count)

        redacted = _SENSITIVE_ASSIGNMENT_PATTERN.sub(
            lambda match: _redact_assignment_match(match=match, report=active_report),
            redacted,
        )
        return redacted

    def redact_jsonl_text(self, text: str, report: RedactionReport | None = None) -> str:
        """Redact a JSONL session text while preserving one event per line.

        Args:
            text: Raw JSONL content.  Malformed lines are handled as plain text.
            report: Optional report updated with replacement metadata.

        Returns:
            Redacted JSONL text.  Parsed JSON lines are re-serialized in compact
            UTF-8 form; malformed lines remain text after regex redaction.
        """

        active_report = report or RedactionReport()
        lines: list[str] = []
        for raw_line in text.splitlines():
            if not raw_line.strip():
                lines.append(raw_line)
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                lines.append(self.redact_text(raw_line, active_report))
                continue
            redacted_event = self.redact_jsonable(event, active_report)
            lines.append(json.dumps(redacted_event, ensure_ascii=False, separators=(",", ":")))
        if text.endswith(("\n", "\r")):
            return "\n".join(lines) + "\n"
        return "\n".join(lines)

    def _redact_jsonable(self, *, value: Any, report: RedactionReport, parent_key: str | None) -> Any:
        """Recursive implementation for parsed JSON-compatible values.

        Args:
            value: Current value to redact.
            report: Redaction metadata collector.
            parent_key: Dictionary key that owns ``value``, if any.

        Returns:
            Redacted value.
        """

        if parent_key and _is_sensitive_key(parent_key) and _is_scalar(value):
            report.record(label=_normalize_label(parent_key))
            return _placeholder(_normalize_label(parent_key))
        if isinstance(value, str):
            return self.redact_text(value, report)
        if isinstance(value, list):
            return [self._redact_jsonable(value=item, report=report, parent_key=None) for item in value]
        if isinstance(value, tuple):
            return [self._redact_jsonable(value=item, report=report, parent_key=None) for item in value]
        if isinstance(value, dict):
            redacted_dict: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                redacted_dict[key_text] = self._redact_jsonable(
                    value=item,
                    report=report,
                    parent_key=key_text,
                )
            return redacted_dict
        return value


def collect_sensitive_values(value: Any, *, prefix: str = "") -> dict[str, str]:
    """Collect concrete secret values from a parsed config object.

    Args:
        value: Parsed JSON-like value to inspect.
        prefix: Internal path prefix used to build stable labels.

    Returns:
        Mapping from redaction labels to scalar values whose keys are sensitive,
        such as ``apiKey`` or ``app_secret``.
    """

    found: dict[str, str] = {}
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if _is_sensitive_key(key) and _is_scalar(item):
                text = str(item)
                if _is_redactable_known_secret(text):
                    found[_normalize_label(path)] = text
                continue
            found.update(collect_sensitive_values(item, prefix=path))
        return found
    if isinstance(value, list):
        for index, item in enumerate(value):
            found.update(collect_sensitive_values(item, prefix=f"{prefix}[{index}]"))
    return found


def _normalize_known_secret_pairs(known_secrets: Mapping[str, str]) -> list[tuple[str, str]]:
    """Normalize and sort known secret values before replacement.

    Args:
        known_secrets: Raw label/value mapping.

    Returns:
        ``(label, value)`` pairs sorted by descending value length so longer
        secrets are replaced before shorter overlapping strings.
    """

    pairs: list[tuple[str, str]] = []
    seen_values: set[str] = set()
    for label, value in known_secrets.items():
        text = str(value)
        if not _is_redactable_known_secret(text) or text in seen_values:
            continue
        seen_values.add(text)
        pairs.append((_normalize_label(label), text))
    return sorted(pairs, key=lambda item: len(item[1]), reverse=True)


def _is_redactable_known_secret(value: str) -> bool:
    """Return whether a known value is safe to use for literal replacement.

    Args:
        value: Candidate secret value.

    Returns:
        True when the value is long enough and not already a placeholder.
    """

    stripped = value.strip()
    if len(stripped) < _MIN_KNOWN_SECRET_LENGTH:
        return False
    return not stripped.startswith(REDACTED_PREFIX)


def _replace_literal(text: str, needle: str, replacement: str) -> tuple[str, int]:
    """Replace all literal occurrences of one secret value.

    Args:
        text: Source text.
        needle: Exact secret value.
        replacement: Placeholder to write.

    Returns:
        Tuple of redacted text and replacement count.
    """

    count = text.count(needle)
    if count == 0:
        return text, 0
    return text.replace(needle, replacement), count


def _replace_pattern(*, pattern: re.Pattern[str], text: str, replacement: str) -> tuple[str, int]:
    """Replace regex matches and report the number of replacements.

    Args:
        pattern: Compiled pattern to replace.
        text: Source text.
        replacement: Replacement text.

    Returns:
        Tuple of redacted text and replacement count.
    """

    redacted, count = pattern.subn(replacement, text)
    return redacted, count


def _redact_assignment_match(*, match: re.Match[str], report: RedactionReport) -> str:
    """Redact one ``KEY=value`` or ``key: value`` regex match.

    Args:
        match: Regex match from ``_SENSITIVE_ASSIGNMENT_PATTERN``.
        report: Redaction metadata collector.

    Returns:
        The original key and separator with the value replaced by a placeholder.
    """

    name = match.group("name")
    value = match.group("value")
    if not _is_sensitive_key(name):
        return match.group(0)
    if value.startswith(REDACTED_PREFIX):
        return match.group(0)
    label = _normalize_label(name)
    name_quote = match.group("name_quote")
    quote = match.group("quote")
    report.record(label=label)
    return f"{name_quote}{name}{name_quote}{match.group('space_before')}{quote}{_placeholder(label)}{quote}"


def _placeholder(label: str) -> str:
    """Build a stable redaction placeholder.

    Args:
        label: Rule name or known secret label.

    Returns:
        Placeholder text safe to commit.
    """

    return f"{REDACTED_PREFIX}{_normalize_label(label)}{REDACTED_SUFFIX}"


def _is_sensitive_key(key: str) -> bool:
    """Return whether a dictionary key or assignment name looks sensitive.

    Args:
        key: Field or variable name.

    Returns:
        True when the normalized name contains a known secret-related word.
    """

    normalized = key.replace("-", "_").replace(".", "_").lower()
    return any(word in normalized for word in _SENSITIVE_KEY_WORDS)


def _is_scalar(value: Any) -> bool:
    """Return whether a value should be replaced as a single secret field.

    Args:
        value: Candidate JSON value.

    Returns:
        True for strings, numbers, booleans, and null; False for containers.
    """

    return value is None or isinstance(value, (str, int, float, bool))


def _normalize_label(label: str) -> str:
    """Normalize labels so placeholders are stable and compact.

    Args:
        label: Raw key path or rule name.

    Returns:
        Lowercase label containing only simple punctuation.
    """

    lowered = label.strip().replace("[", "_").replace("]", "").replace(".", "_").replace("-", "_").lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", lowered).strip("_")
    return normalized or "secret"
