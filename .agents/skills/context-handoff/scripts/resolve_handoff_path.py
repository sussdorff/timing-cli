#!/usr/bin/env -S uv run --no-project
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
RELATIVE_DIR = Path(".intake/context-handoff")


def emit_error(
    summary: str,
    code: str,
    message: str,
    *,
    data: dict[str, Any] | None = None,
    next_step: str,
) -> int:
    print(
        json.dumps(
            {
                "status": "error",
                "summary": summary,
                "data": data or {},
                "errors": [{"code": code, "message": message}],
                "next_steps": [next_step],
            }
        )
    )
    return 2


def resolve_session_id(explicit: str | None) -> tuple[str, str] | tuple[None, str]:
    if explicit:
        return explicit, "argument"

    codex_id = os.environ.get("CODEX_THREAD_ID")
    claude_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    claude_active = bool(
        os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT")
    )
    codex_active = bool(
        os.environ.get("CODEX_CI") or os.environ.get("CODEX_CLI_PATH")
    )

    if claude_active:
        return (claude_id, "CLAUDE_CODE_SESSION_ID") if claude_id else (None, "missing")
    if codex_active:
        return (codex_id, "CODEX_THREAD_ID") if codex_id else (None, "missing")
    if codex_id and claude_id:
        return None, "ambiguous"
    if codex_id:
        return codex_id, "CODEX_THREAD_ID"
    if claude_id:
        return claude_id, "CLAUDE_CODE_SESSION_ID"
    return None, "missing"


def git_output(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def resolve_repo_root(explicit: Path | None) -> Path | None:
    if explicit is not None:
        candidate = explicit.resolve()
        if not candidate.is_dir():
            return None
        result = git_output("rev-parse", "--show-toplevel", cwd=candidate)
        if result.returncode != 0 or Path(result.stdout.strip()).resolve() != candidate:
            return None
        return candidate

    result = git_output("rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def is_linked_worktree(repo_root: Path) -> bool:
    result = git_output("rev-parse", "--git-common-dir", cwd=repo_root)
    if result.returncode != 0:
        return False
    common_dir = Path(result.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = repo_root / common_dir
    return common_dir.resolve() != (repo_root / ".git").resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--session-id")
    args = parser.parse_args()

    session_id, source = resolve_session_id(args.session_id)
    if source == "ambiguous":
        return emit_error(
            "Canonical harness session ID is ambiguous",
            "SESSION_ID_AMBIGUOUS",
            "Both Codex and Claude session IDs are present without an active-harness marker.",
            next_step="Pass the exact active harness session ID with --session-id.",
        )
    if not session_id:
        return emit_error(
            "Canonical harness session ID is unavailable",
            "SESSION_ID_UNAVAILABLE",
            (
                "Pass --session-id or expose the active harness's CODEX_THREAD_ID "
                "or CLAUDE_CODE_SESSION_ID."
            ),
            next_step="Obtain the exact session ID from the active harness.",
        )
    if not SESSION_ID.fullmatch(session_id):
        return emit_error(
            "Canonical harness session ID is invalid",
            "SESSION_ID_INVALID",
            "Session ID must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$.",
            next_step="Obtain the exact session ID from the active harness.",
        )

    repo_root = resolve_repo_root(args.repo_root)
    if repo_root is None:
        return emit_error(
            "Repository root is invalid",
            "REPO_ROOT_INVALID",
            "The repository root must exist and equal its Git worktree root.",
            next_step="Run from the target Git worktree or pass its exact root.",
        )

    relative_path = RELATIVE_DIR / f"{session_id}.md"
    path = repo_root / relative_path
    ignored = git_output("check-ignore", "-q", "--", str(relative_path), cwd=repo_root)
    if ignored.returncode != 0:
        return emit_error(
            "Context handoff path is not ignored by Git",
            "HANDOFF_PATH_NOT_IGNORED",
            "Refusing to write conversation context to a path that Git may track.",
            data={
                "relative_path": relative_path.as_posix(),
                "path": str(path),
                "git_ignored": False,
            },
            next_step="Add .intake/context-handoff/ to the repository's Git ignore rules.",
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "summary": "Resolved context handoff path",
                "data": {
                    "session_id": session_id,
                    "source": source,
                    "relative_path": relative_path.as_posix(),
                    "path": str(path),
                    "exists": path.exists(),
                    "git_ignored": True,
                    "worktree_local": is_linked_worktree(repo_root),
                },
                "errors": [],
                "next_steps": [],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
