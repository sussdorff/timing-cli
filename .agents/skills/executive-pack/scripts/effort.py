#!/usr/bin/env python3
"""
effort.py — skill:executive-pack effort operation entrypoint.

Self-locating thin wrapper around classify_effort.py. Callers resolve
the installed executive-pack runtime and call this script; classify_effort.py is
found from __file__ without any additional path resolution.

Usage:
  uv run python "$EXECUTIVE_PACK_RUNTIME/scripts/effort.py" <bead-id> [--force]

EXPLICIT invocation only. On a cache miss, classify_effort.py performs a
write + LLM call. Never invoke this from read-only or
casual effort queries.
"""

import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_CLASSIFY = _SCRIPT_DIR / "classify_effort.py"


def main() -> int:
    if not _CLASSIFY.exists():
        print(
            f"ERROR: classify_effort.py not found at {_CLASSIFY}",
            file=sys.stderr,
        )
        return 1
    return subprocess.call([sys.executable, str(_CLASSIFY)] + sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
