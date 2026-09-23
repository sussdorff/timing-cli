# Provenance Labels

Contract URI: `standard://judge-layer/provenance/provenance-label.v1`

Maturity: draft.

Provenance labels describe the evidence basis for claims in Action Proposals,
Mandates, judge outcomes, and eval cases. They do not grant authority by
themselves.

Related contracts: [Action Proposal](action-proposal.md), [Judge Outcomes](judge-outcomes.md),
[Mandate Schema](mandate-schema.md), [Judge Eval Suite](judge-eval-suite.md).

## Labels

| Label | Meaning | Typical use |
|-------|---------|-------------|
| `observed` | Directly read from a source, tool result, file, conversation, or API response. | User instruction, account record, current file state. |
| `inferred` | Derived from observed evidence through model reasoning. | Intent classification, risk assessment, likely recipient identity. |
| `generated` | Created by the actor or model, not independently verified. | Draft email body, proposed filename, generated summary. |
| `confirmed` | Verified by an authority or second independent source. | User confirmation, policy lookup, account owner match. |
| `disputed` | Conflicting evidence exists or the claim is contested. | Mismatched recipient, stale memory, contradictory user statements. |
| `superseded` | Previously valid evidence replaced by newer evidence. | Expired mandate, changed instruction, updated record. |

## Evidence-vs-Instruction Rule

Evidence can support an instruction, but evidence is not automatically authority.
A user request, policy record, or mandate may authorize action only within its
explicit scope and limits.

## Label Strength

| Stronger for authorization | Weaker for authorization |
|----------------------------|--------------------------|
| `confirmed` mandate within scope | `generated` actor claim |
| `observed` current user instruction | `inferred` intent without confirmation |
| `observed` policy or account state | `superseded` or `disputed` source |

For `external-side-effect` and `high-risk` actions, a judge should treat
generated-only evidence as insufficient unless a mandate explicitly allows it.

## Transition Rules

| Transition | Meaning |
|------------|---------|
| `observed` -> `confirmed` | A second source or authority validates the claim. |
| `observed` -> `disputed` | A later source conflicts with the claim. |
| `confirmed` -> `superseded` | A newer mandate, instruction, or record replaces it. |
| `generated` -> `observed` | Generated content is written, sent, or otherwise materialized and can now be inspected. |
