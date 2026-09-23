# Subagent Gates

Constraints applied before dispatch and checks applied after completion for any
delegated implementation task.

## Pre-dispatch scope constraints

A subagent asked to add 5 UI filters instead changed 70 files and 5000 LOC —
splitting an API layer into 8 files and deleting unrelated backend routes —
because one ambiguous phrase read as permission to refactor.

| Constraint | Form |
| --- | --- |
| Negative constraints first | "Do not refactor, delete, or move any existing files." leads the prompt. |
| Explicit file scope | "Only modify these files: [list]" or "Do not create new files." |
| Unambiguous phrasing | "Fetch all rows for this page only" instead of "load all X client-side" — broad phrasing gets read as broad permission. |

## Post-completion gates

| Gate | Check |
| --- | --- |
| Churn matches scope | `git diff --stat`: file count and LOC delta plausible for the task size. Net LOC above ~3x the expected task size warrants investigation before merge. |
| No unexpected deletions | Deleted files listed and justified; `git diff -- <deleted-files>` confirms nothing load-bearing was removed. |
| No out-of-scope additions | New files outside the expected scope are a red flag, not a bonus. |
| Non-zero exit is inspected, not discarded | An agent exiting non-zero (e.g. partial completion) may leave correct uncommitted work in the worktree. `git status` and `git diff` after the exit determine what was actually produced; orphaned changes otherwise get silently mixed into later commits, obscuring authorship. |
| Completed checkpoints replay, not re-execute | A dispatch runner with checkpoint state (e.g. `checkpoint=completed`) short-circuits on re-dispatch with the same run ID and replays the stored completion report. Follow-up work after completion needs a fresh dispatch (fix-agent or new run ID), not a re-invocation. |
