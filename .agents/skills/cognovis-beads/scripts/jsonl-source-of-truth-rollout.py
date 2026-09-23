#!/usr/bin/env python3
"""Align bd repository configs with Dolt-as-source-of-truth policy.

The script intentionally targets only real bd repository configs at
`<repo>/.beads/config.yaml`. It does not edit nested Dolt server configs such as
`<repo>/.beads/dolt/config.yaml`, even though broad find commands can match them.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


JSONL_EXPORT_PATH = ".beads/issues.jsonl"
SOURCE_OF_TRUTH_COMMENT = "# Disable JSONL auto-import; Dolt is the source of truth."
GITIGNORE_COMMENT = "# Beads JSONL export is local; Dolt is the source of truth."


@dataclass(frozen=True)
class RolloutUpdate:
    repo: Path
    config_path: Path
    config_action: str
    config_changed: bool
    gitignore_action: str = "skipped"
    gitignore_changed: bool = False
    git_index_action: str = "skipped"
    git_index_changed: bool = False
    jsonl_file_action: str = "skipped"
    jsonl_file_changed: bool = False
    error: str | None = None

    @property
    def changed(self) -> bool:
        return (
            self.config_changed
            or self.gitignore_changed
            or self.git_index_changed
            or self.jsonl_file_changed
        )


def discover_configs(root: Path, max_depth: int) -> list[Path]:
    """Find `<repo>/.beads/config.yaml` files below root."""
    root = root.expanduser().resolve()
    if not root.exists():
        return []

    configs: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            continue

        if depth >= max_depth:
            dirnames[:] = []

        if current_path.name in {".claude", ".git", "node_modules", ".venv", "__pycache__"}:
            dirnames[:] = []
            continue

        if current_path.name == ".beads" and "config.yaml" in filenames:
            file_depth = depth + 1
            if file_depth <= max_depth:
                configs.append(current_path / "config.yaml")
            dirnames[:] = []

    return sorted(configs)


def _split_newline(line: str) -> tuple[str, str]:
    body = line.rstrip("\r\n")
    return body, line[len(body) :]


def ensure_bool_setting(
    text: str,
    *,
    key: str,
    value: bool,
    insert_comment: str | None = None,
) -> tuple[str, str, bool]:
    """Return updated text, action label, and changed flag for a top-level bool."""
    expected = "true" if value else "false"
    key_re = re.escape(key)
    active_re = re.compile(
        rf"^(?P<indent>\s*){key_re}\s*:\s*(?P<value>true|false)\s*(?P<comment>#.*)?$"
    )
    commented_re = re.compile(
        rf"^(?P<indent>\s*)#\s*{key_re}\s*:\s*(?:true|false)\s*(?P<comment>#.*)?$"
    )
    lines = text.splitlines(keepends=True)

    for index, line in enumerate(lines):
        body, newline = _split_newline(line)
        match = active_re.match(body)
        if not match:
            continue

        if match.group("value") == expected:
            return text, f"{key}:already-ok", False

        comment = match.group("comment") or ""
        separator = " " if comment else ""
        lines[index] = (
            f"{match.group('indent')}{key}: {expected}{separator}{comment}{newline or '\n'}"
        )
        return "".join(lines), f"{key}:updated-active", True

    for index, line in enumerate(lines):
        body, newline = _split_newline(line)
        match = commented_re.match(body)
        if not match:
            continue

        lines.insert(index + 1, f"{match.group('indent')}{key}: {expected}{newline or '\n'}")
        return "".join(lines), f"{key}:inserted-after-comment", True

    suffix = "" if not text or text.endswith(("\n", "\r")) else "\n"
    comment_line = f"{insert_comment}\n" if insert_comment else ""
    block = f"{suffix}\n{comment_line}{key}: {expected}\n"
    return text + block, f"{key}:appended", True


def ensure_beads_config(text: str) -> tuple[str, str, bool]:
    """Set the bd config flags that keep Dolt authoritative over JSONL exports."""
    changed = False
    actions: list[str] = []
    settings = [
        ("no-auto-import", True, SOURCE_OF_TRUTH_COMMENT),
        ("import.auto", False, None),
        ("export.auto", False, None),
        ("export.git-add", False, None),
    ]

    updated = text
    for key, value, comment in settings:
        updated, action, did_change = ensure_bool_setting(
            updated,
            key=key,
            value=value,
            insert_comment=comment,
        )
        actions.append(action)
        changed = changed or did_change

    return updated, ",".join(actions), changed


def _repo_for_config(path: Path) -> Path:
    return path.parent.parent


def _ensure_gitignore(repo: Path, *, dry_run: bool) -> tuple[str, bool, str | None]:
    path = repo / ".gitignore"
    try:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        return "error", False, str(exc)

    lines = {line.strip() for line in text.splitlines()}
    if JSONL_EXPORT_PATH in lines:
        return "already-ignored", False, None

    suffix = "" if not text or text.endswith(("\n", "\r")) else "\n"
    updated = f"{text}{suffix}\n{GITIGNORE_COMMENT}\n{JSONL_EXPORT_PATH}\n"
    if not dry_run:
        try:
            path.write_text(updated, encoding="utf-8")
        except OSError as exc:
            return "error", False, str(exc)

    return "would-ignore" if dry_run else "ignored", True, None


def _git_tracks_jsonl(repo: Path) -> tuple[bool, str | None]:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--error-unmatch", JSONL_EXPORT_PATH],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, None
    if result.returncode == 1:
        return False, None
    return False, (result.stderr or result.stdout).strip()


def _untrack_jsonl(repo: Path, *, dry_run: bool) -> tuple[str, bool, str | None]:
    git_dir = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
    )
    if git_dir.returncode != 0:
        return "not-a-git-repo", False, None

    tracked, error = _git_tracks_jsonl(repo)
    if error:
        return "error", False, error
    if not tracked:
        return "already-untracked", False, None
    if dry_run:
        return "would-untrack", True, None

    result = subprocess.run(
        ["git", "-C", str(repo), "rm", "--cached", "-f", "--", JSONL_EXPORT_PATH],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "error", False, (result.stderr or result.stdout).strip()
    return "untracked", True, None


def _remove_jsonl_file(repo: Path, *, dry_run: bool) -> tuple[str, bool, str | None]:
    path = repo / JSONL_EXPORT_PATH
    if not path.exists():
        return "already-absent", False, None
    if dry_run:
        return "would-remove", True, None
    try:
        path.unlink()
    except OSError as exc:
        return "error", False, str(exc)
    return "removed", True, None


def update_config(path: Path, *, dry_run: bool, cleanup_jsonl: bool) -> RolloutUpdate:
    repo = _repo_for_config(path)
    try:
        original = path.read_text(encoding="utf-8")
    except OSError as exc:
        return RolloutUpdate(
            repo=repo,
            config_path=path,
            config_action="error",
            config_changed=False,
            error=str(exc),
        )

    updated, config_action, config_changed = ensure_beads_config(original)
    if config_changed and not dry_run:
        try:
            path.write_text(updated, encoding="utf-8")
        except OSError as exc:
            return RolloutUpdate(
                repo=repo,
                config_path=path,
                config_action="error",
                config_changed=False,
                error=str(exc),
            )

    if not cleanup_jsonl:
        return RolloutUpdate(
            repo=repo,
            config_path=path,
            config_action=config_action,
            config_changed=config_changed,
        )

    gitignore_action, gitignore_changed, gitignore_error = _ensure_gitignore(
        repo, dry_run=dry_run
    )
    if gitignore_error:
        return RolloutUpdate(
            repo=repo,
            config_path=path,
            config_action=config_action,
            config_changed=config_changed,
            gitignore_action=gitignore_action,
            gitignore_changed=gitignore_changed,
            error=gitignore_error,
        )

    git_index_action, git_index_changed, git_index_error = _untrack_jsonl(
        repo, dry_run=dry_run
    )
    if git_index_error:
        return RolloutUpdate(
            repo=repo,
            config_path=path,
            config_action=config_action,
            config_changed=config_changed,
            gitignore_action=gitignore_action,
            gitignore_changed=gitignore_changed,
            git_index_action=git_index_action,
            git_index_changed=git_index_changed,
            error=git_index_error,
        )

    jsonl_file_action, jsonl_file_changed, jsonl_file_error = _remove_jsonl_file(
        repo, dry_run=dry_run
    )
    if jsonl_file_error:
        return RolloutUpdate(
            repo=repo,
            config_path=path,
            config_action=config_action,
            config_changed=config_changed,
            gitignore_action=gitignore_action,
            gitignore_changed=gitignore_changed,
            git_index_action=git_index_action,
            git_index_changed=git_index_changed,
            jsonl_file_action=jsonl_file_action,
            jsonl_file_changed=jsonl_file_changed,
            error=jsonl_file_error,
        )

    return RolloutUpdate(
        repo=repo,
        config_path=path,
        config_action=config_action,
        config_changed=config_changed,
        gitignore_action=gitignore_action,
        gitignore_changed=gitignore_changed,
        git_index_action=git_index_action,
        git_index_changed=git_index_changed,
        jsonl_file_action=jsonl_file_action,
        jsonl_file_changed=jsonl_file_changed,
    )


def run(paths: Iterable[Path], *, dry_run: bool, cleanup_jsonl: bool) -> list[RolloutUpdate]:
    return [
        update_config(path, dry_run=dry_run, cleanup_jsonl=cleanup_jsonl)
        for path in paths
    ]


def _summary(results: list[RolloutUpdate]) -> dict[str, int]:
    summary = {
        "total": len(results),
        "changed": 0,
        "already_ok": 0,
        "errors": 0,
    }
    for result in results:
        if result.error:
            summary["errors"] += 1
        elif result.changed:
            summary["changed"] += 1
        else:
            summary["already_ok"] += 1
    return summary


def _print_text(results: list[RolloutUpdate], *, dry_run: bool) -> None:
    verb = "would update" if dry_run else "updated"
    for result in results:
        if result.error:
            print(f"ERROR {result.repo}: {result.error}", file=sys.stderr)
        elif result.changed:
            print(
                f"{verb} {result.repo} "
                f"(config={result.config_action}; "
                f"gitignore={result.gitignore_action}; "
                f"git-index={result.git_index_action}; "
                f"jsonl-file={result.jsonl_file_action})"
            )

    summary = _summary(results)
    print(
        f"total={summary['total']} changed={summary['changed']} "
        f"already_ok={summary['already_ok']} errors={summary['errors']}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Align discovered bd repos with Dolt-as-source-of-truth policy."
    )
    parser.add_argument("--root", type=Path, default=Path.home() / "code")
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--cleanup-jsonl",
        action="store_true",
        help=(
            "Also ignore .beads/issues.jsonl and remove it from the git index. "
            "The working-tree export file is removed so empty DB recovery cannot "
            "re-seed from a stale export."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write files; exit 1 if any selected update is needed.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dry_run = bool(args.dry_run or args.check)
    configs = discover_configs(args.root, args.max_depth)
    results = run(configs, dry_run=dry_run, cleanup_jsonl=args.cleanup_jsonl)
    summary = _summary(results)

    if args.json:
        print(
            json.dumps(
                {
                    "summary": summary,
                    "results": [
                        {
                            "repo": str(result.repo),
                            "config_path": str(result.config_path),
                            "config_action": result.config_action,
                            "config_changed": result.config_changed,
                            "gitignore_action": result.gitignore_action,
                            "gitignore_changed": result.gitignore_changed,
                            "git_index_action": result.git_index_action,
                            "git_index_changed": result.git_index_changed,
                            "jsonl_file_action": result.jsonl_file_action,
                            "jsonl_file_changed": result.jsonl_file_changed,
                            "changed": result.changed,
                            "error": result.error,
                        }
                        for result in results
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        _print_text(results, dry_run=dry_run)

    if summary["errors"]:
        return 2
    if args.check and summary["changed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
