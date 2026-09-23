#!/usr/bin/env python3
"""
aggregate_debriefs — Merge multiple parsed debrief dicts into one.

Reads a JSON array of debrief dicts from stdin, merges the four list fields
across all entries, and writes the merged result as a JSON object to stdout.

Each input dict must conform to the shape produced by parse_debrief.py:
    {
        "key_decisions": [...],
        "challenges_encountered": [...],
        "surprising_findings": [...],
        "follow_up_items": [...]
    }

The output is a single merged dict with the same four keys, where each list
is the concatenation of the corresponding lists from all input dicts.

Exit codes:
    0  Success (including empty input array → empty lists)
    1  Invalid JSON on stdin

Usage:
    echo '[{"key_decisions": ["foo"], ...}, ...]' | python3 aggregate_debriefs.py
    cat debriefs.json | python3 aggregate_debriefs.py
"""

import json
import sys


_KEYS = ["key_decisions", "challenges_encountered", "surprising_findings", "follow_up_items"]


def aggregate(debriefs: list[dict]) -> dict:
    """Merge a list of debrief dicts into a single merged dict.

    Args:
        debriefs: List of debrief dicts, each with the four canonical keys.

    Returns:
        A single dict with each key containing the concatenated lists from
        all input dicts.
    """
    merged = {k: [] for k in _KEYS}
    for debrief in debriefs:
        for k in _KEYS:
            merged[k].extend(debrief.get(k, []))
    return merged


def main() -> None:
    """Read JSON array from stdin, merge debrief dicts, write JSON to stdout."""
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON on stdin: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print("Error: Input must be a JSON array of debrief dicts.", file=sys.stderr)
        sys.exit(1)

    merged = aggregate(data)
    print(json.dumps(merged, ensure_ascii=False))


if __name__ == "__main__":
    main()
