#!/usr/bin/env python3
"""Validate Action Proposal documents before judge invocation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is expected in this repo
    yaml = None


REQUIRED_FIELDS = {
    "proposal_id",
    "actor_ref",
    "risk_class",
    "effect_type",
    "intended_action",
    "reason",
    "evidence_refs",
    "authorization",
    "expected_consequence",
    "rollback_path",
}
RISK_CLASSES = {"read-only", "reversible-write", "external-side-effect", "high-risk"}
EFFECT_TYPES = {"filesystem", "network", "financial", "messaging", "credential", "other"}
PROVENANCE_LABELS = {"observed", "inferred", "generated", "confirmed", "disputed", "superseded"}


def load_document(path: str) -> Any:
    """Load a YAML-compatible or JSON proposal document."""
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    return json.loads(text)


def is_non_empty_string(value: Any) -> bool:
    """Return whether value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def validate_evidence_refs(value: Any, errors: list[str]) -> None:
    """Validate evidence_refs shape without judging evidence sufficiency."""
    if not isinstance(value, list):
        errors.append("evidence_refs: expected array")
        return
    for index, ref in enumerate(value):
        prefix = f"evidence_refs[{index}]"
        if not isinstance(ref, dict):
            errors.append(f"{prefix}: expected object")
            continue
        if not is_non_empty_string(ref.get("ref")):
            errors.append(f"{prefix}.ref: expected non-empty string")
        label = ref.get("label")
        if label not in PROVENANCE_LABELS:
            errors.append(f"{prefix}.label: invalid provenance label {label!r}")


def validate_intended_action(value: Any, errors: list[str]) -> None:
    """Validate the nested intended_action object."""
    if not isinstance(value, dict):
        errors.append("intended_action: expected object")
        return
    for field in ("verb", "target"):
        if not is_non_empty_string(value.get(field)):
            errors.append(f"intended_action.{field}: expected non-empty string")
    if "arguments" not in value:
        errors.append("intended_action.arguments: missing required field")
    elif not isinstance(value["arguments"], dict):
        errors.append("intended_action.arguments: expected object")


def validate_action_proposal(proposal: Any) -> list[str]:
    """Return schema errors for an Action Proposal."""
    errors: list[str] = []
    if not isinstance(proposal, dict):
        return ["proposal: expected object"]

    missing = sorted(REQUIRED_FIELDS - set(proposal))
    if missing:
        errors.append("missing required field(s): " + ", ".join(missing))

    for field in ("proposal_id", "actor_ref", "reason", "expected_consequence"):
        if field in proposal and not is_non_empty_string(proposal[field]):
            errors.append(f"{field}: expected non-empty string")

    risk_class = proposal.get("risk_class")
    if "risk_class" in proposal and risk_class not in RISK_CLASSES:
        errors.append(f"risk_class: invalid value {risk_class!r}")

    effect_type = proposal.get("effect_type")
    if "effect_type" in proposal and effect_type not in EFFECT_TYPES:
        errors.append(f"effect_type: invalid value {effect_type!r}")

    if "intended_action" in proposal:
        validate_intended_action(proposal["intended_action"], errors)

    if "evidence_refs" in proposal:
        validate_evidence_refs(proposal["evidence_refs"], errors)

    if "authorization" in proposal and proposal["authorization"] is not None:
        if not isinstance(proposal["authorization"], dict):
            errors.append("authorization: expected object or null")

    if "rollback_path" in proposal and proposal["rollback_path"] is not None:
        if not is_non_empty_string(proposal["rollback_path"]):
            errors.append("rollback_path: expected non-empty string or null")

    return errors


def envelope(status: str, summary: str, data: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    """Build the execution-result JSON envelope."""
    return {
        "status": status,
        "summary": summary,
        "data": data,
        "errors": errors,
        "next_steps": [] if status == "ok" else ["Fix the Action Proposal schema errors before calling the judge."],
    }


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(description="Validate a judge-layer Action Proposal.")
    parser.add_argument("proposal", help="Proposal YAML/JSON path, or '-' for stdin")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the validator."""
    args = build_parser().parse_args(argv)
    try:
        proposal = load_document(args.proposal)
    except Exception as exc:
        result = envelope("error", "Action Proposal could not be parsed", {}, [str(exc)])
        print(json.dumps(result, indent=2))
        return 2

    errors = validate_action_proposal(proposal)
    status = "error" if errors else "ok"
    data = {}
    if isinstance(proposal, dict):
        data = {
            "proposal_id": proposal.get("proposal_id"),
            "risk_class": proposal.get("risk_class"),
            "effect_type": proposal.get("effect_type"),
        }
    summary = "Action Proposal schema valid" if not errors else "Action Proposal schema invalid"
    print(json.dumps(envelope(status, summary, data, errors), indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
