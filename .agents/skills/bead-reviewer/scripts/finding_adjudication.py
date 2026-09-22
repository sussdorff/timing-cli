#!/usr/bin/env python3
"""Partition author decisions so only genuine review disputes escalate."""

from __future__ import annotations

from typing import Any


class FindingAdjudicationError(ValueError):
    """Raised when findings or author decisions are incomplete."""


def adjudicate_findings(
    findings: list[dict[str, Any]], decisions: dict[str, dict[str, str]]
) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    disputes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in findings:
        finding_id = str(finding.get("finding_id") or "")
        if not finding_id or finding_id in seen:
            raise FindingAdjudicationError("finding IDs must be present and unique")
        seen.add(finding_id)
        author = decisions.get(finding_id)
        if not author:
            raise FindingAdjudicationError(f"missing author decision for {finding_id}")
        decision = author.get("decision")
        rationale = str(author.get("rationale") or "").strip()
        if decision not in {"accepted", "disputed"} or not rationale:
            raise FindingAdjudicationError(f"invalid author decision for {finding_id}")
        record = {**finding, "author_rationale": rationale}
        if decision == "accepted":
            accepted.append(record)
        else:
            disputes.append(record)
    return {
        "outcome": "human_required" if disputes else ("repair" if accepted else "clean"),
        "accepted": accepted,
        "disputes": disputes,
    }
