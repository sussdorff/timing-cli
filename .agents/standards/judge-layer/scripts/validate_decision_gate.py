#!/usr/bin/env python3
"""Validate Decision Brief and Human Decision Gate markdown shape."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DECISION_BRIEF_FIELDS = {
    "Decision required",
    "Recommended default",
    "Operational risk",
    "Operational do-nothing/default outcome",
    "Delivery consequence",
    "Decision needed by",
    "Evidence appendix references",
    "Blast radius",
    "Rollback path",
    "Alternatives considered",
}
DECISION_GATE_FIELDS = {
    "Decision owner",
    "Allowed outcomes",
    "Trigger timing",
    "Minimum evidence plan",
    "Operational do-nothing/default outcome",
    "Delivery consequence",
    "Overrideability",
    "Sequencing constraints",
}
JUDGE_OUTCOMES = {"ALLOW", "BLOCK", "REVISE", "ESCALATE"}
MANDATE_FIELDS = {
    "scope",
    "limits",
    "evidence_refs",
    "granted_at",
    "granted_by",
    "expires_at",
    "supersedes",
}


def load_document(path: str) -> str:
    """Load a markdown document."""
    return sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")


def is_non_empty_string(value: Any) -> bool:
    """Return whether value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def extract_section(markdown: str, heading: str) -> str | None:
    """Return the body for a level-2 markdown section."""
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(markdown)
    if match is None:
        return None
    next_heading = re.search(r"^##\s+", markdown[match.end() :], re.MULTILINE)
    if next_heading is None:
        return markdown[match.end() :]
    return markdown[match.end() : match.end() + next_heading.start()]


def has_subheading(section: str, heading: str) -> bool:
    """Return whether a section contains a level-3 markdown heading."""
    return bool(re.search(rf"^###\s+{re.escape(heading)}\s*$", section, re.MULTILINE))


def parse_fields(section: str) -> dict[str, str]:
    """Parse simple markdown field labels of the form `Label: value`."""
    fields: dict[str, str] = {}
    for line in section.splitlines():
        match = re.match(r"^\s*(?:[-*]\s*)?(?:\*\*)?([^:\n`*][^:\n]*?)(?:\*\*)?:\s*(.*?)\s*$", line)
        if match is None:
            continue
        label = match.group(1).strip()
        value = match.group(2).strip()
        fields[label.lower()] = value
    return fields


def validate_required_fields(
    *,
    section_name: str,
    fields: dict[str, str],
    required: set[str],
    errors: list[str],
) -> None:
    """Validate required non-empty fields."""
    for field in sorted(required):
        value = fields.get(field.lower())
        if not is_non_empty_string(value):
            errors.append(f"{section_name}.{field}: missing required field")


def validate_allowed_outcomes(value: str | None, errors: list[str]) -> None:
    """Validate gate outcome vocabulary without deciding the outcome."""
    if not is_non_empty_string(value):
        return
    tokens = [token.strip().strip(".`").upper() for token in re.split(r"[,/]", value or "") if token.strip()]
    invalid = [token for token in tokens if token not in JUDGE_OUTCOMES]
    if not tokens or invalid:
        errors.append(
            "Human Decision Gate.Allowed outcomes: expected comma-separated values from "
            "ALLOW, BLOCK, REVISE, ESCALATE"
        )


def validate_mandate_field_disjointness(fields: dict[str, str], errors: list[str]) -> None:
    """Reject inline Mandate field redefinitions in a gate."""
    for field in sorted(MANDATE_FIELDS & set(fields)):
        errors.append(
            f"Human Decision Gate: Mandate field {field!r} must not be redefined; "
            "reference mandate-schema.md instead"
        )


def validate_decision_document(markdown: str) -> list[str]:
    """Return structural errors for Decision Brief and Human Decision Gate markdown."""
    errors: list[str] = []
    brief_section = extract_section(markdown, "Decision Brief")
    gate_section = extract_section(markdown, "Human Decision Gate")
    if brief_section is None and gate_section is None:
        return ["document: expected ## Decision Brief or ## Human Decision Gate section"]

    if brief_section is not None:
        if not has_subheading(brief_section, "Compact Manager View"):
            errors.append("Decision Brief.Compact Manager View: missing required section")
        if not has_subheading(brief_section, "Evidence Appendix"):
            errors.append("Decision Brief.Evidence Appendix: missing required section")
        validate_required_fields(
            section_name="Decision Brief",
            fields=parse_fields(brief_section),
            required=DECISION_BRIEF_FIELDS,
            errors=errors,
        )

    if gate_section is not None:
        gate_fields = parse_fields(gate_section)
        validate_required_fields(
            section_name="Human Decision Gate",
            fields=gate_fields,
            required=DECISION_GATE_FIELDS,
            errors=errors,
        )
        validate_allowed_outcomes(gate_fields.get("allowed outcomes"), errors)
        validate_mandate_field_disjointness(gate_fields, errors)

    return errors


def envelope(status: str, summary: str, data: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    """Build the execution-result JSON envelope."""
    return {
        "status": status,
        "summary": summary,
        "data": data,
        "errors": errors,
        "next_steps": [] if status == "ok" else ["Fix the Decision Brief or Human Decision Gate structure."],
    }


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(description="Validate Decision Brief and Human Decision Gate markdown.")
    parser.add_argument("document", help="Markdown path, or '-' for stdin")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the validator."""
    args = build_parser().parse_args(argv)
    try:
        markdown = load_document(args.document)
    except Exception as exc:
        result = envelope("error", "Decision document could not be parsed", {}, [str(exc)])
        print(json.dumps(result, indent=2))
        return 2

    errors = validate_decision_document(markdown)
    status = "error" if errors else "ok"
    data = {
        "decision_brief": extract_section(markdown, "Decision Brief") is not None,
        "human_decision_gate": extract_section(markdown, "Human Decision Gate") is not None,
    }
    summary = "Decision document schema valid" if not errors else "Decision document schema invalid"
    print(json.dumps(envelope(status, summary, data, errors), indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
