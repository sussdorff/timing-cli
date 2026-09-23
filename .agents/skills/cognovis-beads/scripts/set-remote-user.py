#!/usr/bin/env python3
"""Set the Dolt RemoteAPI username in a repo_state.json file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Set remotes.origin.params.__DOLT__grpc_username in repo_state.json."
    )
    parser.add_argument("repo_state", type=Path)
    parser.add_argument("username")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data = json.loads(args.repo_state.read_text(encoding="utf-8"))
    origin = data.setdefault("remotes", {}).setdefault("origin", {})
    params = origin.setdefault("params", {})
    params["__DOLT__grpc_username"] = args.username
    args.repo_state.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"set origin RemoteAPI username to {args.username} in {args.repo_state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
