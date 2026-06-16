"""Shared helpers for normalizing low-risk text formatting noise."""

from __future__ import annotations


_DISPLAY_TEXT_TRANSLATION = str.maketrans(
    {
        "（": "(",
        "）": ")",
    }
)


def normalize_display_text(value: str) -> str:
    """Normalize formatting variants that should not change business meaning."""

    return value.translate(_DISPLAY_TEXT_TRANSLATION)
