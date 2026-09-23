# Mandate Schema

Contract URI: `standard://judge-layer/mandates/mandate.v1`

Maturity: draft.

A Mandate is an authorization-as-evidence record. It proves that an actor may
operate within a bounded scope; it does not authorize actions outside that scope.

Related contracts: [Action Proposal](action-proposal.md), [Judge Outcomes](judge-outcomes.md),
[Provenance Labels](provenance-labels.md), [Decision Gate](decision-gate.md),
[Judge Eval Suite](judge-eval-suite.md).

Standing mandates are still `standard://judge-layer/mandates/mandate.v1`
records. A `## Human Decision Gate` may reference a Mandate, but it does not
define a parallel authorization object or weaken this schema's validity rules.

## Required Fields

| Field | Type | Meaning |
|-------|------|---------|
| `mandate_id` | string | Stable identifier for proposals, logs, and audits. |
| `scope` | object | Actions, targets, systems, accounts, and time range covered. |
| `limits` | object | Amount caps, recipient constraints, allowed verbs, approval ceilings, or other boundaries. |
| `evidence_refs` | array | Sources proving the mandate, each with a provenance label. |
| `granted_at` | timestamp | When the mandate was granted. |
| `granted_by` | object | Person, role, system, or policy authority that granted it. |
| `expires_at` | timestamp or null | Expiration time. `null` means no explicit expiry, not permanent authority. |
| `supersedes` | array | Mandate IDs this record replaces. |

## Optional Fields

| Field | Meaning |
|-------|---------|
| `subject_ref` | Actor, user, service account, or organization receiving the authority. |
| `delegation_chain` | Chain of grants when authority is delegated. |
| `revoked_at` | Time the mandate was revoked. |
| `notes` | Non-authoritative explanation for auditors. |

## Optional Profile: Transport Authorization

Transport adapters may reuse the Mandate shape above with fields needed for
deterministic pre-handler checks. This profile does not replace the judge-layer
Action Proposal flow from ADR-0003.

Transport-layer mandates SHOULD include these fields when they authorize
mutation, session-write, external-side-effect, or high-risk tools. They remain
profile fields rather than base required fields because non-transport judge
consumers share the same Mandate contract.

| Field | Meaning |
|-------|---------|
| `session_binding` | MCP transport, server-session identity digest, workspace-root digest, run ID, bead ID, phase, and allowed tool scope. |
| `replay` | Replay-prevention metadata such as `jti`, nonce digest, `single_use`, and consumed-at timestamp. |
| `policy_ref` | Policy version and digest that were active when the mandate was issued. |
| `audience` | Expected MCP server, daemon, or launcher identity. |
| `revocation_ref` | Lookup key for the revocation registry. |
| `storage_ref` | Non-secret reference to the issuer-side grant record. |
| `redaction` | Fields that must be digested or omitted in audit output. |

Transport authorization grants must be checked for issuer trust, scope,
workspace/run/bead/phase binding, expiry, revocation, replay, and policy digest
before dispatching the tool handler.

## Validity Rules

| Condition | Judge interpretation |
|-----------|----------------------|
| Proposal target is outside `scope` | `BLOCK`. |
| Proposal exceeds `limits` | `BLOCK`. |
| Mandate is expired, revoked, superseded, or disputed | `ESCALATE` or `BLOCK` based on policy. |
| Runtime revocation lookup finds the mandate ID | `BLOCK`. |
| `replay.single_use` mandate has already consumed its `jti` or nonce | `BLOCK`. |
| `session_binding` does not match the current session, workspace, run, bead, or phase | `BLOCK`. |
| Mandate evidence is generated-only | Treat as insufficient for side effects. |
| `expires_at` is null for `high-risk` action | `ESCALATE` unless another policy sets a shorter operational window. |
| MCP transport grant issuer is not trusted | `BLOCK` before handler dispatch. |

## Minimal Shape

```json
{
  "mandate_id": "mandate-2026-05-14-001",
  "scope": {
    "verbs": ["send"],
    "targets": ["email"],
    "accounts": ["user@example.com"]
  },
  "limits": {
    "recipients": ["customer@example.com"],
    "attachments_allowed": false
  },
  "evidence_refs": [
    {
      "ref": "conversation://current/user-confirmation",
      "label": "observed"
    }
  ],
  "granted_at": "2026-05-14T10:00:00Z",
  "granted_by": {
    "type": "user",
    "ref": "user://current"
  },
  "expires_at": "2026-05-14T11:00:00Z",
  "supersedes": []
}
```
