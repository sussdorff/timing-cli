---
name: adr-currency
description: Audit existing ADRs against current code and remove stale contradictions; domain-modeling records new decisions.
requires_standards: [writing/plain-technical-english]
compatibility: {}
metadata: {}
action_boundary:
  risk_class: reversible-write
  effect_type: filesystem
  proposal_schema: standard://judge-layer/proposals/action-proposal.v1
  judge: agent://judge-default
  requires_mandate: false
---

# ADR Currency Audit

Re-baseline `docs/adr/` to present-tense, current-state records. History
lives in git. Pending work lives in beads.

## Inputs

- The repository `docs/adr/` corpus (plus package-local `docs/adr/` if present).
- `docs/adr/AUTHORING.md` when the repo has one.
- Current code, `CONTEXT.md`, and live beads.

## Outputs

- A triage table (ID, verdict, action, one-line reason) for human approval.
- After approval: deletes, rewrites, and index regeneration in the working tree.

## Exclusions

- Do not delete or rewrite ADRs before the cut-list is approved.
- Do not create new architecture decisions here; hand those to domain-modeling.
- Do not leave `status: superseded` tombstones. `git rm` dead records.

## Workflow

1. Inventory ADR files and frontmatter (`status`, `applies_to`, `prohibits`).
2. Ground each ADR against the code. Do not judge from titles.
3. Classify: LIVE-ACCURATE, LIVE-DRIFTED, ASPIRATIONAL, DEAD-REMOVED, SUPERSEDED, REDUNDANT.
4. Present the cut-list and stop for approval.
5. Execute approved deletes/rewrites/trims. Fix dangling references.
6. If the repo ships `scripts/build-adr-index.py`, regenerate the index and run its tests.

## Do NOT

- Treat "Revision Notes" or "not yet implemented" as current instruction.
- Invent a clinical or committee owner for approval. The repository owner decides.
- Claim the corpus is current without a code-grounded table.

## Resources

| File | Purpose |
|------|---------|
| `references/process.md` | Verdict definitions, trim rules, and verification commands |
