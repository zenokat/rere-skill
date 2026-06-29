"""Safety gate for CodeBuddy eval runs.

The eval harness does not exercise real upload or external write actions. The
safety gate blocks instructions that positively request upload and returns a
permission mode suitable for Docker-isolated validate/preview cases. Docker is
the security boundary; CodeBuddy permissions are auxiliary guardrails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from evals.cases.manifest_models import EvalCase


@dataclass(frozen=True)
class SafetyDecision:
    """Safety decision used by the CodeBuddy command builder.

    Attributes:
        allowed: Whether the case may continue.
        permission_mode: CodeBuddy permission mode for the run. Docker-isolated
            runs use bypassPermissions because the container is the security
            boundary.
        blocked_reason: Short explanation when the case is blocked.
        inject_skip_permissions: Legacy compatibility flag. It remains False
            because the command uses --permission-mode instead of the short
            skip flag.
        notes: Additional evaluator-facing notes.
    """

    allowed: bool
    permission_mode: str
    blocked_reason: str | None = None
    inject_skip_permissions: bool = False
    notes: list[str] = field(default_factory=list)


class CodeBuddySafetyGuard:
    """Decide whether a case is safe to run before invoking CodeBuddy."""

    def decide(self, *, case: EvalCase) -> SafetyDecision:
        """Perform the pre-run safety decision.

        Args:
            case: Current eval case.

        Returns:
            SafetyDecision describing whether execution is allowed and which
            permission mode the command builder should request.
        """

        upload_requested = _looks_like_upload_request(case.prompt)

        if upload_requested:
            return SafetyDecision(
                allowed=False,
                permission_mode="bypassPermissions",
                blocked_reason="The eval harness does not run upload or external write actions.",
            )

        return SafetyDecision(
            allowed=True,
            permission_mode="bypassPermissions",
            inject_skip_permissions=False,
            notes=[
                "Upload is blocked by policy; Docker is the primary read/write isolation boundary.",
            ],
        )


def _looks_like_upload_request(text: str) -> bool:
    """Decide whether the instruction positively asks for upload.

    Args:
        text: Case instruction text.

    Returns:
        True when upload looks requested, False when upload is only mentioned as
        a prohibition such as "do not run upload".
    """

    cleaned = _remove_negated_upload_mentions(text.lower())
    return bool(re.search(r"\bupload\b", cleaned)) or "\u4e0a\u4f20" in cleaned


def _remove_negated_upload_mentions(text: str) -> str:
    """Remove phrases where upload is explicitly prohibited.

    Args:
        text: Lower-cased instruction text.

    Returns:
        Instruction text with negative upload phrases removed, so remaining
        upload mentions are more likely to be positive requests.
    """

    english_patterns = [
        r"\bdo\s+not\s+(?:(?:run|execute|perform|call|trigger|do)\s+)?(?:the\s+)?upload\b",
        r"\bdon't\s+(?:(?:run|execute|perform|call|trigger|do)\s+)?(?:the\s+)?upload\b",
        r"\bnot\s+(?:(?:run|execute|perform|call|trigger|do)\s+)?(?:the\s+)?upload\b",
        r"\bno\s+upload\b",
        r"\bwithout\s+upload\b",
        r"\bupload\s+(?:was\s+|is\s+|should\s+be\s+)?not\s+(?:run|executed|performed|called|triggered|done)\b",
        r"\bupload\s+not\s+(?:run|executed|performed|called|triggered|done)\b",
    ]
    chinese_patterns = [
        r"\u4e0d\u8981(?:\u6267\u884c|\u8fd0\u884c|\u8c03\u7528|\u89e6\u53d1|\u8dd1|\u505a)?\s*(?:upload|\u4e0a\u4f20)",
        r"\u4e0d(?:\u6267\u884c|\u8fd0\u884c|\u8c03\u7528|\u89e6\u53d1|\u8dd1|\u505a)?\s*(?:upload|\u4e0a\u4f20)",
        r"\u7981\u6b62(?:\u6267\u884c|\u8fd0\u884c|\u8c03\u7528|\u89e6\u53d1)?\s*(?:upload|\u4e0a\u4f20)",
        r"\u672a(?:\u6267\u884c|\u8fd0\u884c|\u8c03\u7528|\u89e6\u53d1)?\s*(?:upload|\u4e0a\u4f20)",
        r"(?:upload|\u4e0a\u4f20)\s*\u4e0d(?:\u6267\u884c|\u8fd0\u884c|\u8c03\u7528|\u89e6\u53d1|\u505a)?",
    ]
    cleaned = text
    for pattern in [*english_patterns, *chinese_patterns]:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    return cleaned