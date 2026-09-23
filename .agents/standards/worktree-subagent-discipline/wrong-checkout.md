# Wrong Checkout

Edits and commits intended for a task worktree repeatedly land in the main
checkout instead. This failure is silent: the agent reports success, and nothing
looks wrong until a diff or a blocked merge exposes it. It occurred twice in a
single working day with the same subagent (doc-changelog-updater, 2026-07-13).

## Failure modes

| Failure | Mechanism |
| --- | --- |
| Absolute path targets main checkout | Edit calls that use the main repo's absolute path (`<repo>/src/...`) instead of the worktree path (`<repo>/.claude/worktrees/<name>/src/...`) modify the main checkout and block the later merge from the worktree branch. |
| Relative paths resolve against the wrong cwd | Relative paths resolved from an unexpected cwd silently target the main working tree. Only worktree-absolute paths are reliable. |
| Subagent commits on the wrong branch | A subagent whose cwd is the main repo root commits to `main` instead of the feature branch. `git branch --show-current` before committing detects this. |
| Path derived from assumption | A subagent that resolves "the repo" from the canonical checkout location writes there even when dispatched for a worktree. The target path must be passed explicitly in the task context and used verbatim. |
| Stale read cache in worktrees | The Read tool can return stale content inside a worktree while the committed state differs. When Read and Grep disagree, `git show HEAD:<path>` or Grep reflect disk truth. |
| Pre-staged dirt blocks merge-back | Staged-but-uncommitted changes in the main checkout (e.g. a VERSION bump from an interrupted session close) block worktree merges. `git status` on the main checkout belongs before any merge-back. |
| Codex sandbox cannot commit in linked worktrees | For a linked worktree, gitdir metadata (including `index.lock`) lives under the main checkout's `.git/worktrees/<name>/`. A workspace-write sandbox scoped to the worktree path cannot write it, so `git add`/`git commit` fail with sandbox write-permission errors. Git mutations need a fallback outside the sandbox. |

## Detection and recovery

| Aspect | Rule |
| --- | --- |
| Detection | `git status` on both the main checkout and the target worktree before committing anything from a subagent run. Unexpected dirty state on main that mirrors the expected worktree output is the signature. |
| Recovery | Non-destructive: `git stash push` the stray main-checkout changes (safety net), reapply the identical content in the correct worktree, commit there, confirm main is clean, then drop the stash. Never force-discard the stray copy first. |
| Wrong-branch commit | Cherry-pick the commit onto the worktree branch, then reset main. |
