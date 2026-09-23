#!/usr/bin/env python3
"""Safe worktree lifecycle operations for Cognovis Gas City bug workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Sequence


def _issue_tracker_name(repo_root: str | Path | None = None) -> str | None:
    override = os.environ.get("COGNOVIS_BEADS_REGISTRY")
    registry = Path(override).expanduser() if override else (
        Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        / "cognovis" / "beads-repos.toml"
    )
    try:
        loaded = tomllib.loads(registry.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    checkout = Path(repo_root or Path.cwd()).expanduser().resolve()
    for entry in loaded.get("repository", []):
        raw = entry.get("path")
        if not raw:
            continue
        try:
            entry_path = Path(str(raw)).expanduser().resolve()
        except OSError:
            continue
        if entry_path != checkout:
            continue
        name = str(entry.get("tracker") or "").strip()
        if name in {"github", "forgejo"}:
            return name
        return None
    return None


class LifecycleError(RuntimeError):
    """Raised when a lifecycle safety invariant is not satisfied."""


def run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=cwd,
        check=False,
        capture_output=capture,
        text=True,
        # Pin the locale: this runner's output is matched for markers such as
        # "CONFLICT", and a localized git turns that into a silent miss on any
        # non-English machine.
        env={**os.environ, "LC_ALL": "C", "LANG": "C"},
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise LifecycleError(
            f"Command failed ({result.returncode}): {shlex.join(args)}\n{detail}"
        )
    return result


def git(repo: Path, *args: str, check: bool = True) -> str:
    return run(["git", "-C", str(repo), *args], check=check).stdout.strip()


def resolve_repo(path: str) -> Path:
    repo = Path(path).expanduser().resolve()
    root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    return root


def safe_id(bead_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", bead_id):
        raise LifecycleError(f"Unsafe bead id: {bead_id!r}")
    return bead_id


def ensure_within(path: Path, parent: Path) -> Path:
    resolved = path.expanduser().resolve()
    root = parent.expanduser().resolve()
    if resolved == root or root not in resolved.parents:
        raise LifecycleError(f"Path must be a child of {root}: {resolved}")
    return resolved


def state_path(repo: Path, bead_id: str) -> Path:
    common = Path(git(repo, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = repo / common
    state_dir = common.resolve() / "cognovis-gas-city"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"{safe_id(bead_id)}.json"


def read_state(repo: Path, bead_id: str) -> dict[str, Any]:
    path = state_path(repo, bead_id)
    if not path.exists():
        raise LifecycleError(f"Lifecycle state does not exist: {path}")
    data = json.loads(path.read_text())
    if data.get("repo") != str(repo):
        raise LifecycleError("Lifecycle state belongs to a different repository")
    return data


def write_state(repo: Path, bead_id: str, data: dict[str, Any]) -> None:
    path = state_path(repo, bead_id)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def emit(summary: str, data: dict[str, Any] | None = None) -> int:
    print(
        json.dumps(
            {
                "status": "ok",
                "summary": summary,
                "data": data or {},
                "errors": [],
                "next_steps": [],
            },
            sort_keys=True,
        )
    )
    return 0


def prepare(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    bead_id = safe_id(args.bead_id)
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    worktree = ensure_within(workspace_root / bead_id, workspace_root)
    branch = args.branch or f"bead-{bead_id}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch):
        raise LifecycleError(f"Unsafe branch name: {branch!r}")

    existing_state = state_path(repo, bead_id)
    if existing_state.exists():
        state = read_state(repo, bead_id)
        if Path(state["worktree"]).resolve() != worktree or state["branch"] != branch:
            raise LifecycleError(
                "Existing lifecycle state does not match requested workspace"
            )
        if worktree.is_dir() and git(worktree, "branch", "--show-current") == branch:
            return emit("Reused existing owned worktree", state)
        raise LifecycleError(
            "Lifecycle state exists but its owned worktree is unavailable"
        )

    if worktree.exists():
        raise LifecycleError(f"Refusing to reuse unowned path: {worktree}")

    base_ref = args.base_ref
    git(repo, "fetch", "origin", args.base_branch)
    git(repo, "rev-parse", "--verify", f"{base_ref}^{{commit}}")
    branch_exists = (
        run(
            [
                "git",
                "-C",
                str(repo),
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
            ],
            check=False,
        ).returncode
        == 0
    )
    if branch_exists:
        run(["git", "-C", str(repo), "worktree", "add", str(worktree), branch])
    else:
        run(
            [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                "-b",
                branch,
                str(worktree),
                base_ref,
            ]
        )

    state = {
        "schema_version": 1,
        "bead_id": bead_id,
        "repo": str(repo),
        "workspace_root": str(workspace_root),
        "worktree": str(worktree),
        "branch": branch,
        "base_ref": base_ref,
        "base_branch": args.base_branch,
        "prepared_sha": git(worktree, "rev-parse", "HEAD"),
        "integrated_sha": "",
    }
    write_state(repo, bead_id, state)
    return emit("Created owned branch worktree", state)


def require_clean(worktree: Path) -> None:
    status = git(worktree, "status", "--porcelain")
    if status:
        raise LifecycleError(f"Worktree is dirty and cannot be integrated:\n{status}")


def require_clean_review(report_arg: str) -> Path:
    report = Path(report_arg).expanduser().resolve()
    if not report.is_file():
        raise LifecycleError(f"Review report does not exist: {report}")
    text = report.read_text()
    status_lines = [
        line.strip() for line in text.splitlines() if line.strip().startswith("Status:")
    ]
    if len(status_lines) != 1:
        raise LifecycleError("Review report must contain exactly one 'Status:' line")
    if status_lines[0] != "Status: CLEAN":
        raise LifecycleError(f"Review gate did not pass: {status_lines[0]}")
    return report


def integrate(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    require_clean_review(args.review_report)
    state = read_state(repo, args.bead_id)
    workspace_root = Path(state["workspace_root"])
    worktree = ensure_within(Path(state["worktree"]), workspace_root)
    if not worktree.is_dir():
        raise LifecycleError(f"Owned worktree is missing: {worktree}")
    if git(worktree, "branch", "--show-current") != state["branch"]:
        raise LifecycleError("Owned worktree is on an unexpected branch")
    require_clean(worktree)

    head = git(worktree, "rev-parse", "HEAD")
    if head == state["prepared_sha"]:
        raise LifecycleError("Implementation produced no commits")

    git(repo, "fetch", "origin", state["base_branch"])
    remote_base = f"origin/{state['base_branch']}"
    integration = ensure_within(
        workspace_root / f".{state['bead_id']}-integration", workspace_root
    )
    if integration.exists():
        raise LifecycleError(f"Unowned integration path already exists: {integration}")

    run(
        [
            "git",
            "-C",
            str(repo),
            "worktree",
            "add",
            "--detach",
            str(integration),
            remote_base,
        ]
    )
    integration_error: LifecycleError | None = None
    cleanup_error: LifecycleError | None = None
    try:
        git(
            integration,
            "merge",
            "--no-ff",
            state["branch"],
            "-m",
            f"merge({state['bead_id']}): integrate Gas City worktree",
        )
        for command in args.verify_command:
            result = subprocess.run(
                command, cwd=integration, shell=True, executable="/bin/sh"
            )
            if result.returncode != 0:
                raise LifecycleError(
                    f"Verification command failed ({result.returncode}): {command}"
                )
        integrated_sha = git(integration, "rev-parse", "HEAD")
        if args.push:
            git(integration, "push", "origin", f"HEAD:{state['base_branch']}")
        else:
            raise LifecycleError("Integration requires explicit --push authorization")
    except LifecycleError as exc:
        integration_error = exc
    finally:
        run(
            ["git", "-C", str(integration), "merge", "--abort"],
            check=False,
        )
        removal = run(
            ["git", "-C", str(repo), "worktree", "remove", str(integration)],
            check=False,
        )
        if removal.returncode != 0:
            cleanup_error = LifecycleError(
                "Integration worktree could not be removed safely; no force fallback was used"
            )

    if integration_error is not None:
        if cleanup_error is not None:
            raise LifecycleError(
                f"{integration_error}\nAdditionally: {cleanup_error}"
            ) from integration_error
        raise integration_error
    if cleanup_error is not None:
        raise cleanup_error

    state["integrated_sha"] = integrated_sha
    write_state(repo, args.bead_id, state)
    return emit(
        "Merged, verified, and pushed through an isolated integration worktree", state
    )


def cleanup(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    state = read_state(repo, args.bead_id)
    if not state.get("integrated_sha"):
        raise LifecycleError("Refusing cleanup before a successful integration")

    git(repo, "fetch", "origin", state["base_branch"])
    ancestry = run(
        [
            "git",
            "-C",
            str(repo),
            "merge-base",
            "--is-ancestor",
            state["integrated_sha"],
            f"origin/{state['base_branch']}",
        ],
        check=False,
    )
    if ancestry.returncode != 0:
        raise LifecycleError(
            "Integrated commit is not reachable from the remote base branch"
        )

    workspace_root = Path(state["workspace_root"])
    worktree = ensure_within(Path(state["worktree"]), workspace_root)
    if worktree.exists():
        if git(worktree, "branch", "--show-current") != state["branch"]:
            raise LifecycleError(
                "Refusing to remove a worktree on an unexpected branch"
            )
        require_clean(worktree)
        run(["git", "-C", str(repo), "worktree", "remove", str(worktree)])

    branch_check = run(
        [
            "git",
            "-C",
            str(repo),
            "branch",
            "--format=%(refname:short)",
            "--merged",
            f"origin/{state['base_branch']}",
        ],
        check=True,
    ).stdout.splitlines()
    merged = {line.strip() for line in branch_check}
    if state["branch"] in merged:
        run(["git", "-C", str(repo), "branch", "-d", state["branch"]])

    state_file = state_path(repo, args.bead_id)
    state_file.unlink()
    return emit("Removed the verified owned worktree without force deletion", state)


def abort(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    state = read_state(repo, args.bead_id)
    if state.get("integrated_sha"):
        raise LifecycleError("Refusing abort after integration; use cleanup instead")
    workspace_root = Path(state["workspace_root"])
    worktree = ensure_within(Path(state["worktree"]), workspace_root)
    if worktree.exists():
        if git(worktree, "branch", "--show-current") != state["branch"]:
            raise LifecycleError("Refusing to abort a worktree on an unexpected branch")
        require_clean(worktree)
        if git(worktree, "rev-parse", "HEAD") != state["prepared_sha"]:
            raise LifecycleError("Refusing to abort a worktree that contains commits")
        run(["git", "-C", str(repo), "worktree", "remove", str(worktree)])
    run(["git", "-C", str(repo), "branch", "-D", state["branch"]])
    state_path(repo, args.bead_id).unlink()
    return emit("Aborted an unintegrated owned worktree with no commits", state)


def close_bead(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    if state_path(repo, args.bead_id).exists():
        raise LifecycleError("Refusing to close while lifecycle state still exists")
    tracker = _issue_tracker_name(repo)
    if not tracker:
        run(["bd", "close", args.bead_id, "--reason", args.reason], cwd=repo, capture=False)
        if args.push_beads:
            run(
                [
                    "ccore",
                    "beads",
                    "sync",
                    "--repo",
                    str(repo),
                    "--operation-id",
                    f"gascity-close:{args.bead_id}",
                ],
                cwd=repo,
                capture=False,
            )
    else:
        run(["ccore", "tracker", "close", args.bead_id], cwd=repo, capture=False)
    return emit("Closed bead after integration and cleanup", {"bead_id": args.bead_id})


def review_gate(args: argparse.Namespace) -> int:
    report = require_clean_review(args.report)
    return emit("Review gate passed", {"report": str(report), "status": "CLEAN"})


def write_review_gate(args: argparse.Namespace) -> int:
    lifecycle_script = Path(args.lifecycle_script).expanduser().resolve()
    if not lifecycle_script.is_file():
        raise LifecycleError(f"Lifecycle script does not exist: {lifecycle_script}")
    report = Path(args.report).expanduser().resolve()
    uv_bin = Path(args.uv_bin).expanduser().resolve()
    if not uv_bin.is_file() or not os.access(uv_bin, os.X_OK):
        raise LifecycleError(f"uv executable is unavailable: {uv_bin}")
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = shlex.join(
        [
            str(uv_bin),
            "run",
            str(lifecycle_script),
            "review-gate",
            "--report",
            str(report),
        ]
    )
    temporary = output.with_suffix(".tmp")
    temporary.write_text(f"#!/bin/sh\nexec {command}\n")
    temporary.chmod(0o700)
    os.replace(temporary, output)
    return emit(
        "Created an executable convergence gate at the requested runtime path",
        {"gate_path": str(output), "report": str(report)},
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--repo", required=True)
    prepare_parser.add_argument("--bead-id", required=True)
    prepare_parser.add_argument("--workspace-root", required=True)
    prepare_parser.add_argument("--base-ref", default="origin/main")
    prepare_parser.add_argument("--base-branch", default="main")
    prepare_parser.add_argument("--branch", default="")
    prepare_parser.set_defaults(handler=prepare)

    integrate_parser = subparsers.add_parser("integrate")
    integrate_parser.add_argument("--repo", required=True)
    integrate_parser.add_argument("--bead-id", required=True)
    integrate_parser.add_argument("--review-report", required=True)
    integrate_parser.add_argument("--verify-command", action="append", default=[])
    integrate_parser.add_argument("--push", action="store_true")
    integrate_parser.set_defaults(handler=integrate)

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--repo", required=True)
    cleanup_parser.add_argument("--bead-id", required=True)
    cleanup_parser.set_defaults(handler=cleanup)

    abort_parser = subparsers.add_parser("abort")
    abort_parser.add_argument("--repo", required=True)
    abort_parser.add_argument("--bead-id", required=True)
    abort_parser.set_defaults(handler=abort)

    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("--repo", required=True)
    close_parser.add_argument("--bead-id", required=True)
    close_parser.add_argument("--reason", required=True)
    close_parser.add_argument("--push-beads", action="store_true")
    close_parser.set_defaults(handler=close_bead)

    gate_parser = subparsers.add_parser("review-gate")
    gate_parser.add_argument("--report", required=True)
    gate_parser.set_defaults(handler=review_gate)

    write_gate_parser = subparsers.add_parser("write-review-gate")
    write_gate_parser.add_argument("--lifecycle-script", required=True)
    write_gate_parser.add_argument("--uv-bin", required=True)
    write_gate_parser.add_argument("--report", required=True)
    write_gate_parser.add_argument("--output", required=True)
    write_gate_parser.set_defaults(handler=write_review_gate)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except (LifecycleError, json.JSONDecodeError, OSError) as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "summary": "Lifecycle operation failed safely",
                    "data": {},
                    "errors": [str(exc)],
                    "next_steps": [
                        "Resolve the reported invariant and retry the same operation."
                    ],
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
