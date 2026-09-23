# Judge Outcomes

Contract URI: `standard://judge-layer/outcomes/judge-outcome.v1`

Maturity: draft.

Judges return one of four outcomes for every well-formed Action Proposal:
`ALLOW`, `BLOCK`, `REVISE`, or `ESCALATE`.

Related contracts: [Action Proposal](action-proposal.md), [Provenance Labels](provenance-labels.md),
[Mandate Schema](mandate-schema.md), [Judge Eval Suite](judge-eval-suite.md).

## Outcome Semantics

| Outcome | Meaning | Actor behavior |
|---------|---------|----------------|
| `ALLOW` | Proposal is within evidence, authorization, and policy boundaries. | Execute exactly the approved action and log the decision. |
| `BLOCK` | Proposal must not execute. The defect is substantive, not just incomplete. | Halt and record the reason. |
| `REVISE` | Proposal could be allowed after bounded changes. | Produce one revised proposal and submit it again. |
| `ESCALATE` | Human or higher-authority review is required. | Halt, record the escalation target, and do not execute. |

## Composition Rule

When multiple checks produce different outcomes, use this precedence:

`BLOCK > ESCALATE > REVISE > ALLOW`

`BLOCK` wins because a known prohibition must not be softened by uncertainty or
style feedback. `ESCALATE` wins over `REVISE` because a judge cannot revise its
way through missing authority. `REVISE` wins over `ALLOW` because the action is
not approved until the requested change is incorporated.

## Output Fields

| Field | Required | Meaning |
|-------|----------|---------|
| `decision` | yes | One of `ALLOW`, `BLOCK`, `REVISE`, `ESCALATE`. |
| `reason` | yes | Concise human-readable basis for the decision. |
| `reason_category` | yes | `schema`, `authorization`, `evidence`, `scope`, `policy`, `risk`, or `other`. |
| `policy_version` | no | Identifier for the judge ruleset, prompt, or policy version used for the decision. |
| `constraints` | no | Conditions attached to an `ALLOW`. |
| `revised_proposal` | no | Replacement proposal for `REVISE`. |
| `escalation_target` | no | Person, role, system, or queue for `ESCALATE`. |
| `provenance_refs` | yes | Evidence references the judge used, labeled by provenance. |

## Policy Version

Judges may include `policy_version` when the outcome should be auditable against
a specific ruleset, prompt revision, or policy bundle. The field is optional so
existing judges remain valid, but consumers that persist judge decisions should
store it when present. This supports policy-drift audits and stale-judgment
detection after judge instructions or governing policies change.

## Provenance Requirement

Every non-`ALLOW` outcome names the failed evidence, authorization, policy, or
scope boundary. Every `ALLOW` outcome names the evidence and mandate that made
the action permissible.
