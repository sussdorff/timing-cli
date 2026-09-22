---
name: session-close
description: Finalize the calling coding delivery with ccore session-close after required review; excludes release and unrelated cleanup.
requires:
  - script:ccore
requires_standards: [worktree-subagent-discipline, writing/plain-technical-english, writing/unslop, writing/unambiguous-english, workflow/agent-session-capture]
disableModelInvocation: true
---

# Session Close

Finish only the calling session through the installed `ccore` CLI.

## Inputs

- Git repository, named calling branch, integration target, and exact session worktrees.
- Zero or more explicit hosted issue refs (`owner/repo#N` or issue URL).
- A concise session summary and any durable learnings extracted by the active session.

## Outputs

- Durable `ccore_session_close_v1` state for
  `stop -> contain -> finalize -> remember -> cleanup`.
- Exact issue-owned containers stopped before any Git integration or finalization side effect.
- Proof that the caller's committed head is contained, explicit hosted-issue finalization,
  an Open Brain memory reference, and cleanup results.
- One recorded delivery identity: session ID, the exact issue refs, the repository,
  the branches, the candidate SHA, the harness, and the worktree owner. The journal
  and the pull-request footer carry it, never from a worktree path or a branch name.

`ccore` records the worktree owner as `session-close` for a self-managed worktree
it may clean, or a provider value such as `t3code` for one it must retain; it
treats every owner other than `session-close` as provider-owned. Those spellings
are the durable ones. This Library's `self` and `provider:<id>` name the same two
facts, and `scripts/agent_workspace_guard.py` reads either. Provider signals — a
provider session path, an explicit `--harness` — may decide the value at record
time; every later decision reads the recorded field.

## Delivery paths

The caller resolves `direct`, `pr-auto`, or `pr-review` with the installed
executive-pack `scripts/landing_policy.py` and passes the matching
`--delivery` value. This skill does not decide the policy and does not restate its
matrix.

- `direct`: `ccore session-close run ... --delivery merge` integrates the head and
  finishes `completed`.
- `pr-auto`: `ccore session-close run ... --delivery pr --merge-authority agent_bot`
  requests the authorized bot merge, proves containment and finalizes in one run.
- `pr-review`: `ccore session-close run ... --delivery pr --merge-authority human`
  publishes without merging. After human merge, `ccore session-close complete-pr
  --session-id <id>` observes containment and finalizes.

Human-authority publication returns review_pending with issues still open; it is not
terminal completion. Report the PR and Session Close ID for continuation. Only the
CLI's completed or completed_with_warnings result establishes terminal delivery.

## Workflow
1. Commit all intended work and identify only worktrees created or owned by this session.
2. Change to a stable checkout outside any worktree that Cleanup must remove. Run
   `ccore session-close run --help`, then invoke `ccore session-close run` with
   the repository, branch, exact `--issue` and `--worktree` values, `--summary`, and
   each material `--learning`. `--bead` is a hidden alias for `--issue`. For pull-request delivery `--summary` carries the
   full text written by `cognovis-pr`: line one becomes the title, the whole text the body. Pass EVERY repository the session touched: one
   `ccore session-close run` per repository, never only the feature worktree's
   repository.
   The work order lives in the repository's tracker: run `ccore tracker show <ref>`
   for `owner/repo#N` or an issue URL. Unhosted registry entries fail closed.
3. The first capability validates the explicit issues and stops their exact opted-in containers.
   Docker unavailability becomes a loud `docker_unverified` warning; run stale cleanup later.
4. Capture the returned Session Close ID. On a typed refusal, repair only the named condition and
   run `ccore session-close resume --session-id <id>` from the stable checkout; use `status` for read-only inspection. Never start a second `run` to retry. From a checkout on the target branch, `ccore` contains the named branch head while that branch exists and ignores the identity once it is gone;
   for a retryable dirty checkout, commit only intended paths and resume that ID.
   `finalize` comments a landing note and closes the in-scope hosted issues after
   containment. There is no `bd close` and no `ccore beads sync`.
   Integration starts from the last cleanly reviewed state: a conflict-free rebase
   needs no new review; behavioral conflict resolution needs focused integration review;
   incompatible Main and feature intent is a human decision blocker.
5. Report terminal results, including every warning and retained Docker resource. Do not duplicate
   the CLI's side effects. Cleanup fast-forward-pulls a clean checked-out target branch from the
   verified remote; equivalent diverged histories align with compare-and-swap protection, and a
   clean checkout holding commits the remote target lacks is merged and pushed without force.
   Only a conflicting merge or a dirty checkout produces a retryable refusal, and the checkout
   then remains in its pre-merge state.

## Exclusions

- Review gates, reviewer receipts, Pack authorization, release/version/tag behavior,
  and CI policy are owned by their originating flows and are never Session Close inputs.
- Session Close never force-pushes and never infers issue refs or cleanup targets
  from branch names or filesystem scans.
- Never spawn a Session Close agent; run the deterministic CLI in the active session.

## Resources

| Resource | Purpose |
|---|---|
| `ccore session-close --help` | Authoritative interface |
| `~/.local/state/ccore/session-close/<id>.json`, `~/.local/state/ccore/agent-runs/` | Inputs for a later `/retro` on this session's environment |
