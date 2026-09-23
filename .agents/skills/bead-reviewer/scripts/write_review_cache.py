#!/usr/bin/env python3
"""Persist one typed review result only when it still matches live state."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import compute_bead_content_sha
import contract_loader
import finding_rules
import review_contract


SCHEMA_VERSION = 2


class ReviewCacheWriteError(RuntimeError):
    """Raised when a review result cannot be safely persisted."""


def _run_bd(
    args: list[str], *, repo_root: str | Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bd", *args],
        cwd=Path(repo_root).expanduser().resolve(),
        capture_output=True,
        text=True,
        check=False,
    )


def load_live_bead(bead_id: str, repo_root: str | Path) -> dict[str, Any]:
    """Load one current bead from the explicitly bound target repository."""
    try:
        return compute_bead_content_sha.load_live_bead(bead_id, repo_root)
    except (RuntimeError, ValueError) as exc:
        raise ReviewCacheWriteError(str(exc)) from exc


def compute_review_shas(
    bead: dict[str, Any],
    repo_root: str | Path,
    reviewer_skill_path: str | None = None,
) -> dict[str, Any]:
    """Compute the three bindings required by schema v2."""
    contract = contract_loader.resolve_contract(repo_root=repo_root)
    if contract["status"] != "ok":
        codes = ", ".join(item["code"] for item in contract["diagnostics"])
        raise ReviewCacheWriteError(
            f"resolved review contract is not usable: {codes or contract['status']}"
        )
    try:
        allowed_rule_ids = finding_rules.allowed_rule_ids(contract["rules"])
    except finding_rules.FindingRuleError as exc:
        raise ReviewCacheWriteError(str(exc)) from exc
    return {
        "content_sha": compute_bead_content_sha.compute_content_sha(
            bead, label_families=contract["label_families"]
        ),
        "reviewer_sha": compute_bead_content_sha.compute_reviewer_sha(
            reviewer_skill_path
        ),
        "contract_sha": contract["contract_sha"],
        "allowed_rule_ids": allowed_rule_ids,
    }


def _validate_bound_result(
    review_result: dict[str, Any],
    *,
    bead_id: str,
    shas: dict[str, Any],
) -> None:
    try:
        review_contract.validate_review_result(
            review_result,
            expected_bead_id=bead_id,
            expected_digest=shas["content_sha"],
            expected_reviewer_sha=shas["reviewer_sha"],
            expected_contract_sha=shas["contract_sha"],
            allowed_rule_ids=shas["allowed_rule_ids"],
        )
    except review_contract.ReviewContractError as exc:
        raise ReviewCacheWriteError(str(exc)) from exc


def _stamp(
    review_result: dict[str, Any], *, timestamp: str | None = None
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "reviewed_at": timestamp
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": review_result["profile"],
        "outcome": review_result["outcome"],
        "content_sha": review_result["reviewed_digest"],
        "reviewer_sha": review_result["reviewer_sha"],
        "contract_sha": review_result["contract_sha"],
        "finding_ids": sorted(
            {finding["finding_id"] for finding in review_result["findings"]}
        ),
        "finding_rule_ids": sorted(
            {finding["rule_id"] for finding in review_result["findings"]}
        ),
    }


def write_review_cache(
    *,
    review_result: dict[str, Any],
    repo_root: str | Path,
    reviewer_skill_path: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Write metadata.review after two live revision-bound validations."""
    if review_result.get("outcome") == "unavailable":
        raise ReviewCacheWriteError("unavailable review results cannot be stamped")
    bead_id = str(review_result.get("bead_id") or "").strip()
    if not bead_id:
        raise ReviewCacheWriteError("review bead_id is required")
    root = Path(repo_root).expanduser().resolve()

    first_bead = load_live_bead(bead_id, root)
    first_id = str(first_bead.get("id") or bead_id)
    first_shas = compute_review_shas(first_bead, root, reviewer_skill_path)
    _validate_bound_result(review_result, bead_id=first_id, shas=first_shas)

    review = _stamp(review_result, timestamp=timestamp)

    second_bead = load_live_bead(bead_id, root)
    second_id = str(second_bead.get("id") or bead_id)
    second_shas = compute_review_shas(second_bead, root, reviewer_skill_path)
    _validate_bound_result(review_result, bead_id=second_id, shas=second_shas)

    result = _run_bd(
        [
            "update",
            bead_id,
            "--set-metadata",
            f"review={json.dumps(review, ensure_ascii=True, sort_keys=True)}",
        ],
        repo_root=root,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "bd update failed"
        raise ReviewCacheWriteError(
            f"metadata review write failed for {bead_id}: {detail}"
        )
    return {"bead_id": bead_id, "review": review}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--result-file",
        type=Path,
        help="Typed review-result JSON; omit to read JSON from stdin.",
    )
    parser.add_argument("--reviewer-skill-path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.result_file:
            review_result = json.loads(args.result_file.read_text(encoding="utf-8"))
        else:
            review_result = json.load(sys.stdin)
        payload = write_review_cache(
            review_result=review_result,
            repo_root=args.repo_root,
            reviewer_skill_path=args.reviewer_skill_path,
        )
    except (
        OSError,
        json.JSONDecodeError,
        ReviewCacheWriteError,
    ) as exc:
        sys.stderr.write(f"write_review_cache.py: ERROR: {exc}\n")
        return 1
    print(json.dumps({"status": "ok", **payload}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
