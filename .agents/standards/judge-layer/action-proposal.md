# Action Proposal

Contract URI: `standard://judge-layer/proposals/action-proposal.v1`

Maturity: draft.

An Action Proposal is the structured object a side-effecting actor submits before
execution. It is evaluated by a judge before the side effect happens.

Related contracts: [Judge Outcomes](judge-outcomes.md), [Provenance Labels](provenance-labels.md),
[Mandate Schema](mandate-schema.md), [Judge Eval Suite](judge-eval-suite.md).

## Required Fields

| Field | Type | Meaning |
|-------|------|---------|
| `proposal_id` | string | Stable identifier for logs, eval cases, and mandates. |
| `actor_ref` | string | Skill, agent, or script proposing the action. |
| `risk_class` | enum | `read-only`, `reversible-write`, `external-side-effect`, or `high-risk`. |
| `effect_type` | enum | `filesystem`, `network`, `financial`, `messaging`, `credential`, or `other`. |
| `intended_action` | object | Verb, target, arguments, and external system affected. |
| `reason` | string | Why the actor believes the action is needed. |
| `evidence_refs` | array | Source references supporting the proposal, each with a provenance label. |
| `authorization` | object or null | Mandate reference or inline authorization evidence. |
| `expected_consequence` | string | Expected external/user-visible result if allowed. |
| `rollback_path` | string or null | How the action can be undone; `null` only when impossible. |

## Validation Rules

| Rule | Judge consequence |
|------|-------------------|
| Missing required field | `ESCALATE` with reason category `schema`. |
| `risk_class` is `external-side-effect` or `high-risk` and no authorization exists | `BLOCK` unless policy explicitly allows mandate-free execution. |
| Evidence is only actor-generated and not independently observed, confirmed, or mandated | `REVISE` or `ESCALATE`, depending on risk. |
| `rollback_path` is null for `high-risk` actions | `ESCALATE` unless the mandate explicitly accepts irreversible action. |
| Intended target does not match authorization scope | `BLOCK`. |

## Deterministic Pre-Validation

Before a caller sends a proposal to a judge, it should run:
`python3 standards/judge-layer/scripts/validate_action_proposal.py <proposal-file>`.

The script checks required fields, enum values, nested `intended_action` shape,
and provenance label shape. It does not decide authorization or policy; those
remain judge responsibilities.

## Minimal Shape

```json
{
  "proposal_id": "proposal-2026-05-14-001",
  "actor_ref": "skill://mail-send",
  "risk_class": "external-side-effect",
  "effect_type": "messaging",
  "intended_action": {
    "verb": "send",
    "target": "email",
    "arguments": {}
  },
  "reason": "User asked to send the prepared message.",
  "evidence_refs": [
    {
      "ref": "conversation://current/user-request",
      "label": "observed"
    }
  ],
  "authorization": {
    "mandate_ref": "mandate://user/current-session/send-email"
  },
  "expected_consequence": "The recipient receives the message.",
  "rollback_path": "Send a correction or recall request if supported."
}
```
