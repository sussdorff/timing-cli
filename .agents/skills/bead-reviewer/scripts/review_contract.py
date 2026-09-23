#!/usr/bin/env python3
"""Typed request and result contract for live bead specification reviews."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import finding_rules


PROFILES = {
    "formal": ("formal",),
    "semantic": ("semantic",),
    "repository": ("repository",),
    "related-beads": ("related-beads",),
    "full": ("formal", "semantic", "repository", "related-beads"),
}
OUTCOMES = {"clean", "warnings", "blocked", "unavailable"}
CRITERION_STATUSES = {"ran", "skipped", "unavailable"}
SEVERITIES = {"blocking", "warning"}
EDIT_OPERATIONS = {"replace", "remove", "add"}


class ReviewContractError(ValueError):
    """Raised when a review request or result violates the closed contract."""


def normalize_review_request(
    *,
    bead_id: str,
    target_repo: str | Path,
    profile: str = "full",
    criteria: list[str] | None = None,
) -> dict[str, Any]:
    identifier = bead_id.strip()
    if not identifier:
        raise ReviewContractError("bead_id is required")
    if profile not in PROFILES:
        raise ReviewContractError(f"unknown review profile: {profile}")
    selected = tuple(criteria) if criteria is not None else PROFILES[profile]
    unknown = sorted(set(selected) - set(PROFILES["full"]))
    if unknown:
        raise ReviewContractError(f"unknown review criteria: {', '.join(unknown)}")
    repo = Path(target_repo).expanduser().resolve()
    if not repo.is_dir():
        raise ReviewContractError(f"target repository does not exist: {repo}")
    return {
        "bead_id": identifier,
        "profile": profile,
        "criteria": list(selected),
        "target_repo": str(repo),
    }


def validate_review_result(
    result: dict[str, Any],
    *,
    expected_bead_id: str,
    expected_digest: str,
    expected_reviewer_sha: str,
    expected_contract_sha: str,
    allowed_rule_ids: set[str] | frozenset[str],
    expected_profile: str | None = None,
) -> dict[str, Any]:
    if result.get("bead_id") != expected_bead_id:
        raise ReviewContractError("review bead_id does not match the request")
    if result.get("profile") not in PROFILES:
        raise ReviewContractError("review profile is invalid")
    if expected_profile is not None and result.get("profile") != expected_profile:
        raise ReviewContractError("review profile does not match the request")
    outcome = result.get("outcome")
    if outcome not in OUTCOMES:
        raise ReviewContractError("review outcome is invalid")
    if outcome == "unavailable":
        _validate_unavailable(result)
        return result
    if result.get("reviewed_digest") != expected_digest:
        raise ReviewContractError(
            "review content digest does not match the live revision"
        )
    if result.get("reviewer_sha") != expected_reviewer_sha:
        raise ReviewContractError("reviewer digest does not match the live reviewer")
    if result.get("contract_sha") != expected_contract_sha:
        raise ReviewContractError("contract digest does not match the resolved contract")

    criteria = result.get("criteria")
    if not isinstance(criteria, list):
        raise ReviewContractError("criteria must be a list")
    for item in criteria:
        if not isinstance(item, dict) or item.get("criterion") not in PROFILES["full"]:
            raise ReviewContractError("criterion entry is invalid")
        if item.get("status") not in CRITERION_STATUSES:
            raise ReviewContractError("criterion status is invalid")
        if item["status"] != "ran" and not item.get("reason"):
            raise ReviewContractError("skipped or unavailable criteria require a reason")

    findings = result.get("findings")
    if not isinstance(findings, list):
        raise ReviewContractError("findings must be a list")
    seen_finding_ids: set[str] = set()
    for finding in findings:
        finding_id = _validate_finding(
            finding,
            bead_id=expected_bead_id,
            allowed_rule_ids=allowed_rule_ids,
        )
        if finding_id in seen_finding_ids:
            raise ReviewContractError(f"duplicate finding_id: {finding_id}")
        seen_finding_ids.add(finding_id)
    outcome = result["outcome"]
    severities = {finding["severity"] for finding in findings}
    if outcome == "clean" and findings:
        raise ReviewContractError("clean outcome cannot contain findings")
    if outcome == "warnings" and (not findings or severities != {"warning"}):
        raise ReviewContractError("warnings outcome requires only warning findings")
    if outcome == "blocked" and (not findings or "blocking" not in severities):
        raise ReviewContractError("blocked outcome requires a blocking finding")
    return result


def _validate_unavailable(result: dict[str, Any]) -> None:
    reason = result.get("unavailable_reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ReviewContractError("unavailable outcome requires unavailable_reason")
    if result.get("reviewed_digest") not in {None, ""}:
        raise ReviewContractError("unavailable outcome requires an empty digest")
    if result.get("criteria") != []:
        raise ReviewContractError("unavailable outcome requires empty criteria")
    if result.get("findings") != []:
        raise ReviewContractError("unavailable outcome requires empty findings")


def _validate_finding(
    finding: Any,
    *,
    bead_id: str,
    allowed_rule_ids: set[str] | frozenset[str],
) -> str:
    if not isinstance(finding, dict):
        raise ReviewContractError("finding must be an object")
    for field in (
        "rule_id",
        "finding_id",
        "criterion",
        "message",
    ):
        if not isinstance(finding.get(field), str) or not finding[field].strip():
            raise ReviewContractError(f"finding {field} is required")
    if finding["criterion"] not in PROFILES["full"]:
        raise ReviewContractError("finding criterion is invalid")
    if finding.get("severity") not in SEVERITIES:
        raise ReviewContractError("finding severity is invalid")
    evidence = finding.get("evidence")
    if not isinstance(evidence, list) or not evidence or not all(
        isinstance(item, str) and item.strip() for item in evidence
    ):
        raise ReviewContractError("finding evidence must contain at least one reference")
    change = finding.get("recommended_change")
    if not isinstance(change, dict):
        raise ReviewContractError("finding recommended_change must be a structured edit")
    if change.get("operation") not in EDIT_OPERATIONS:
        raise ReviewContractError(
            "finding recommended_change operation must be replace, remove, or add"
        )
    for field in ("target", "result"):
        if not isinstance(change.get(field), str) or not change[field].strip():
            raise ReviewContractError(
                f"finding recommended_change {field} is required"
            )
    try:
        return finding_rules.validate_finding_identity(
            finding,
            bead_id=bead_id,
            allowed_rules=allowed_rule_ids,
        )
    except finding_rules.FindingRuleError as exc:
        raise ReviewContractError(str(exc)) from exc


def _load_json_object(path: str | Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewContractError(f"could not load {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewContractError(f"{label} must contain one JSON object")
    return value


def validate_result_files(
    *,
    result_file: str | Path,
    bindings_file: str | Path,
    contract_file: str | Path,
    bead_id: str,
    profile: str,
) -> dict[str, Any]:
    """Validate one ACPX answer against caller-owned live bindings and rules."""
    result = _load_json_object(result_file, label="review result")
    bindings = _load_json_object(bindings_file, label="review bindings")
    contract = _load_json_object(contract_file, label="resolved review contract")
    rules = contract.get("rules")
    if contract.get("status") != "ok" or not isinstance(rules, list):
        raise ReviewContractError("resolved review contract is not usable")
    return validate_review_result(
        result,
        expected_bead_id=bead_id,
        expected_digest=str(bindings.get("content_sha") or ""),
        expected_reviewer_sha=str(bindings.get("reviewer_sha") or ""),
        expected_contract_sha=str(bindings.get("contract_sha") or ""),
        allowed_rule_ids=finding_rules.allowed_rule_ids(rules),
        expected_profile=profile,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--result-file", required=True)
    validate.add_argument("--bindings-file", required=True)
    validate.add_argument("--contract-file", required=True)
    validate.add_argument("--bead-id", required=True)
    validate.add_argument("--profile", choices=sorted(PROFILES), default="full")
    args = parser.parse_args(argv)
    try:
        result = validate_result_files(
            result_file=args.result_file,
            bindings_file=args.bindings_file,
            contract_file=args.contract_file,
            bead_id=args.bead_id,
            profile=args.profile,
        )
    except ReviewContractError as exc:
        print(
            json.dumps({"status": "error", "error": str(exc)}, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
