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
- An exact active Bead ID only when the conversation and current work identify one unambiguously.
- The canonical harness session ID for file-backed handoffs.

## Outputs

- One persisted handoff containing Purpose, Current State, Decisions and Rationale, Failed Approaches, Important Exact Details, Open Questions, Continuation Point, and Uncertainties.
- One copyable bootstrap sentence naming the exact Bead or handoff path.

## Workflow

1. Treat a Bead as active only when this conversation and current work identify exactly one. Never select a Bead merely because it is claimed or in progress elsewhere.
2. Write context another capable agent cannot recover by reading files, Git, or the Bead body. Preserve exact errors, response shapes, identifiers, corrections, and rationale when they affect continuation. Keep the handoff contextual, not prescriptive.
3. For the Bead route, treat the explicit invocation as the mandate, submit the declared external-side-effect Action Proposal, and proceed only after `ALLOW`.
4. For an allowed Bead route, start the temporary handoff file with `## Context Handoff <ISO-8601 timestamp>` and append it with `bd note <id> --file <handoff-file>` without rewriting the body. Follow the repository's tracker-sync policy before reporting success.
5. Otherwise run `uv run --no-project <skill-root>/scripts/resolve_handoff_path.py` from the target worktree. Pass `--repo-root <exact-root>` only as a validated override and `--session-id <exact-id>` only when automatic harness detection cannot resolve one ID. Stop on an error; never substitute a timestamp or invented ID.
6. Write to the absolute `data.path`. When `data.exists` is false, create the handoff; when true, append a clearly separated new `Context Handoff` section and preserve prior sections. Do not create any other documentation file.
7. In the persistence summary, state when `data.worktree_local` is true that the handoff is worktree-local and will disappear if that worktree is removed. Then return exactly one bootstrap sentence. For a file use: `Read <data.path> as context from the previous chat; refresh mutable repository and tracker state, then continue from its Continuation Point.` For a Bead use: `Read the latest Context Handoff note on Bead <id> with bd show <id> --json; refresh mutable repository and tracker state, then continue from its Continuation Point.` When the registry entry declares a tracker, use `ccore tracker` instead of `bd`; with no tracker field, keep `bd` for the Beads archive.

## Do Not

- Call `/clear`, `/compact`, archive, or session-close for the user.
- Claim a Bead, change its work order, or store unrelated conversation history.
- Present `.intake` as durable across worktree removal, machines, or repository cleanup.
- Write a file-backed handoff unless the resolver confirms the path is ignored by Git.

## Resources

| File | Purpose |
|---|---|
| `scripts/resolve_handoff_path.py` | Validate a canonical session ID and return the safe local handoff path. |
