# Worktree Mechanics

Behavioral facts about git worktrees that differ from single-checkout intuition.

| Fact | Detail |
| --- | --- |
| Automatic worktree cleanup loses work | An agent-managed worktree (e.g. Agent tool `isolation: worktree`) is cleaned up when its task closes; uncommitted or unmerged work is gone. Manual lifecycle control (e.g. `EnterWorktree`) keeps the worktree alive until the work is integrated. |
| Worktrees track `origin/main`, not local main | A worktree can report "up to date with origin/main" while local main holds unpushed commits the worktree lacks. Absorbing them requires merging the local main branch directly. |
| Massive post-rebase deletions signal a stale base | A rebase onto main that shows large LOC deletions (thousands of lines) usually means the branch was based on an older main. Diagnosis: `git diff --diff-filter=D` for deleted files. Recovery: restore via `git checkout origin/main -- <paths>`, reset to `origin/main`, re-apply only the intended changes. |
| Commit before merging from main | With uncommitted changes in the worktree, any merge from main aborts with "local changes would be overwritten". Committing the feature work first (WIP commits are fine) is the standard path; stashing is reserved for genuine scratch work. |
| Sibling worktrees merge back sequentially | Two worktrees based on the same branch are merged one at a time: merge the first into main and push; pull the updated main into the second; then merge the second. Independent parallel merge-and-push produces diverged heads on the remote. |
| Conflict-resolution default | When a feature branch conflicts with `origin/main`: keep the branch's feature logic, absorb purely additive upstream changes (new imports, new unrelated functions), and never accept "ours" or "theirs" wholesale. Where both sides modified the same code, the feature version wins and the upstream intent is verified against the diff. |
