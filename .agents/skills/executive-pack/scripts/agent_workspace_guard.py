#!/usr/bin/env -S uv run python
"""Fail closed before a file-writing agent targets the wrong Git worktree."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# A worktree is admitted by declared ownership. Self-managed means this delivery
# created it and will clean it up; provider-owned means an external coding
# provider created it and stays responsible for retiring it.
#
# Two vocabularies name the same two facts, and both have to be readable here.
# `self` and `provider:<id>` are this Library's spellings. `session-close` and
# `t3code` are what `ccore` Session Close actually writes into the durable
# `worktree_owner` field, and ccore's own cleanup reads any value other than
# `session-close` as provider-owned. A guard that understood only the Library
# spellings could not classify the values the system of record writes.
#
# The guard never infers ownership from a path. The recording side may use
# provider signals -- ccore detects `t3code` from a `/.t3/` path at record time
# -- but every decision here reads the recorded field. The one location rule is
# the converse: a declared self-managed worktree must live under the canonical
# root. Without it `self` is the default, so a provider worktree passed with no
# owner would be admitted as self-managed and later cleaned by a non-owner.
# Provider-owned worktrees are deliberately exempt: their location is their
# owner's business.
SELF_OWNER = "self"
CCORE_SELF_OWNER = "session-close"
SELF_MANAGED_OWNERS = frozenset({SELF_OWNER, CCORE_SELF_OWNER})
# Bare provider spellings `ccore` emits. Kept closed rather than "anything that
# is not self": an unknown bare token is far more likely a typo than a new
# provider, and a typo must be refused, not silently granted the exemption from
# the canonical-root rule.
CCORE_PROVIDER_OWNERS = frozenset({"t3code"})
_PROVIDER_RE = re.compile(r"^provider:[a-z0-9][a-z0-9._-]*$")
DEFAULT_SELF_MANAGED_ROOT = Path("~/code/.worktrees")

SELF_MANAGED = "self_managed"
PROVIDER_OWNED = "provider"


def ownership_kind(owner: str) -> str | None:
    """Which ownership a recorded owner value names, or None when unrecognized."""
    value = (owner or "").strip()
    if value in SELF_MANAGED_OWNERS:
        return SELF_MANAGED
    if value in CCORE_PROVIDER_OWNERS or _PROVIDER_RE.match(value):
        return PROVIDER_OWNED
    return None


def _result(code: str, **fields: Any) -> dict[str, Any]:
    return {
        "status": "ok" if code == "WORKSPACE_VALID" else "error",
        "code": code,
        **fields,
    }


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _within(candidate: Path, root: Path) -> bool:
    """Containment on fully resolved paths.

    Both sides are resolved here rather than relying on the caller having done
    it. `relative_to` is pure string arithmetic, so an unresolved `..` segment
    or a symlink on either side would answer a question about spelling instead
    of about location.
    """
    try:
        candidate.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True


def _resolved_git_path(cwd: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def validate_workspace(
    *,
    invocation_dir: Path,
    expected_workspace: Path,
    require_linked_worktree: bool,
    expected_branch: str | None = None,
    targets: list[Path] | None = None,
    worktree_owner: str | None = None,
    self_managed_root: Path | None = None,
) -> dict[str, Any]:
    """Validate worktree identity, ownership, and optional file-write targets."""
    owner = (worktree_owner or SELF_OWNER).strip()
    ownership = ownership_kind(owner)
    canonical_root = Path(
        self_managed_root if self_managed_root is not None else DEFAULT_SELF_MANAGED_ROOT
    ).expanduser()

    def _owned(code: str, **fields: Any) -> dict[str, Any]:
        return _result(
            code, worktree_owner=owner, ownership=ownership, **fields
        )

    if ownership is None:
        return _owned(
            "WORKTREE_OWNER_INVALID",
            expected_workspace=str(expected_workspace),
        )

    invocation_dir = invocation_dir.resolve()
    expected_workspace = expected_workspace.resolve()
    root_probe = _git(invocation_dir, "rev-parse", "--show-toplevel")
    if root_probe.returncode != 0:
        return _owned(
            "NOT_A_GIT_WORKSPACE",
            expected_workspace=str(expected_workspace),
        )
    workspace_root = Path(root_probe.stdout.strip()).resolve()
    common_probe = _git(invocation_dir, "rev-parse", "--git-common-dir")
    git_dir_probe = _git(invocation_dir, "rev-parse", "--absolute-git-dir")
    branch_probe = _git(invocation_dir, "symbolic-ref", "--quiet", "--short", "HEAD")
    if common_probe.returncode != 0 or git_dir_probe.returncode != 0:
        return _owned(
            "GIT_IDENTITY_UNAVAILABLE",
            workspace_root=str(workspace_root),
            expected_workspace=str(expected_workspace),
        )
    common_dir = _resolved_git_path(invocation_dir, common_probe.stdout.strip())
    git_dir = _resolved_git_path(invocation_dir, git_dir_probe.stdout.strip())
    branch = branch_probe.stdout.strip() if branch_probe.returncode == 0 else ""

    if workspace_root != expected_workspace:
        return _owned(
            "WORKSPACE_ROOT_MISMATCH",
            workspace_root=str(workspace_root),
            expected_workspace=str(expected_workspace),
            git_common_dir=str(common_dir),
            git_dir=str(git_dir),
            branch=branch,
        )
    if require_linked_worktree and git_dir == common_dir:
        return _owned(
            "MAIN_CHECKOUT_FORBIDDEN",
            workspace_root=str(workspace_root),
            expected_workspace=str(expected_workspace),
            git_common_dir=str(common_dir),
            git_dir=str(git_dir),
            branch=branch,
        )
    if not branch:
        return _owned(
            "DETACHED_HEAD_FORBIDDEN",
            workspace_root=str(workspace_root),
            expected_workspace=str(expected_workspace),
            git_common_dir=str(common_dir),
            git_dir=str(git_dir),
            branch=branch,
        )
    if expected_branch and branch != expected_branch:
        return _owned(
            "BRANCH_MISMATCH",
            workspace_root=str(workspace_root),
            expected_workspace=str(expected_workspace),
            git_common_dir=str(common_dir),
            git_dir=str(git_dir),
            branch=branch,
            expected_branch=expected_branch,
        )
    # Only a task worktree is held to the canonical root. A caller that
    # explicitly admits the main checkout is not claiming a task worktree at
    # all, and the canonical repository checkout never lives under that root.
    if (
        require_linked_worktree
        and ownership == SELF_MANAGED
        and not _within(workspace_root, canonical_root)
    ):
        return _owned(
            "SELF_MANAGED_WORKTREE_OUTSIDE_ROOT",
            workspace_root=str(workspace_root),
            expected_workspace=str(expected_workspace),
            git_common_dir=str(common_dir),
            git_dir=str(git_dir),
            branch=branch,
            self_managed_root=str(canonical_root),
        )
    resolved_targets: list[str] = []
    for target in targets or []:
        resolved_target = (
            target.resolve()
            if target.is_absolute()
            else (workspace_root / target).resolve()
        )
        try:
            resolved_target.relative_to(workspace_root)
        except ValueError:
            return _owned(
                "TARGET_OUTSIDE_WORKSPACE",
                workspace_root=str(workspace_root),
                expected_workspace=str(expected_workspace),
                git_common_dir=str(common_dir),
                git_dir=str(git_dir),
                branch=branch,
                target=str(resolved_target),
            )
        resolved_targets.append(str(resolved_target))
    return _owned(
        "WORKSPACE_VALID",
        workspace_root=str(workspace_root),
        expected_workspace=str(expected_workspace),
        git_common_dir=str(common_dir),
        git_dir=str(git_dir),
        branch=branch,
        targets=resolved_targets,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a file-writing agent's active Git worktree."
    )
    parser.add_argument("--expected-workspace", type=Path, required=True)
    parser.add_argument("--expected-branch")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        type=Path,
        help="Planned write target; repeat for every file the agent may modify.",
    )
    parser.add_argument(
        "--allow-main-checkout",
        action="store_true",
        help="Allow the canonical main checkout instead of requiring a linked worktree.",
    )
    parser.add_argument(
        "--worktree-owner",
        default=SELF_OWNER,
        help=(
            "Who owns this worktree's lifecycle. Self-managed: 'self' or the "
            "ccore-recorded 'session-close'. Provider-owned: 'provider:<id>' or "
            "a ccore-recorded provider value such as 't3code' (default: self)."
        ),
    )
    parser.add_argument(
        "--self-managed-root",
        type=Path,
        default=DEFAULT_SELF_MANAGED_ROOT,
        help=(
            "Canonical root a 'self' worktree must live under "
            f"(default: {DEFAULT_SELF_MANAGED_ROOT}). Ignored for provider owners."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = validate_workspace(
        invocation_dir=Path.cwd(),
        expected_workspace=args.expected_workspace,
        require_linked_worktree=not args.allow_main_checkout,
        expected_branch=args.expected_branch,
        targets=args.target,
        worktree_owner=args.worktree_owner,
        self_managed_root=args.self_managed_root,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
