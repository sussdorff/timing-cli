#!/usr/bin/env python3
"""Git fixture helpers for adapter tests."""

import subprocess
from pathlib import Path


def init_main_checkout(repo: Path) -> str:
    """Initialize a plain git checkout and return its initial HEAD SHA."""
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    (repo / "init.txt").write_text("init\n")
    (repo / ".gitignore").write_text(".beads/\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def init_linked_worktree(worktree: Path, *, branch_name: str | None = None) -> str:
    """Create a real linked worktree at worktree and return its initial HEAD SHA.

    By default the linked branch is ``<name>-linked``. Pass ``branch_name`` to
    control the branch name explicitly — e.g. to encode the assigned bead
    identity so ``adapter_role_profile`` accepts the worktree as the assigned
    bead worktree (see ``init_bead_worktree``).
    """
    if worktree.exists():
        if any(worktree.iterdir()):
            raise ValueError(f"worktree path is not empty: {worktree}")
        worktree.rmdir()

    main_checkout = worktree.parent / f"{worktree.name}-main"
    init_main_checkout(main_checkout)
    branch = branch_name or f"{worktree.name}-linked"
    subprocess.run(
        ["git", "-C", str(main_checkout), "worktree", "add", "-b", branch, str(worktree)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def init_bead_worktree(worktree: Path, bead_id: str) -> str:
    """Create a linked worktree whose branch encodes the assigned bead identity.

    Mirrors the repo's real worktree convention (``worktree-bead-<id>``) so that
    ``adapter_role_profile.resolve_role_profile('implementer', bead_id=...)``
    accepts it as the worktree assigned to that bead. Returns the initial HEAD
    SHA.
    """
    return init_linked_worktree(worktree, branch_name=f"worktree-bead-{bead_id}")
