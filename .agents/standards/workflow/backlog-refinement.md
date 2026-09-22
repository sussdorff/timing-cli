# Backlog Refinement

## Purpose

Backlog refinement is the periodic cleanup contract for bead backlogs. It uses
the triage pattern to keep planned work current, deduplicated, and assigned to
the right repository without silently deleting context.

## Configuration Reference

Repository-specific refinement configuration lives in `.beads/refinement-config.yml`.
The standalone schema for that file is documented separately at
`standards/schemas/refinement-config.schema.json`. This standard references the
schema by relative path and intentionally does not inline the schema content.

## Trigger Conditions

Run backlog refinement when any of these conditions applies:

| Trigger | Meaning |
|---|---|
| `cadence` | The configured recurring interval has elapsed for this repository or stream. |
| `manual` | A user explicitly requests a workplan, backlog review, cross-repo cleanup, or duplicate sweep. |
| `stale-threshold` | A bead has exceeded the configured stale age without progress, verification, or updated context. |

The workflow may also run as a preflight dependency for wave planning, but that
preflight must still use the configured trigger data rather than hardcoded local
rules.

## Allowed Change Types

Backlog refinement may propose only these change types:

| Change | Description | Confirmation Required |
|---|---|---|
| `close` | Close obsolete, invalid, already-completed, or superseded beads with a cited reason. | Yes |
| `fold` | Fold one or more duplicate or subordinate beads into a surviving target bead. | Yes |
| `move` | Move or recreate a bead in a configured sibling repository when ownership is wrong. | Yes |
| `update` | Update metadata, labels, dependencies, priority, owner, or description to reflect current reality. | When destructive or cross-repo |

The workflow must not invent new change types in prose. If a case does not fit
one of these actions, classify it as a confirmation item and record the reason.

## Audit Trail

Every executed refinement action must append one JSONL row to
`.beads/triage-audit.jsonl` in the repository where the action is applied. Rows
must identify the item, prior state, new state, actor, reason, and timestamp.

The audit trail is the first place a later reviewer should inspect before
challenging a cleanup decision. Bead notes may summarize the same decision, but
they do not replace the JSONL audit row.

## Required Flow

1. Load the configured bead set and sibling repository hints.
2. Classify each bead using a finite refinement taxonomy.
3. Enrich classifications with premise checks, duplicate matches, domain
   clusters, and history.
4. Confirm destructive, ambiguous, or cross-repo changes.
5. Execute approved `close`, `fold`, `move`, or `update` actions through `bd` and
   configured repository tooling.
6. Record every applied action in `.beads/triage-audit.jsonl`.

## Compliance

A backlog refinement implementation complies with this standard when it documents
its trigger source, limits actions to the allowed change types, writes the audit
row for each executed action, and validates local configuration against the
external schema reference when that schema is available.
