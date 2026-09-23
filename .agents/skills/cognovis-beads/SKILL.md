---
name: cognovis-beads
description: Apply Cognovis bead authoring, safe synchronization and recovery conventions; use bd directly for ordinary tracker reads.
compatibility: {}
metadata: {}
---

<!-- COGNOVIS_OVERLAY_BEGIN -->
# Cognovis Beads Overlay

Upstream Beads owns tracker behavior, and `bd prime` is its canonical command and
release reference. This overlay defines only Cognovis authoring, state, synchronization,
and recovery behavior layered on top. Repository delivery belongs to `executive-pack`;
context, metrics, review, and worktree helpers belong to their delivery consumers.

For new or changed work orders, read [authoring.md](references/authoring.md).
Beads is archive-only for repositories whose registry entry declares a
`tracker`. Live work orders use `ccore tracker`; `bd` remains for archive
reads and for registry entries with no tracker.

## Cognovis Invariants

- Validate factory-ready create/update bodies with the existing author-check hook.
- Keep Acceptance Criteria observable and preserve one Means of Compliance entry per AC.
- A note never changes the work order. When a decision supersedes part of a bead,
  rewrite the body — Intent, Scope-In, Scope-Out, Acceptance Criteria, Pre-Mortem —
  through `ccore tracker` (declared tracker) or `bd update <id> --body-file` (archive),
  and use a note only to record why it changed
  and when. Notes carry context, evidence, and history; the body is the instruction,
  and whoever picks the bead up reads the body. A body contradicting its own note is
  worse than an uncorrected one, because it hands out the superseded instruction
  silently. Writing a note *because* the body is now wrong is the signal to rewrite
  the body.
- For bug beads, default to one AC for the failing case and add one adjacent
  control-case AC only when regression risk warrants it. Use the smallest focused
  regression check as MoC. Keep implementation constraints in Scope-Out and keep
  full suites, unrelated systems, customer data, E2E/UAT, deployments, health
  checks, and push preflight out of bug AC/MoC unless the reported defect itself
  crosses that boundary.
- Use `ccore beads sync --operation-id <stable-id>` when an
  automated workflow needs serialized commit, pull, push, reconcile, and durable resume.
  A plain direct `bd dolt push` remains permitted for ordinary upstream Beads operation.
- Forced Dolt push is recovery-only and requires explicit human authorization; no normal
  agent command exposes a force option.

## Dolt Engine

bd runs Dolt in-process at `.beads/embeddeddolt/<db_name>/`, gitignored;
`https://dolt.cognovis.de/<db_name>` is a *remote*, not a server. Worktrees share the main
checkout's engine, so a claim is visible in every worktree with no sync step. Load
[`references/dolt-sync.md`](references/dolt-sync.md) for database creation, fresh-clone
recovery, auth, upgrade ordering, the prefix registry, and force-push recovery; ordinary
`bd` use needs none of it. Remote host facts live in `infra-devops/hetzner/docs/inventory.yml`.

## Resources

| Path | Purpose |
|---|---|
| `scripts/cognovis-beads.py` | Prints this overlay for upstream `bd prime` sessions |
<!-- COGNOVIS_OVERLAY_END -->
