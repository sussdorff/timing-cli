#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable


TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "in",
    "of",
    "or",
    "the",
    "to",
    "with",
}
BdRunner = Callable[..., subprocess.CompletedProcess[str]]
MemoryRunner = Callable[[str], list[dict[str, object]]]


def _tokens(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS}


def _load_closed_beads(repo: Path, bd_runner: BdRunner) -> list[dict[str, object]]:
    cmd = ["bd", "list", "--status=closed", "--json"]
    result = bd_runner(
        cmd,
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "bd list failed")
    loaded = json.loads(result.stdout)
    if not isinstance(loaded, list):
        raise RuntimeError("bd list did not return a JSON array")
    return loaded


def _score_bead(query_tokens: set[str], bead: dict[str, object]) -> int:
    text = f"{bead.get('title', '')} {bead.get('description', '')}"
    return len(query_tokens & _tokens(text))


def _related_closed_beads(
    description: str, *, repo: Path, bd_runner: BdRunner
) -> list[dict[str, object]]:
    query_tokens = _tokens(description)
    related: list[dict[str, object]] = []
    for bead in _load_closed_beads(repo, bd_runner):
        score = _score_bead(query_tokens, bead)
        if score > 0:
            related.append(
                {
                    "id": str(bead.get("id", "")),
                    "title": str(bead.get("title", "")),
                    "score": score,
                }
            )
    return sorted(related, key=lambda item: item["score"], reverse=True)


def search_open_brain(description: str) -> list[dict[str, object]]:
    if shutil.which("ob") is None:
        return []
    # --json is a global flag on the ob command (before the subcommand)
    result = subprocess.run(
        ["ob", "--json", "search", description],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"[query_history] ob search failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}", file=sys.stderr)
        return []
    loaded = json.loads(result.stdout or "[]")
    # ob --json search returns {"total": N, "results": [...]} or a plain list
    if isinstance(loaded, dict):
        return loaded.get("results", [])
    return loaded if isinstance(loaded, list) else []


def query_history(
    description: str,
    *,
    repo: Path | str = ".",
    bd_runner: BdRunner = subprocess.run,
    memory_runner: MemoryRunner = search_open_brain,
) -> dict[str, list[dict[str, object]]]:
    return {
        "closed_beads": _related_closed_beads(
            description,
            repo=Path(repo),
            bd_runner=bd_runner,
        ),
        "open_brain_memories": memory_runner(description),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Query related historical context.")
    parser.add_argument("description", help="Bead description or search text")
    parser.add_argument("--repo", default=".", help="Repository path for bd")
    args = parser.parse_args()

    print(json.dumps(query_history(args.description, repo=args.repo), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
