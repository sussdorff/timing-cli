#!/usr/bin/env python3
"""Prepare explicitly requested live Bead IDs for manual review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

def review_prep(
    bead_ids: list[str],
    repo_root: str | Path,
    *,
    profile: str = "full",
    force: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Return only IDs and profiles; manual reviews never consult reusable gates."""
    del repo_root, force
    return {
        "skip": [],
        "review": [{"beadId": bead_id, "profile": profile} for bead_id in bead_ids],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bead_ids", nargs="+")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--profile", default="full")
    parser.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    result = review_prep(
        args.bead_ids,
        args.repo_root,
        profile=args.profile,
        force=args.force,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
