#!/usr/bin/env python3
"""Cognovis-only Beads helpers that complement the upstream bd CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

OVERLAY_START = "<!-- COGNOVIS_OVERLAY_BEGIN -->"
OVERLAY_END = "<!-- COGNOVIS_OVERLAY_END -->"


class SyncError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def render_context() -> str:
    skill_path = Path(__file__).resolve().parents[1] / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")
    if OVERLAY_START not in content or OVERLAY_END not in content:
        raise SyncError(
            "overlay_markers_missing", f"Overlay markers missing in {skill_path}"
        )
    return content.split(OVERLAY_START, 1)[1].split(OVERLAY_END, 1)[0].strip() + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "context", help="Print the Cognovis overlay for upstream bd prime"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "context":
            sys.stdout.write(render_context())
            return 0
    except (OSError, SyncError) as exc:
        code = exc.code if isinstance(exc, SyncError) else "cognovis_beads_error"
        print(f"{code}: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
