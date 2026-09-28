---
name: context-handoff
description: Preserve conversation context when explicitly requested before a new chat; excludes automatic compaction and delivery finalization.
requires_standards: [judge-layer, writing/plain-technical-english, writing/unslop, writing/unambiguous-english]
compatibility: {}
metadata: {}
action_boundary:
  risk_class: external-side-effect
  effect_type: network
  proposal_schema: standard://judge-layer/proposals/action-proposal.v1
  judge: agent://judge-default
  requires_mandate: true
---

# Context Handoff

Preserve conversation-only knowledge so a fresh chat can resume after `/clear`.

## Inputs

- The current conversation and repository state.
- An exact active hosted issue reference (`owner/repo#N`) only when the conversation and current work identify one unambiguously.
- The canonical harness session ID for file-backed handoffs.

## Outputs

- One persisted handoff containing Purpose, Current State, Decisions and Rationale, Failed Approaches, Important Exact Details, Open Questions, Continuation Point, and Uncertainties.
- One copyable bootstrap sentence naming the exact issue or handoff path.

## Workflow

1. Treat an issue as active only when this conversation and current work identify exactly one. Never select an issue merely because it is assigned or in progress elsewhere. A repository without a hosted tracker has no issue route.
2. Write context another capable agent cannot recover by reading files, Git, or the issue body. Preserve exact errors, response shapes, identifiers, corrections, and rationale when they affect continuation. Keep the handoff contextual, not prescriptive.
3. For the issue route, treat the explicit invocation as the mandate, submit the declared external-side-effect Action Proposal, and proceed only after `ALLOW`.
4. For an allowed issue route, start the temporary handoff text with `## Context Handoff <ISO-8601 timestamp>` and post it as one comment with `ccore tracker comment <owner/repo#N> --body "$(cat <handoff-file>)"` without editing the issue body. Report success only on an `ok` envelope.
5. Otherwise run `uv run --no-project <skill-root>/scripts/resolve_handoff_path.py` from the target worktree. Pass `--repo-root <exact-root>` only as a validated override and `--session-id <exact-id>` only when automatic harness detection cannot resolve one ID. Stop on an error; never substitute a timestamp or invented ID.
6. Write to the absolute `data.path` (`.intake/context-handoff/<session-id>.md` under the resolved repository root). When `data.exists` is false, create the handoff; when true, append a clearly separated new `Context Handoff` section and preserve prior sections. Do not create any other documentation file.
7. In the persistence summary, state when `data.worktree_local` is true that the handoff is worktree-local and will disappear if that worktree is removed. Then return exactly one bootstrap sentence. For a file use: `Read <data.path> as context from the previous chat; refresh mutable repository and tracker state, then continue from its Continuation Point.` For an issue use: `Read the latest Context Handoff comment on <owner/repo#N> (<html_url>); refresh mutable repository and tracker state, then continue from its Continuation Point.` `ccore tracker show` returns the issue body without comments, so name the issue's `html_url`.

## Do Not

- Call `/clear`, `/compact`, archive, or close the session for the user.
- Assign or claim an issue, change its work order, or store unrelated conversation history.
- Present `.intake` as durable across worktree removal, machines, or repository cleanup.
- Write a file-backed handoff unless the resolver confirms the path is ignored by Git.

## Resources

| File | Purpose |
|---|---|
| `scripts/resolve_handoff_path.py` | Validate a canonical session ID and return the safe local handoff path. |
