---
name: workplan
description: >-
  Triage the beads backlog into keep, fold, weed, move, and cluster decisions.
  Use when reviewing stale work, planning the next batch, or running backlog refinement.
requires:
  - standard:workflow/bead-hygiene
  - skill:bead-reviewer
requires_standards:
  - workflow/bead-hygiene
---

# Workplan

Analyze the active beads backlog with the triage-pattern loop: Load, Classify,
Enrich, Confirm, Execute, and Record. Workplan proposes and applies backlog
refinement decisions; it does not implement beads.

## When to Use

- "Run workplan"
- "Review stale beads"
- "Refine the backlog"
- "Find duplicates and next work"

## Taxonomy

Classify every loaded bead into exactly one outcome:

| Outcome | Meaning | Requires confirmation |
|---|---|---|
| `keep` | Leave as-is; bead remains actionable. | No |
| `fold` | Merge into another bead or close as duplicate of another bead. | Yes |
| `weed` | Close as obsolete, invalid, or no longer valuable. | Yes |
| `move` | Route to a configured sibling repository. | Yes |
| `cluster` | Group related beads under an existing or new epic/label. | Yes when it mutates beads |

Unknown or ambiguous cases become `keep` with a `needs-human-review` reason, not a
free-form outcome.

## Phase 0: Trigger

Start from one of these triggers:

| Trigger | Detection |
|---|---|
| Manual | User invokes workplan with optional filters such as `--label`, `--epic`, or `--focus`. |
| Cron | Scheduled run in a repository with `.beads/config.yaml`. |
| Stale marker | Open or `in_progress` beads with stale timestamps, stale labels, or stale notes. |

Record the trigger in the eventual audit rows. If no bead repository is present, stop.
All bead reads and writes must use the `bd` CLI.

## Phase 1: Load

Collect the working set and sibling-repo hints.

1. Run the workplan gather helper from the skill root:

   ```bash
   skills/workplan/scripts/gather-data.sh
   ```

   In installed layouts this is the `scripts/workplan/gather-data.sh` equivalent
   for the workplan skill.

2. Use the refinement cache helper to avoid redundant `bd` queries:

   ```bash
   uv run python scripts/refinement/cache.py --repo .
   ```

   The helper reads `.beads/refinement-cache.json` when it is < 1 hour old and
   `.beads/last-touched` has not been updated since. Any close, update, or create
   mutation after the last cache write invalidates the cache. Label and epic
   filters bypass the cache and always query `bd` live.

3. Load the authoritative bead bundle. Choose exactly one of the following
   commands.

   For an unfiltered backlog:

   ```bash
   uv run python scripts/refinement/load-bead-bundle.py --repo . > /tmp/workplan-beads.json
   ```

   For a label-scoped run, pass the exact label. This bypasses the cache and
   queries the live active backlog (`open`, `in_progress`, and `blocked`) through
   `bd list --label`:

   ```bash
   uv run python scripts/refinement/load-bead-bundle.py \
     --repo . --label portfolio:harness > /tmp/workplan-beads.json
   ```

4. Classify persisted review freshness without conflating it with backlog
   disposition:

   ```bash
   BEAD_REVIEWER_RUNTIME="$REPO_ROOT/.agents/skills/bead-reviewer"
   test -d "$BEAD_REVIEWER_RUNTIME" || BEAD_REVIEWER_RUNTIME="$REPO_ROOT/.claude/skills/bead-reviewer"
   test -d "$BEAD_REVIEWER_RUNTIME" || BEAD_REVIEWER_RUNTIME="$REPO_ROOT/skills/bead-reviewer"
   test -d "$BEAD_REVIEWER_RUNTIME" || { echo "project-local bead-reviewer skill is unavailable" >&2; exit 1; }
   uv run python "$BEAD_REVIEWER_RUNTIME/scripts/review_freshness.py" \
     --repo-root . --input /tmp/workplan-beads.json \
     > /tmp/workplan-review-freshness.json
   ```

   Every row carries three orthogonal fields: `Review outcome`,
   `Review freshness`, and `Stale reason`. A stamp without
   `schema_version: 2` is `never-reviewed`; only rows with
   `needs_review: true` may be queued for bead-reviewer. A current
   `clean`, `warnings`, or `blocked` result is reused.

   For current review stamps, aggregate cross-backlog finding classes only by
   `metadata.review.finding_rule_ids`. Use `finding_ids` solely to trace or
   adjudicate one evidence-bound occurrence. `ADHOC-UNCLASSIFIED` is a visible
   taxonomy-maintenance count, not permission to derive a new class from message
   wording. The writer stores both lists in lexical order, so output order is not
   a semantic change.

   Repository and portfolio freshness are deferred. This bridge measures only
   bead content, reviewer implementation, and the resolved contract.

5. If `.beads/refinement-config.yml` exists, load sibling repositories:

   ```bash
   uv run python scripts/refinement/list-sibling-repos.py --config .beads/refinement-config.yml
   ```

The six callable refinement scripts used by workplan are:
`load-bead-bundle.py`, `find-duplicates.py`, `cluster-by-domain.py`,
`list-sibling-repos.py`, `verify-premises.py`, and
`plan-delivery-batches.py`. `bead_io.py` is their shared parser module and is not
invoked directly.

## Phase 2: Classify

Assign one taxonomy outcome to every bead. Use deterministic evidence first, then
LLM judgment only for the final reason text.

Run duplicate and domain helpers:

```bash
uv run python scripts/refinement/find-duplicates.py --input /tmp/workplan-beads.json
uv run python scripts/refinement/cluster-by-domain.py --input /tmp/workplan-beads.json
```

Parse `<!-- severity: ... -->` directives from
`standards/workflow/bead-hygiene.md` before assigning the final outcome. Apply the
rules during classification:
- `critical` hygiene violations force `keep` with `needs-human-review` unless the
  user explicitly confirms a destructive action.
- `major` violations appear in the classification table as warnings and may support
  `fold`, `weed`, or `cluster` recommendations when other evidence agrees.
- `minor` violations appear as advisory notes only.

The classify output must surface hygiene violations, severity, and the
orthogonal review state:

```markdown
| Bead | Outcome | Reason | Review outcome | Review freshness | Stale reason | Hygiene severity | Hygiene violations | Evidence |
|---|---|---|---|---|---|---|---|---|
| clc-abc | keep | Ready and current | clean | current | none | none | none | bd ready |
| clc-def | fold | Duplicate of clc-abc | warnings | stale | content | major | TITLE-VAGUE | find-duplicates |
| clc-ghi | keep | Needs human review before action | none | never-reviewed | legacy-schema | critical | AC-ZERO | bead-hygiene |
```

Classification rules:

- `fold`: duplicate score or semantic overlap points to a clearer surviving bead.
- `weed`: premise is obsolete, all referenced surfaces are gone, or the bead is invalid.
- `move`: sibling-repo keywords match and the current repo is not the owner.
- `cluster`: domain helper finds related beads that need shared label, epic, or dependency
  structure.
- `keep`: bead is ready, still relevant, blocked for a valid reason, or ambiguous.

Review freshness is evidence, not a sixth taxonomy outcome. Run one live
bead-reviewer invocation per `stale` or `never-reviewed` bead and persist the
typed result through the schema-v2 writer before continuing. Never re-review a
current row merely because workplan is running.

When presenting aggregated review evidence, group by stable rule ID and retain
the occurrence IDs as drill-down evidence. Never aggregate legacy free-form
finding IDs or infer a rule from a finding message.

During the MIRA pilot, include at least one `decision` bead and record the
`false-stale` rate caused by label-only changes. Session, claim, and other
non-semantic label churn is a measurement input for the joint follow-up, not a
reason to silently change digest semantics during the pilot.

## Phase 3: Enrich

Add evidence that makes each classification auditable.

Run premise verification:

```bash
uv run python scripts/refinement/verify-premises.py --input /tmp/workplan-beads.json
```

Run history lookup for beads whose outcome is `fold`, `weed`, `move`, or `cluster`:

```bash
uv run python scripts/triage/query_history.py "<bead title and description>" --repo .
```

Enrichment fields:

| Field | Source |
|---|---|
| Duplicate target | `find-duplicates.py` |
| Domain cluster | `cluster-by-domain.py` |
| Sibling repository match | `list-sibling-repos.py` |
| Premise status | `verify-premises.py` |
| Related closed work and memories | `query_history.py` |
| Hygiene severity and rule text | Parsed `bead-hygiene.md` directives |

## Phase 4: Confirm

Batch destructive, cross-repo, and structural decisions before execution. Use the
triage confirmation helper:

```bash
uv run python scripts/triage/present_decisions.py --input /tmp/workplan-decisions.json
```

Confirmation is required for `fold`, `weed`, `move`, and mutating `cluster` actions.
Non-mutating `keep` rows are reported but do not require approval. If the user changes
a decision, update the planned action before execution and preserve the original
recommendation in the reason text.

## Phase 5: Execute

Apply only confirmed actions through the authoritative interface.

| Outcome | Execution |
|---|---|
| `keep` | No mutation unless the user explicitly requested a label or note. |
| `fold` | Use `bd update`, `bd dep`, and `bd close --reason` to preserve the surviving bead and close duplicates with a clear reason. |
| `weed` | Use `bd close --reason` with the obsolete or invalid reason. |
| `move` | Create or update the target repo bead with author-checked `bd`, then close or link the source bead only after confirmation. |
| `cluster` | Use `bd update` for labels, `bd dep` for relationships, or an approved author-checked epic bead when needed. |

Never mutate `.beads/issues.jsonl` directly.

## Phase 6: Record

Append one audit row per executed change:

```bash
uv run python scripts/triage/audit_log.py --path .beads/triage-audit.jsonl --item-id "<bead-id>" --before "<before-state>" --after "<after-state>" --actor workplan --reason "<confirmed reason>"
```

Rows must include item, before state, after state, actor, reason, timestamp, and trigger.
If the helper schema does not have a dedicated trigger field, include the trigger in the
reason string.

## Label-Scoped Delivery Plan

When the trigger includes `--label`, complete duplicate, premise, history,
confirmation, execution, and audit work before planning delivery. Reload the
exact label after confirmed mutations so folded or weeded beads cannot leak into
the plan, then build a deterministic plan from the surviving bundle:

```bash
uv run python scripts/refinement/load-bead-bundle.py \
  --repo . --label portfolio:harness > /tmp/workplan-beads.json
uv run python scripts/refinement/plan-delivery-batches.py \
  --repo . --input /tmp/workplan-beads.json \
  > /tmp/workplan-delivery-plan.json
```

The planner hydrates the filtered list with one authoritative `bd show` query so
dependency state is current. Present its sections in this order:

1. `in_progress`: already-started work, treated as Wave 0.
2. `batches`: priority-then-ID-stable topological batches. A dependency on Wave 0
   is eligible for Batch 1.
3. `externally_blocked`: explicitly blocked beads, dependencies outside the label,
   and downstream work that cannot yet be planned.
4. `cycles`: beads that participate in dependency cycles.

The plan is a handoff artifact, not authorization to implement or dispatch.
Workplan must not invoke an implementation harness, ACPX, Pi, Wayfinder, or a
multi-agent workflow. Use Wayfinder only as a separate, explicit decision aid
when unresolved choices remain after triage.

## Output

Return both the classification table and audit summary:

```markdown
## Workplan

Trigger: <manual | cron | stale marker>
Loaded: <N> beads

### Classification
| Bead | Outcome | Reason | Review outcome | Review freshness | Stale reason | Hygiene severity | Hygiene violations | Evidence |
|---|---|---|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

### Confirmed Actions
| Bead | Before | After | Reason |
|---|---|---|---|
| ... | ... | ... | ... |

### Audit Log
Path: .beads/triage-audit.jsonl
Rows appended: <N>

### Delivery Plan
In progress: <IDs>
Batch 1: <IDs>
Batch 2: <IDs>
External blockers: <IDs and blockers>
Cycles: <IDs>
```

## Resources

- `standards/workflow/triage-pattern.md` — required six-step loop.
- `standards/workflow/bead-hygiene.md` — severity directives parsed in Phase 2.
- `scripts/refinement/load-bead-bundle.py`
- `scripts/refinement/find-duplicates.py`
- `scripts/refinement/cluster-by-domain.py`
- `scripts/refinement/list-sibling-repos.py`
- `scripts/refinement/verify-premises.py`
- `scripts/refinement/plan-delivery-batches.py`
- `scripts/refinement/bead_io.py`
- `scripts/triage/query_history.py`
- `scripts/triage/present_decisions.py`
- `scripts/triage/audit_log.py`
- `skills/workplan/scripts/gather-data.sh`

## Out of Scope

- Implementing beads.
- Dispatching waves.
- Editing bead state without confirmation for destructive or cross-repo actions.
