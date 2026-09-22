# Production Feedback Loop: Signal Classification and Triage Workflow

Signals from production systems (user corrections, edge cases, unhappy outcomes) are the primary input for spec evolution. This standard defines how to classify a signal, determine the appropriate response, and convert it into a spec-evolution bead.

## Signal Classification Taxonomy

Every production signal belongs to exactly one of three types:

| Type | Definition | Source | Response |
|------|-----------|--------|----------|
| **Behavioral Drift** | Service diverges from its own spec — the spec is correct but the service no longer implements it | Dependency changed, config modified, agent behavior shifted | Re-run factory with current spec (no spec change needed) |
| **Specification Gap** | Service works as specced, but encounters a situation the spec never contemplated | New use case, edge case, environmental constraint | Human examines gap, amends spec with new scenario or intent |
| **Satisfaction Regression** | Service meets spec perfectly but users are unhappy — the spec itself is wrong | Users report frustration despite correct behavior | Creative spec evolution — rewrite or extend the intent |

### Decision Rules: Which Type Is It?

Ask these questions in order:

1. **Does the service currently match its spec?**
   - No → **Behavioral Drift**. Stop here. Re-run factory.
   - Yes → continue

2. **Does the spec address this situation at all?**
   - No (situation was never contemplated) → **Specification Gap**. Stop here. Amend spec.
   - Yes → continue

3. **Are users still unhappy even though behavior matches spec?**
   - Yes → **Satisfaction Regression**. Evolve the spec.

### Signal Indicators by Type

**Behavioral Drift** signals:
- Recent dependency update broke existing behavior
- Agent follows an old CLAUDE.md rule that conflicts with current guidance
- Config drift between environments causes different outcomes

**Specification Gap** signals:
- User feedback contains "we never thought about X"
- A new environmental constraint appears (e.g., PING disabled in production networks)
- An edge case causes the service to either crash or silently do the wrong thing

**Satisfaction Regression** signals:
- Feature works exactly as documented but users want different behavior
- User says "yes but" — agrees the service is correct but wants something different
- Recurring corrections that don't point to broken code but to wrong assumptions

## Triage Workflow: Signal to Bead

### Step 1: Identify the Signal

Sources to monitor:
- `feedback-extractor` agent output (`feedback-extractions-{TICKET}.json`)
- User corrections in conversation histories (type: `correction`, confidence ≥ 0.80)
- Recurring patterns (`patterns.json`) — two or more occurrences of the same issue

Minimum signal threshold for a bead:
- Confidence ≥ 0.80, OR
- Appeared in 2+ separate tickets/conversations

### Step 2: Classify the Signal

Apply the three decision rules from the taxonomy above. Note the classification explicitly — it determines what comes next.

### Step 3: Locate the Affected Spec

Find the bead(s) whose spec governs the affected behavior:

```bash
# Search by feature name or component
bd list --status=closed --json | jq '.[] | select(.title | test("KEYWORD"; "i")) | {id, title}'

# Or search by component tag
bd list --json | jq '.[] | select(.metadata.component == "COMPONENT_NAME") | {id, title}'
```

### Step 4: Create the Spec-Evolution Bead

Use this template (see Template section below). Bead type rules:
- **Behavioral Drift** → `--type=bug` (the service is broken relative to spec)
- **Specification Gap** → `--type=task` (the spec needs extension)
- **Satisfaction Regression** → `--type=feature` (new or revised behavior needed)

### Step 5: Link and Close the Loop

After creating the bead:
1. Note the signal source (ticket ID, feedback ID) in the bead description
2. Reference the original feature bead via `bd update` metadata
3. If the signal came from a feedback file, mark it as actioned in your notes

## Bead Creation Template

Validate a factory-ready body and call `bd create --body-file <file>` with fields like these:

```yaml
title: "[TYPE] Component: one-line problem statement"
type: task
context: |
  ## Signal Origin
Source: feedback-extractions-{TICKET}.json, item {fb-id}
Signal type: Specification Gap | Behavioral Drift | Satisfaction Regression
Original feature bead: {ORIGINAL_BEAD_ID} (if known)

## What the Signal Shows
{Paste the exact user feedback or correction here}

## Why This Is a [TYPE]
{One paragraph explaining the classification. Reference the spec that applies or the situation that was never contemplated.}

## What the Spec Needs
  {Concrete amendment: what to add, change, or remove from the intent/contracts/constraints}
acceptance_criteria:
  - Spec updated to cover this situation
  - New behavior verified against the amended spec
means_of_compliance:
  - acceptance_criterion: Spec updated to cover this situation
    method: review
  - acceptance_criterion: New behavior verified against the amended spec
    method: test
metadata:
  intent: Amend spec to handle the situation based on production signal {fb-id}
  component: "[component]"
  signal_source: "[TICKET_ID]"
  signal_type: gap|drift|regression
```

Adapt `type` based on signal type:
- Gap → `task`
- Drift → `bug`
- Regression → `feature`

## Quick Reference

```
Production signal
       │
       ▼
Service matches its spec?
  No ──► Behavioral Drift → bd create (type=bug) → re-run factory
  Yes ──► Spec covers this situation?
             No ──► Specification Gap → bd create (type=task) → amend spec
             Yes ──► Users still unhappy?
                        Yes ──► Satisfaction Regression → bd create (type=feature) → evolve spec
```

## Worked Example

See `workflow/production-feedback-example.md` for a concrete end-to-end example from the charly-server feedback archives.

## Relationship to Other Standards

- **factory-ready.md**: After amending a spec, run `/bead-reviewer` to verify the new bead is ready for autonomous execution
- **bead-spec.md**: Use NLSpec metadata (`intent`, `contracts`, `constraints`) when writing the amended spec with `bd create`
- **verification-discipline.md**: Verification of spec-evolution beads should include demo or doc MoC, not just unit tests
