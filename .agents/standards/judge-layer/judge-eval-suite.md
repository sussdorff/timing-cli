# Judge Eval Suite

Contract URI: `standard://judge-layer/evals/judge-eval-suite.v1`

Maturity: draft.

A judge eval suite measures whether a judge blocks bad actions without blocking
legitimate work. A judge without an eval suite is not release-ready.

Related contracts: [Action Proposal](action-proposal.md), [Judge Outcomes](judge-outcomes.md),
[Provenance Labels](provenance-labels.md), [Mandate Schema](mandate-schema.md).

## Minimum Case Discipline

| Requirement | Rule |
|-------------|------|
| Case count | At least 20 cases before a judge ships. |
| Outcome coverage | Include `ALLOW`, `BLOCK`, `REVISE`, and `ESCALATE`. |
| Allow coverage | Include at least 4 legitimate `ALLOW` cases so `false_block_rate` is a useful regression signal. |
| Risk coverage | Include at least one `external-side-effect` case and one `high-risk` case. |
| Evidence coverage | Include observed, inferred, generated, confirmed, disputed, and superseded evidence. |
| Mandate coverage | Include valid, missing, expired, out-of-scope, and superseded mandates. |

## Case Shape

| Field | Meaning |
|-------|---------|
| `case_id` | Stable identifier. |
| `proposal` | Action Proposal under test. |
| `context_refs` | Evidence, policy, files, records, or conversation snippets visible to the judge. |
| `expected_decision` | Expected `ALLOW`, `BLOCK`, `REVISE`, or `ESCALATE`. |
| `expected_reason_category` | Expected reason class such as `authorization`, `evidence`, `scope`, `policy`, or `schema`. |
| `risk_notes` | Human explanation of why the case matters. |

## Required Metrics

| Metric | Meaning |
|--------|---------|
| `false_allow_rate` | Bad or unauthorized proposals incorrectly allowed. |
| `false_block_rate` | Legitimate proposals incorrectly blocked. |
| `escalation_rate` | Share of cases escalated to a human or higher authority. |
| `revision_rate` | Share of cases requiring bounded proposal changes. |
| `latency_p50` | Median judge latency. |
| `latency_p95` | 95th percentile judge latency. |
| `cost_per_judged_action` | Average inference/tool cost per decision. |
| `human_override_rate` | Share of human-reviewed cases where the judge was overridden. |
| `incidents_caught_before_execution` | Count of unsafe actions caught pre-action. |

## Baseline Failure Modes

The default suite for a generic judge should include cases for wrong recipient,
missing authorization, stale memory, ambiguous instruction, unauthorized external
party, sensitive attachment, destructive tool arguments, public/internal audience
mix-up, wrong account, partial authorization, expired mandate, superseded mandate,
disputed evidence, generated-only evidence, malformed proposal, missing rollback,
irreversible action, policy conflict, revision that becomes safe, and a clean
low-risk allow. Add additional clean allow cases for read-only work, reversible
local writes, valid external mandates, and valid high-risk mandates when using
the suite for regression tracking.
