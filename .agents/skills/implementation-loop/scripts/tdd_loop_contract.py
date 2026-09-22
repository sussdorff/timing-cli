#!/usr/bin/env python3
"""Detect implementation-loop TDD contract violations.

RED/GREEN remains behavioral. This helper classifies whether an implementer
slice edited the declared test tree (not GREEN) and whether a tdd-test-author
slice wrote outside that tree (not accepted RED).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any


class PathClassificationError(ValueError):
    """A path is empty, the repo root, or outside the repository."""


def repo_relative_path(path: str, repo_root: Path) -> PurePosixPath:
    """Return a repo-relative path after resolving `.` / `..` and symlinks."""
    if not str(path).strip() or str(path).strip() in {".", ".."}:
        raise PathClassificationError("empty or repo-root path")
    repo = repo_root.resolve()
    raw = Path(path)
    candidate = raw.resolve() if raw.is_absolute() else (repo / raw).resolve()
    try:
        relative = candidate.relative_to(repo)
    except ValueError as exc:
        raise PathClassificationError("path is outside the repository") from exc
    if not relative.parts or relative.as_posix() == ".":
        raise PathClassificationError("empty or repo-root path")
    return PurePosixPath(relative.as_posix())


def _under_tree(candidate: PurePosixPath, tree: PurePosixPath) -> bool:
    return candidate == tree or tree in candidate.parents


def paths_under_test_tree(
    changed_paths: list[str],
    test_tree: str,
    *,
    repo_root: Path | None = None,
) -> list[str]:
    root = (repo_root or Path.cwd()).resolve()
    tree = repo_relative_path(test_tree, root)
    hits: list[str] = []
    for raw in changed_paths:
        try:
            candidate = repo_relative_path(raw, root)
        except PathClassificationError:
            continue
        if _under_tree(candidate, tree):
            hits.append(raw)
    return hits


def paths_outside_test_tree(
    changed_paths: list[str],
    test_tree: str,
    *,
    repo_root: Path | None = None,
) -> list[str]:
    under = set(
        paths_under_test_tree(changed_paths, test_tree, repo_root=repo_root)
    )
    return [raw for raw in changed_paths if raw not in under]


def _invalid_tree_result(reason: str, green_exit: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "invalid", "reason": reason, "paths": []}
    if green_exit is not None:
        payload["green_exit"] = green_exit
    return payload


def classify_implementer_slice(
    *,
    changed_paths: list[str],
    test_tree: str,
    green_exit: int,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path.cwd()).resolve()
    try:
        repo_relative_path(test_tree, root)
    except PathClassificationError as exc:
        return _invalid_tree_result(str(exc), green_exit)
    edits = paths_under_test_tree(changed_paths, test_tree, repo_root=root)
    if edits:
        return {
            "status": "contract_violation",
            "reason": "implementer edited the test tree",
            "paths": edits,
            "green_exit": green_exit,
        }
    if green_exit != 0:
        return {
            "status": "not_green",
            "reason": "GREEN command did not exit 0",
            "paths": [],
            "green_exit": green_exit,
        }
    return {
        "status": "green",
        "reason": "implementer did not edit the test tree",
        "paths": [],
        "green_exit": green_exit,
    }


def classify_author_slice(
    *,
    changed_paths: list[str],
    test_tree: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path.cwd()).resolve()
    try:
        repo_relative_path(test_tree, root)
    except PathClassificationError as exc:
        return _invalid_tree_result(str(exc))
    outside = paths_outside_test_tree(changed_paths, test_tree, repo_root=root)
    if outside:
        return {
            "status": "contract_violation",
            "reason": "tdd-test-author edited outside the declared test tree",
            "paths": outside,
        }
    return {
        "status": "red",
        "reason": "tdd-test-author wrote only under the declared test tree",
        "paths": [],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    classify = sub.add_parser("classify", help="Classify an implementer slice")
    classify.add_argument("--test-tree", required=True)
    classify.add_argument("--green-exit", type=int, required=True)
    classify.add_argument("--changed-path", action="append", default=[])
    classify.add_argument("--repo-root", default=".")
    author = sub.add_parser("classify-author", help="Classify a tdd-test-author slice")
    author.add_argument("--test-tree", required=True)
    author.add_argument("--changed-path", action="append", default=[])
    author.add_argument("--repo-root", default=".")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root)
    if args.command == "classify-author":
        result = classify_author_slice(
            changed_paths=list(args.changed_path),
            test_tree=args.test_tree,
            repo_root=repo_root,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "red" else 1
    result = classify_implementer_slice(
        changed_paths=list(args.changed_path),
        test_tree=args.test_tree,
        green_exit=args.green_exit,
        repo_root=repo_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "green" else 1


if __name__ == "__main__":
    sys.exit(main())
