#!/usr/bin/env python3
"""Search open hosted issues and Open Brain for duplicates of a draft before mutation.

Usage::

    issue_history.py "<draft goal or description>" --repo <registry-prefix>

The open issues come from ``ccore tracker list --repo <prefix>``; each is scored by
token overlap between the search text and the issue title plus body. Memories come
from ``ob --json search`` when the Open Brain CLI is installed. The result is JSON::

    {"open_issues": [{"number", "title", "url", "score"}],
     "match_fields": ["title", "body"] | ["title"] | [],
     "open_brain_memories": [...]}

``match_fields`` names the issue fields the search compared. ``ccore tracker list``
returns issue bodies on GitHub and Forgejo since ccore 2026.9.18; when any listed issue
lacks a body (an older ccore), duplicates can only match on the title (``["title"]``).
Issues are not hydrated one by one. An empty issue list compares nothing (``[]``).

A failing tracker call is a loud error (non-zero exit, message on stderr): intake
must not treat "could not search" as "no duplicate".
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from typing import Any, Callable

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

TrackerRunner = Callable[..., subprocess.CompletedProcess[str]]
MemoryRunner = Callable[[str], list[dict[str, object]]]


def _tokens(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS}


def _list_open_issues(repo: str, tracker_runner: TrackerRunner) -> list[dict[str, Any]]:
    argv = ["ccore", "tracker", "list", "--repo", repo]
    label = " ".join(argv)
    try:
        result = tracker_runner(argv, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"{label} could not run: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or f"exit {result.returncode}"
        raise RuntimeError(f"{label} failed: {detail}")
    try:
        payload = json.loads(result.stdout or "", strict=False)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("status") not in {"ok", "warning"}:
        summary = payload.get("summary") if isinstance(payload, dict) else None
        raise RuntimeError(f"{label} failed: {summary or 'unexpected output'}")
    data = payload.get("data")
    issues = data.get("issues") if isinstance(data, dict) else None
    if not isinstance(issues, list):
        raise RuntimeError(f"{label} returned no issue list")
    return [issue for issue in issues if isinstance(issue, dict)]


def _match_fields(issues: list[dict[str, Any]]) -> list[str]:
    """The issue fields the search could compare, given what the list payload carried."""
    if not issues:
        return []
    if all(isinstance(issue.get("body"), str) for issue in issues):
        return ["title", "body"]
    return ["title"]


def _related_open_issues(
    text: str, *, issues: list[dict[str, Any]]
) -> list[dict[str, object]]:
    query_tokens = _tokens(text)
    related: list[dict[str, object]] = []
    for issue in issues:
        haystack = f"{issue.get('title') or ''} {issue.get('body') or ''}"
        score = len(query_tokens & _tokens(haystack))
        if score <= 0:
            continue
        related.append(
            {
                "number": issue.get("number"),
                "title": str(issue.get("title") or ""),
                "url": str(issue.get("html_url") or issue.get("url") or ""),
                "score": score,
            }
        )
    return sorted(related, key=lambda item: int(item["score"]), reverse=True)


def search_open_brain(text: str) -> list[dict[str, object]]:
    """Related memories from the Open Brain CLI, or [] when it is not installed."""
    if shutil.which("ob") is None:
        return []
    # --json is a global flag on the ob command (before the subcommand).
    result = subprocess.run(
        ["ob", "--json", "search", text],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        print(f"[issue_history] ob search failed (exit {result.returncode}): {detail}", file=sys.stderr)
        return []
    loaded = json.loads(result.stdout or "[]")
    # ob --json search returns {"total": N, "results": [...]} or a plain list.
    if isinstance(loaded, dict):
        results = loaded.get("results", [])
        return results if isinstance(results, list) else []
    return loaded if isinstance(loaded, list) else []


def query_history(
    text: str,
    *,
    repo: str,
    tracker_runner: TrackerRunner | None = None,
    memory_runner: MemoryRunner | None = None,
) -> dict[str, list[Any]]:
    issues = _list_open_issues(repo, tracker_runner or subprocess.run)
    return {
        "open_issues": _related_open_issues(text, issues=issues),
        "match_fields": _match_fields(issues),
        "open_brain_memories": (memory_runner or search_open_brain)(text),
    }


def main(
    argv: list[str] | None = None,
    *,
    tracker_runner: TrackerRunner | None = None,
    memory_runner: MemoryRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("text", help="Draft goal or description to search for")
    parser.add_argument(
        "--repo",
        required=True,
        help="Registry prefix of the target repository (as accepted by ccore tracker)",
    )
    args = parser.parse_args(argv)
    try:
        result = query_history(
            args.text,
            repo=args.repo,
            tracker_runner=tracker_runner,
            memory_runner=memory_runner,
        )
    except RuntimeError as exc:
        print(f"issue_history: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
