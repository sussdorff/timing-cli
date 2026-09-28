# Production Feedback Loop: Signal Classification and Triage Workflow

Signals from production systems (user corrections, edge cases, unhappy outcomes) are the primary input for spec evolution. This standard defines how to classify a signal, determine the appropriate response, and convert it into a spec-evolution issue.

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

## Triage Workflow: Signal to Issue

### Step 1: Identify the Signal

Sources to monitor:
- `feedback-extractor` agent output (`feedback-extractions-{TICKET}.json`)
- User corrections in conversation histories (type: `correction`, confidence ≥ 0.80)
- Recurring patterns (`patterns.json`) — two or more occurrences of the same issue

Minimum signal threshold for an issue:
- Confidence ≥ 0.80, OR
- Appeared in 2+ separate tickets/conversations

### Step 2: Classify the Signal

Apply the three decision rules from the taxonomy above. Note the classification explicitly — it determines what comes next.

### Step 3: Locate the Affected Spec

Find the issue(s) whose spec governs the affected behavior:

```bash
# Search open issues by feature name or component
ccore tracker list --repo <prefix> | jq '.data.issues[] | select(.title | test("KEYWORD"; "i")) | {number, title}'

# Read the governing issue once found
ccore tracker show <owner/repo#N> | jq -r '.data.body'
```

### Step 4: Create the Spec-Evolution Issue

Use this template (see Template section below). Issue type rules (the `Type:` line):
- **Behavioral Drift** → `Type: bug` (the service is broken relative to spec)
- **Specification Gap** → `Type: task` (the spec needs extension)
- **Satisfaction Regression** → `Type: feature` (new or revised behavior needed)

### Step 5: Link and Close the Loop

After creating the issue:
1. Note the signal source (ticket ID, feedback ID) in the issue body
2. Reference the original feature issue in the body, or add a note with `ccore tracker comment`
3. If the signal came from a feedback file, mark it as actioned in your notes

## Issue Creation Template

Write the body as Markdown, validate it with the intake skill's
`scripts/issue-author-check.py --body-file <file>`, and create it with
`ccore tracker create --repo <prefix> --body-file <file>`. Replace every `<...>` value; the
first column-0 `Goal:` line becomes the issue title.

```markdown
Type: task
Review-Risk: none

## Intent

Goal: <Component> handles <situation> as the amended spec defines
Scope-In: Spec amendment for <situation>; the <component> behavior that follows it.
Scope-Out: Other behavior of <component>.

## Signal Origin

Source: feedback-extractions-<TICKET>.json, item <fb-id>
Signal type: Specification Gap
Original feature issue: <owner/repo#N, or "unknown">

## What the Signal Shows

<The exact user feedback or correction.>

## Why This Is a Specification Gap

<One paragraph that names the spec that applies, or the situation it never covered.>

## What the Spec Needs

<The concrete amendment: what to add, change or remove in intent, contracts or constraints.>

## Acceptance Criteria

1. The spec for <component> states the expected behavior for <situation>.
2. <Component> shows the amended behavior for <situation> in an automated test.

## Means of Compliance

| AC | Criterion | MoC | Evidence |
|---|---|---|---|
| AC1 | Spec covers the situation | review | <spec path> |
| AC2 | Amended behavior verified | unit | <test path> |
```

Set `Type:`, `Signal type:` and the `Why This Is a ...` heading from the signal type:
- Specification Gap → `Type: task`
- Behavioral Drift → `Type: bug`
- Satisfaction Regression → `Type: feature`

Use the MoC tier that fits each criterion (`unit`, `integ`, `e2e`, `smoke`, `review`, `UAT`,
`demo` or `doc`); `unit` in the template is the default for a focused behavior test.

Set `Review-Risk:` to the actual risk of the amended behavior (`none`, `payment`, `pii`,
`auth` or `compliance`).

## Quick Reference

```
Production signal
       │
       ▼
Service matches its spec?
  No ──► Behavioral Drift → ccore tracker create (Type: bug) → re-run factory
  Yes ──► Spec covers this situation?
             No ──► Specification Gap → ccore tracker create (Type: task) → amend spec
             Yes ──► Users still unhappy?
                        Yes ──► Satisfaction Regression → ccore tracker create (Type: feature) → evolve spec
```

## Worked Example

See `workflow/production-feedback-example.md` for a concrete end-to-end example from a PVS adapter server's feedback archives.

## Relationship to Other Standards

- **factory-ready.md**: After amending a spec, run the intake author check to verify the new issue is ready for autonomous execution
- **issue-intake.md**: Write the amended spec as an issue body with `## Intent`, Acceptance Criteria and Means of Compliance before `ccore tracker create`
- **verification-discipline.md**: Verification of spec-evolution issues should include demo or doc MoC, not just unit tests
