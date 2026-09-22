#!/usr/bin/env python3
"""Classify persisted review freshness against current schema-v2 bindings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import compute_bead_content_sha
import contract_loader


REUSABLE_OUTCOMES = {"clean", "warnings", "blocked"}


def _review(bead: dict[str, Any]) -> dict[str, Any] | None:
    metadata = bead.get("metadata")
    value = metadata.get("review") if isinstance(metadata, dict) else None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def classify_review_freshness(
    bead: dict[str, Any], *, current_shas: dict[str, str]
) -> dict[str, Any]:
    """Return review outcome and orthogonal freshness for one bead."""
    result = {
        "bead_id": bead.get("id"),
        "outcome": None,
        "freshness": "never-reviewed",
        "stale_reasons": [],
        "needs_review": True,
    }
    review = _review(bead)
    if review is None:
        return result
    if review.get("schema_version") != 2:
        result["stale_reasons"] = ["legacy-schema"]
        return result

    result["outcome"] = review.get("outcome")
    reasons: list[str] = []
    if review.get("outcome") not in REUSABLE_OUTCOMES:
        reasons.append("invalid-outcome")
    for field, reason in (
        ("content_sha", "content"),
        ("reviewer_sha", "reviewer"),
        ("contract_sha", "contract"),
    ):
        if review.get(field) != current_shas.get(field):
            reasons.append(reason)
    result["stale_reasons"] = reasons
    result["freshness"] = "stale" if reasons else "current"
    result["needs_review"] = bool(reasons)
    return result


def current_shas(
    bead: dict[str, Any], *, repo_root: str | Path
) -> dict[str, str]:
    contract = contract_loader.resolve_contract(repo_root=repo_root)
    if contract["status"] != "ok":
        codes = ", ".join(item["code"] for item in contract["diagnostics"])
        raise RuntimeError(
            f"resolved review contract is not usable: {codes or contract['status']}"
        )
    return {
        "content_sha": compute_bead_content_sha.compute_content_sha(
            bead, label_families=contract["label_families"]
        ),
        "reviewer_sha": compute_bead_content_sha.compute_reviewer_sha(),
        "contract_sha": contract["contract_sha"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--input",
        type=Path,
        help="JSON bead or bead list; omit to read stdin.",
    )
    args = parser.parse_args(argv)
    payload = (
        json.loads(args.input.read_text(encoding="utf-8"))
        if args.input
        else json.load(sys.stdin)
    )
    beads = payload if isinstance(payload, list) else [payload]
    results = [
        classify_review_freshness(
            bead,
            current_shas=current_shas(bead, repo_root=args.repo_root),
        )
        for bead in beads
    ]
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
