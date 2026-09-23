# Diff-Scope Integrity

In a multi-worktree environment (the norm here: every non-default branch has its
own worktree, several beads run concurrently), a review or gate that computes its
own diff can ground against the wrong changes. Every incident below produced a
false verdict or a wrong destructive action before the scope was corrected.

| Rule | Detail |
| --- | --- |
| Review agents receive a pinned diff scope | A diff-scoped reviewer (constraint-checker, cold review, verification) that resolves "the diff" itself can evaluate a different concurrent bead's worktree. The dispatch pins the worktree path and commit range — or pastes the exact diff inline with the instruction not to run git — before any verdict counts. |
| A moving `origin/main` invalidates self-computed diffs | While an implementer session runs, unrelated beads merge to `origin/main`. A reviewer diffing against `origin/main` mid-flight sees contamination from those merges, not scope creep. |
| Pre-implementation SHAs go stale | A `PRE_IMPL_SHA` captured at claim time is invalidated by any mid-flight rebase onto an advanced `origin/main`. Diffing against the stale SHA makes upstream commits look like bead scope creep. The diff range is recomputed against the current merge-base; `git log origin/main...HEAD` is noisy here because it pulls in other beads' rebased commits. |
| Sibling syncs rescope the review range | When the implementer merged a concurrently completed sibling bead's work, downstream reviews are rescoped to the bead's own range (merge-commit-parent..HEAD), not the raw pre-implementation range. |
| Ancestry check precedes destructive action | An unfamiliar commit in the diff range is checked for ancestry (`git merge-base --is-ancestor <sha> origin/main`) before a revert or any other destructive git action — and before filing a scope-creep finding. A commit already on `origin/main` arrived via legitimate sync, and reverting it re-breaks merged work. |
