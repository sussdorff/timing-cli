"""Review-Risk vocabulary and parser for hosted work orders.

A work order declares its review risk on one column-0 ``Review-Risk:`` line.
pr-agent applies that value as the floor of the pull request's risk label; the
intake author check validates the declaration before the issue is created or
updated. This module is the single owner of the vocabulary and the parser.
"""

from __future__ import annotations

import re
from typing import Any

REVIEW_RISKS = ("none", "payment", "pii", "auth", "compliance")
REVIEW_RISK_ALIASES = {"personal-data": "pii"}
REVIEW_RISK_FIELD = "Review-Risk"

_REVIEW_RISK_LINE_RE = re.compile(
    rf"^\s*(?:[-*+]\s*)?(?:\*\*)?{REVIEW_RISK_FIELD}(?:\*\*)?\s*:\*{{0,2}}\s*(.*?)\s*$",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


class ReviewRiskError(ValueError):
    """The body does not declare exactly one known review risk."""

    def __init__(self, code: str, message: str, remedy: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remedy = remedy
        self.details = details


def review_risk_from_body(description: str) -> str:
    """The single review risk declared by an issue body, normalized."""
    declared = _review_risk_declarations(description or "")
    if not declared:
        raise ReviewRiskError(
            "REVIEW_RISK_MISSING",
            "The issue body declares no review-risk classification.",
            _risk_remedy(),
        )
    if len(declared) > 1:
        raise ReviewRiskError(
            "REVIEW_RISK_CONFLICTING",
            "The issue body declares more than one review-risk classification.",
            f"Keep exactly one `{REVIEW_RISK_FIELD}:` line in the issue body.",
            declared=declared,
        )
    return validated_review_risk(declared[0])


def validated_review_risk(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if not text:
        raise ReviewRiskError(
            "REVIEW_RISK_MISSING",
            "No review-risk classification was supplied.",
            _risk_remedy(),
        )
    text = REVIEW_RISK_ALIASES.get(text, text)
    if text not in REVIEW_RISKS:
        raise ReviewRiskError(
            "REVIEW_RISK_UNKNOWN",
            f"Unknown review-risk classification {text!r}.",
            _risk_remedy(),
            review_risk=text,
        )
    return text


def _review_risk_declarations(description: str) -> list[str]:
    declared: list[str] = []
    fenced = False
    marker = ""
    for line in description.splitlines():
        fence = _FENCE_RE.match(line)
        if fence is not None:
            delimiter = fence.group(1)
            if not fenced:
                fenced, marker = True, delimiter
            elif delimiter[0] == marker[0] and len(delimiter) >= len(marker):
                fenced, marker = False, ""
            continue
        if fenced:
            continue
        match = _REVIEW_RISK_LINE_RE.match(line)
        if match is not None:
            declared.append(match.group(1).strip().strip("`*").strip())
    return declared


def _risk_remedy() -> str:
    return (
        f"Add exactly one `{REVIEW_RISK_FIELD}: <value>` line to the issue body, "
        f"where <value> is one of {', '.join(REVIEW_RISKS)}."
    )
