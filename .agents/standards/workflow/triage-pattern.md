# Triage Pattern

## Purpose

Use this standard when a skill, agent, or script turns a set of candidate items
into reviewed decisions. The pattern keeps triage workflows predictable across
memory review, bug review, intake planning, and workplan refinement.

## Six-Step Loop

1. **Load**: collect the candidate items from the authoritative source and keep
   enough source metadata to trace each item back to its origin.
2. **Classify**: assign exactly one outcome from the workflow taxonomy to each
   item. If the item cannot be classified with available context, classify it as
   a decision that requires confirmation rather than inventing a hidden state.
3. **Enrich**: add evidence that makes the classification auditable, such as
   related beads, existing files, prior memories, duplicate candidates, or
   sibling repository hints.
4. **Confirm**: present batched decisions to the user or caller when an action is
   destructive, cross-repo, ambiguous, or otherwise requires approval.
5. **Execute**: apply only the confirmed action for each item. Execution must use
   the workflow's authoritative interface, such as `bd` for beads or the
   configured memory command for open-brain.
6. **Record**: append an audit trail row that includes the item, before and after
   state, actor, reason, and timestamp. The record must be sufficient for a later
   reviewer to understand why the action happened.

## Taxonomy Shape

Each triage workflow must define **3-7 finite outcomes**. The outcome list must
be small enough to fit in one confirmation prompt, explicit enough that two
operators would classify the same item the same way, and closed enough that
unknown cases go to a named review outcome instead of free-text drift.

## Workflow Mappings

| Workflow | Load | Classify | Enrich | Confirm | Execute | Record |
|---|---|---|---|---|---|---|
| `ob-triage` | Load candidate open-brain memories by age, type, or stale marker. | Classify as `keep`, `merge`, `archive`, `delete`, or `promote`. | Add nearby memories, provenance, and project tags. | Batch memories whose action changes or removes stored knowledge. | Call the memory operation for the approved action. | Save the decision to the memory audit trail with the cited reason. |
| `bug-triage` | Load open bug beads and recent incident context. | Classify as `reproduce`, `deduplicate`, `fix-now`, `defer`, or `close-invalid`. | Add logs, duplicate beads, owners, and affected files. | Ask for confirmation before closing, deduplicating, or reprioritizing. | Update the bead via `bd`, create dependencies, or close invalid reports. | Append bead notes or audit rows for the classification and action. |
| `intake-planned` | Load transcript segments or raw intake items. | Classify as `create-bead`, `append-to-bead`, `ask-clarifying-question`, `discard`, or `route-to-sibling`. | Add related open beads, sibling repo hints, and domain labels. | Present proposed bead actions before creating or moving work. | Create or update beads through `bd` after approval. | Record the intake item, target bead or repo, and rationale. |
| `workplan-planned` | Load open backlog beads for the selected scope. | Classify as `keep`, `fold`, `weed`, `move-to-sibling`, or `cluster-into-epic`. | Add duplicate matches, premise checks, history, and domain clusters. | Batch destructive or cross-repo decisions with recommended outcomes. | Close, update, move, or relate beads through `bd` and configured repo tooling. | Append `.beads/triage-audit.jsonl` rows for every applied change. |

## Compliance

A conforming triage workflow names its taxonomy, follows the six steps in order,
and records every executed change in an audit trail. Documentation may add local
details, but it must not remove steps or expand the taxonomy beyond the finite
3-7 outcome range.
