# Stop Taxonomy and Operational Risk

Contract URI: `standard://judge-layer/stops/stop-taxonomy.v1`

Maturity: draft.

This standard defines authoring-time vocabulary for when work must stop for a
human decision or judge-layer outcome. It extends ADR-0003 by naming how
operational decision briefs describe stops; it does not create a competing
runtime taxonomy.

Related contracts: [Decision Brief](decision-brief.md), [Decision Gate](decision-gate.md),
[Judge Outcomes](judge-outcomes.md), [Action Proposal](action-proposal.md), and
[ADR-0003](../../docs/adr/ADR-0003-judge-layer-architecture.md).

## Crosswalk to ADR-0003 `risk_class`

Use ADR-0003's `risk_class` enum as the source of truth:

| `risk_class` | Authoring-time operational meaning | Typical stop posture |
|--------------|------------------------------------|----------------------|
| `read-only` | Observation or inspection only; no system mutation. | Usually no human gate unless evidence is incomplete or sensitive. |
| `reversible-write` | Local or bounded mutation with a concrete rollback path. | Gate when rollback confidence, sequencing, or ownership is uncertain. |
| `external-side-effect` | Action affects an external system, recipient, deployment, or shared service. | Gate unless a current Mandate or explicit policy already authorizes the action. |
| `high-risk` | Irreversible, security-sensitive, production-critical, credential, financial, or broad-impact action. | Stop by default until independent concurrence or a valid Mandate resolves authority. |

## Crosswalk to Judge Outcomes

Decision gates use the same four outcomes as the judge layer:

| Outcome | Stop-taxonomy meaning |
|---------|-----------------------|
| `ALLOW` | Proceed exactly within the presented evidence and constraints. |
| `BLOCK` | Do not proceed; the proposed action is prohibited or outside the acceptable boundary. |
| `REVISE` | Change the proposal, gather specified evidence, or narrow scope before asking again. |
| `ESCALATE` | Route to a human decision owner or higher authority because schema, evidence, risk, or authorization cannot be resolved locally. |

The composition precedence remains ADR-0003's `BLOCK > ESCALATE > REVISE > ALLOW`.

## Required Operational Rules

- Deterministic predicates establish bounds; independent judgment settles the
  final class within those bounds.
- Risk upgrades are unilateral: any reviewer, gate, or decision owner may raise
  operational risk when evidence shows broader blast radius or weaker rollback.
- Downgrades require independent concurrence from someone other than the person
  who gathered the evidence.
- Delivery pressure never lowers the operational-risk bar.
- Investigation may create, strengthen, weaken, or eliminate a gate.
- Whoever gathered the evidence does not get to declare the gate eliminated.

## Stop Classes

| Stop class | Meaning | Allowed resolution |
|------------|---------|--------------------|
| `schema-stop` | Required fields, evidence references, or outcome vocabulary are missing. | `REVISE` or `ESCALATE`; structural validator output is sufficient evidence of the shape defect. |
| `evidence-stop` | The action lacks required executable or read-only evidence. | `REVISE` until evidence exists; human approval alone is not evidence. |
| `authorization-stop` | No current Mandate or explicit owner approval authorizes the side effect. | `ESCALATE` to the decision owner or provide a valid Mandate reference. |
| `risk-stop` | Blast radius, reversibility, timing, or do-nothing cost is judgmental. | `ESCALATE` to the decision owner with a Decision Brief. |
| `policy-stop` | A policy prohibits the action. | `BLOCK`; human approval cannot override the prohibition unless the policy itself permits that exception path. |

## Incident Reference

`clc-h4nm` is the non-blocking incident reference that motivated this standard.
Its old-regime authorization remains recorded for that bead; this standard
governs new authoring and readiness checks going forward.
