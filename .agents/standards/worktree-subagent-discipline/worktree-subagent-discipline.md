---
domain: worktree-subagent-discipline
description: Empirically grounded discipline rules for multi-worktree layouts and delegated subagent work — checkout targeting, worktree mechanics, acceptance gates, parallel orchestration, and diff-scope integrity.
---

# Worktree and Subagent Discipline

> **Scope**: Dev-plane standard for orchestration, dispatch, and review skills/agents that operate in repositories where every non-default branch has its own git worktree and implementation work is delegated to subagents or external coding agents.

## Core rules

| Rule | Detail |
| --- | --- |
| The worktree path is an explicit input | Every writing agent receives its target worktree path explicitly and never derives it from a canonical checkout location. Stray main-checkout edits are a recurring, silent failure mode. See [Wrong checkout](wrong-checkout.md). |
| Worktrees have their own mechanics | Worktrees track `origin/main` (not local main), lose work under automatic cleanup, and require commit-before-merge and sequential merge-back. See [Worktree mechanics](worktree-mechanics.md). |
| Subagent output is gated, not trusted | Scope is constrained up front (negative constraints, file lists) and verified afterward (`git diff --stat`, LOC anomaly check, post-exit state inspection). See [Subagent gates](subagent-gates.md). |
| Parallel agents need dependency order | Dependent work is spawned only after its prerequisites are merged; shared files are briefed explicitly; later branches rebase before merge. See [Parallel orchestration](parallel-orchestration.md). |
| Diff scope is recomputed, never assumed | In multi-worktree environments a captured pre-implementation SHA goes stale; review diffs are re-grounded against the current merge-base, and ancestry is verified before any destructive git action. See [Diff-scope integrity](diff-scope-integrity.md). |

## Related work

- Bead `clc-mfaz` — closed 2026-08-09. Overlay symlinks (`.agents/`, `.claude/skills/`) are bootstrapped by the launcher-side resolver in the meta repo (`meta/scripts/worktree-overlays.py`): `cdx` links after `git worktree add`, `cld` passes `worktree.symlinkDirectories` via `--settings`. Covers memories #35112/#35073.
