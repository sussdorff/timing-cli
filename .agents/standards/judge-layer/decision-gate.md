# Human Decision Gate

Contract URI: `standard://judge-layer/decision-gate.v1`

Maturity: draft.

A Human Decision Gate is an authoring-time markdown control point. It describes
when a human decision owner must choose among judge-layer outcomes after seeing a
Decision Brief. It is not a runtime authorization record and it is not a typed
bead schema field.

The only authoring representation in beads is a markdown section named:

```markdown
## Human Decision Gate
```

Related contracts: [Decision Brief](decision-brief.md), [Stop Taxonomy](stop-taxonomy.md),
[Judge Outcomes](judge-outcomes.md), [Mandate Schema](mandate-schema.md), and
[ADR-0003](../../docs/adr/ADR-0003-judge-layer-architecture.md).

## Required Fields

| Field | Type | Meaning |
|-------|------|---------|
| `decision owner` | string | Person, role, or standing owner who can make the decision. |
| `allowed outcomes` | enum list | One or more judge outcomes: `ALLOW`, `BLOCK`, `REVISE`, `ESCALATE`. |
| `trigger timing` | string | Phase, event, or condition that presents the gate. |
| `minimum evidence plan` | string | Evidence that must be gathered before the gate is presented. |
| `operational do-nothing/default outcome` | string | What happens operationally if no decision is made. |
| `delivery consequence` | string | Schedule or stakeholder impact, kept separate from the operational outcome. |
| `overrideability` | string | Whether and by whom the gate can be overridden. |
| `sequencing constraints` | string | Ordering constraints such as evidence-before-decision or gate-before-deploy. |

Field labels in bead markdown SHOULD use title case, for example
`Decision owner:`. The validator treats labels case-insensitively.

## Outcome Boundary

`allowed outcomes` MUST use the judge-layer four-outcome set:
`ALLOW`, `BLOCK`, `REVISE`, and `ESCALATE`. Do not invent approval vocabulary
such as "approve", "reject", "sign off", or "looks good". If the decision grants
runtime authority, that authority must be represented as a Mandate reference
where applicable.

## Mandate Boundary

A standing mandate IS a `standard://judge-layer/mandates/mandate.v1` record
governed by [mandate-schema.md](mandate-schema.md). A decision gate may reference
a Mandate when one is relevant, but it carries no inline authorization fields:
no inline authorization fields for mandate scope, limits, grantor, expiry, or
supersession live in this contract.

This keeps the gate disjoint from Mandate required fields and prevents a parallel
standing-mandate schema. The gate is a design-time control-point description;
the Mandate is the authorization-as-evidence record.

## Acceptance Criteria Boundary

Human gates stay outside ordinary outcome acceptance criteria. An acceptance
criterion may require executable evidence or observable behavior, but it must
not say that a human confirms tests, audits evidence, signs off on correctness,
or otherwise acts as the evidence auditor. If a human decision is required,
author it in `## Human Decision Gate` and keep the ordinary acceptance criteria
about the delivered outcome.

## Structural Validation

Deterministic structural validation checks required field presence, non-empty
values, allowed outcome vocabulary, and absence of Mandate field redefinition.
It does not decide semantic truth, detect false urgency, judge residual risk, or
declare evidence sufficient.

## Minimal Shape

```markdown
## Human Decision Gate

Decision owner: Release manager.
Allowed outcomes: ALLOW, BLOCK, REVISE, ESCALATE.
Trigger timing: Before deployment.
Minimum evidence plan: Present rollback smoke test and deployment dry run.
Operational do-nothing/default outcome: Keep the current release in place.
Delivery consequence: Delivery waits for the next deployment window.
Overrideability: Not overrideable by the implementation agent.
Sequencing constraints: Evidence must be gathered before the gate is presented.
```

## Incident Reference

`clc-h4nm` is the non-blocking incident reference that motivated this contract.
Its recorded old-regime authorization is not changed by this standard.
