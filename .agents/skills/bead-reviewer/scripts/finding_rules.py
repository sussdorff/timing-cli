#!/usr/bin/env python3
"""Stable rule and deterministic occurrence identities for review findings."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


RULE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$")
FINDING_ID_SUFFIX_RE = re.compile(r"^[0-9a-f]{12}$")
REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "finding-rule-registry.json"
)


class FindingRuleError(ValueError):
    """Raised when finding taxonomy or identity data violates the contract."""


def validate_rule_id(rule_id: Any) -> str:
    """Return a valid uppercase-kebab rule ID or raise a closed error."""
    if not isinstance(rule_id, str) or not RULE_ID_RE.fullmatch(rule_id):
        raise FindingRuleError("rule_id must use uppercase kebab case")
    return rule_id


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the versioned cross-cutting finding-rule registry."""
    source = Path(path).expanduser().resolve() if path else REGISTRY_PATH
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FindingRuleError(f"finding-rule registry is not readable: {source}") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "rules"}:
        raise FindingRuleError("finding-rule registry must contain schema_version and rules")
    if payload["schema_version"] != 1 or not isinstance(payload["rules"], list):
        raise FindingRuleError("finding-rule registry schema is unsupported")

    seen: set[str] = set()
    for entry in payload["rules"]:
        if not isinstance(entry, dict) or set(entry) != {"rule_id", "description"}:
            raise FindingRuleError("finding-rule registry entries are invalid")
        rule_id = validate_rule_id(entry.get("rule_id"))
        if rule_id in seen:
            raise FindingRuleError(f"duplicate finding-rule registry ID: {rule_id}")
        if not isinstance(entry.get("description"), str) or not entry["description"].strip():
            raise FindingRuleError(f"finding-rule registry description is required: {rule_id}")
        seen.add(rule_id)
    return payload


def registered_rule_ids(path: str | Path | None = None) -> set[str]:
    """Return the cross-cutting aggregation keys owned by the reviewer."""
    return {entry["rule_id"] for entry in load_registry(path)["rules"]}


def allowed_rule_ids(
    contract_rules: Iterable[Mapping[str, Any]],
    *,
    registry_path: str | Path | None = None,
) -> set[str]:
    """Merge reviewer-owned keys with rule IDs from one resolved contract."""
    allowed = registered_rule_ids(registry_path)
    for rule in contract_rules:
        if not isinstance(rule, Mapping):
            raise FindingRuleError("resolved contract rule must be an object")
        allowed.add(validate_rule_id(rule.get("rule_id")))
    return allowed


def canonical_evidence(evidence: Any) -> list[str]:
    """Return sorted unique non-empty evidence anchors for identity hashing."""
    if not isinstance(evidence, list) or not evidence:
        raise FindingRuleError("finding evidence must contain at least one reference")
    anchors: set[str] = set()
    for item in evidence:
        if not isinstance(item, str) or not item.strip():
            raise FindingRuleError("finding evidence must contain non-empty strings")
        anchors.add(item.strip())
    return sorted(anchors)


def build_finding_id(
    *,
    rule_id: str,
    bead_id: str,
    criterion: str,
    evidence: list[str],
) -> str:
    """Build the deterministic occurrence ID for one canonical finding tuple."""
    rule = validate_rule_id(rule_id)
    bead = str(bead_id or "").strip()
    if not bead or ":" in bead:
        raise FindingRuleError("bead_id must be non-empty and cannot contain a colon")
    criterion_value = str(criterion or "").strip()
    if not criterion_value:
        raise FindingRuleError("finding criterion is required")
    payload = {
        "bead_id": bead,
        "criterion": criterion_value,
        "evidence": canonical_evidence(evidence),
        "rule_id": rule,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    suffix = hashlib.sha256(encoded).hexdigest()[:12]
    return f"{rule}:{bead}:{suffix}"


def validate_finding_identity(
    finding: Mapping[str, Any],
    *,
    bead_id: str,
    allowed_rules: set[str] | frozenset[str],
) -> str:
    """Validate one finding and return its deterministic occurrence ID."""
    rule_id = validate_rule_id(finding.get("rule_id"))
    if rule_id not in allowed_rules:
        raise FindingRuleError(f"unknown rule_id: {rule_id}")
    expected = build_finding_id(
        rule_id=rule_id,
        bead_id=bead_id,
        criterion=finding.get("criterion"),
        evidence=finding.get("evidence"),
    )
    finding_id = finding.get("finding_id")
    if not isinstance(finding_id, str) or finding_id != expected:
        raise FindingRuleError("finding_id is not deterministic for its canonical inputs")
    suffix = finding_id.rsplit(":", 1)[-1]
    if not FINDING_ID_SUFFIX_RE.fullmatch(suffix):
        raise FindingRuleError("finding_id suffix must be 12 lowercase hex characters")
    return finding_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--rule-id", required=True)
    build.add_argument("--bead-id", required=True)
    build.add_argument("--criterion", required=True)
    build.add_argument("--evidence", action="append", required=True)
    subparsers.add_parser("registry")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "registry":
            print(json.dumps(load_registry(), ensure_ascii=True, sort_keys=True))
        else:
            print(
                build_finding_id(
                    rule_id=args.rule_id,
                    bead_id=args.bead_id,
                    criterion=args.criterion,
                    evidence=args.evidence,
                )
            )
    except FindingRuleError as exc:
        print(f"finding_rules.py: ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
