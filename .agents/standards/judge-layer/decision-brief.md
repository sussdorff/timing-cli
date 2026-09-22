# Decision Brief

Contract URI: `standard://judge-layer/decision-brief.v1`

Maturity: draft.

A Decision Brief is an authoring-time summary for a manager-decidable
operational decision. It is not a runtime authorization record, not a judge
outcome, and not a substitute for executable evidence. It exists so a human can
decide between explicit outcomes after seeing the safe read-only facts, blast
radius, rollback, deployment timing, and do-nothing analysis.

Related contracts: [Decision Gate](decision-gate.md), [Stop Taxonomy](stop-taxonomy.md),
[Judge Outcomes](judge-outcomes.md), [Mandate Schema](mandate-schema.md), and
[ADR-0003](../../docs/adr/ADR-0003-judge-layer-architecture.md).

## Compact Manager View

The manager view is the short section shown before the evidence detail. It MUST
fit in one screen and MUST contain these fields:

| Field | Type | Meaning |
|-------|------|---------|
| `Decision required` | string | The concrete choice the decision owner must make. |
| `Recommended default` | string | The operationally safe default if no decision is made. |
| `Operational risk` | enum | One of ADR-0003 `risk_class` values: `read-only`, `reversible-write`, `external-side-effect`, or `high-risk`. |
| `Operational do-nothing/default outcome` | string | What happens operationally if no one authorizes a change. |
| `Delivery consequence` | string | Schedule, stakeholder, or delivery impact, kept separate from operational risk. |
| `Decision needed by` | string | Time, phase, or event when the decision is needed. |

## Evidence Appendix

The evidence appendix is separate from the compact manager view. It MAY be long,
but it MUST make the factual basis inspectable without asking the manager to
audit code quality. It MUST contain these fields:

| Field | Type | Meaning |
|-------|------|---------|
| `Evidence appendix references` | list or string | Test output, read-only inspection, logs, screenshots, or review artifacts. |
| `Blast radius` | string | Systems, users, data, environments, and external effects touched by the decision. |
| `Rollback path` | string or null | How the action can be undone, or why rollback is unavailable. |
| `Alternatives considered` | string | The safe alternatives, including waiting or doing nothing. |

## Validation Role

Deterministic structural validation checks only that the required fields are
present and shaped as field labels with non-empty values. It does not prove truth,
detect false urgency, decide whether the risk is acceptable, or determine whether
evidence is sufficient. Judgment remains with the independent decision owner or
the applicable judge-layer gate.

## Operational Rules

- Human approval cannot substitute for missing executable evidence.
- Human approval cannot override a policy prohibition.
- Delivery consequence is reported next to the decision, but delivery pressure
  never lowers the operational-risk bar.
- The person who gathered the evidence does not get to declare a gate eliminated.
