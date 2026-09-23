---
domain: judge-layer
description: Shared judge-layer contracts for action proposals, outcomes, provenance labels, mandates, decision gates, and judge evaluation suites.
maturity: draft
---

# Judge Layer

> **Scope**: Loaded by judge agents, judge-aware forges, and orchestrators that need
> a shared pre-action contract for side-effecting skills and agents, plus
> authoring-time contracts for human decision gates.

The judge layer is the pre-action authorization boundary for agentic work. It is
not a post-action review loop. A side-effecting actor emits an Action Proposal,
the judge evaluates it against evidence and authorization, and the actor proceeds
only under the returned outcome.

Taxonomy anchor: [PRIMITIVES.md Judge Specialization](https://github.com/cognovis/library/blob/main/docs/PRIMITIVES.md#judge-specialization).

## Contract Pages

| Page | Contract |
|------|----------|
| [Action Proposal](action-proposal.md) | Structured proposal an actor submits before a side effect. |
| [Judge Outcomes](judge-outcomes.md) | Four-outcome decision model and composition precedence. |
| [Provenance Labels](provenance-labels.md) | Evidence labels used by proposals, mandates, and judge reasoning. |
| [Mandate Schema](mandate-schema.md) | AP2-style authorization-as-evidence record. |
| [Decision Brief](decision-brief.md) | Compact manager view and evidence appendix for human operational decisions. |
| [Human Decision Gate](decision-gate.md) | Markdown `## Human Decision Gate` authoring contract mapped to judge outcomes. |
| [Stop Taxonomy](stop-taxonomy.md) | Operational stop vocabulary crosswalked to ADR-0003 risk classes and judge outcomes. |
| [Judge Eval Suite](judge-eval-suite.md) | Evaluation shape and minimum case discipline for judge agents. |

## Action Boundary Mapping

Side-effecting primitives declare `action_boundary` metadata. The metadata names
the proposal schema, judge, and mandate requirement the orchestrator must honor.

| Field | Values |
|-------|--------|
| `risk_class` | `read-only`, `reversible-write`, `external-side-effect`, `high-risk` |
| `effect_type` | `filesystem`, `network`, `financial`, `messaging`, `credential`, `other` |
| `proposal_schema` | `standard://judge-layer/proposals/action-proposal.v1` or a compatible subtype |
| `judge` | `agent://judge-default` or a specialist judge URI |
| `requires_mandate` | Boolean indicating whether a Mandate record is required |

## Release Rule

A judge is release-ready only when it has a paired eval suite with at least 20
cases and reports false allow, false block, escalation, revision, latency, cost,
human override, and incident-catch metrics.
