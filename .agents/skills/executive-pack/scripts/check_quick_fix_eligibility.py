#!/usr/bin/env python3
"""Check whether work-order JSON is eligible for quick-fix dispatch."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


ELIGIBLE_EFFORTS = frozenset({"micro", "small"})
ELIGIBLE_TYPES = frozenset({"bug", "chore", "task"})


def extract_bead(payload: Any) -> dict[str, Any]:
    """Return the first work-order dict from tracker or Beads JSON."""
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else {}
    if isinstance(payload, dict):
        return payload
    return {}


def get_effort(bead: dict[str, Any]) -> str:
    metadata = bead.get("metadata") or {}
    return str(metadata.get("effort") or "").strip().lower()


def check_eligibility(bead: dict[str, Any], force_tier: str | None = None) -> tuple[bool, str]:
    if force_tier == "quick":
        return True, "eligible (force-tier=quick)"

    effort = get_effort(bead)
    if effort not in ELIGIBLE_EFFORTS:
        return False, f"-bq rejected: effort={effort!r} not in {sorted(ELIGIBLE_EFFORTS)}."

    bead_type = str(bead.get("issue_type") or bead.get("type") or "").strip().lower()
    if bead_type not in ELIGIBLE_TYPES:
        return False, f"-bq rejected: type={bead_type!r} not in {sorted(ELIGIBLE_TYPES)}."

    return True, "eligible"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check quick-fix eligibility for a bead.")
    parser.add_argument("--force-tier", choices=["quick"], default=None)
    args = parser.parse_args()

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"ELIGIBILITY_CHECK_ERROR: invalid JSON on stdin: {exc}", file=sys.stderr)
        return 2

    bead = extract_bead(payload)
    if not bead:
        print("ELIGIBILITY_CHECK_ERROR: no bead in input", file=sys.stderr)
        return 2

    ok, message = check_eligibility(bead, force_tier=args.force_tier)
    print(message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
