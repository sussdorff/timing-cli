---
domain: review-governance
description: Empirically grounded governance rules for multi-layer bead review — layer independence, finding adjudication, the evidence contract, and documented test blind spots.
---

# Review Governance

> **Scope**: Dev-plane standard for bead review pipelines (in-loop, cold, adversarial, verification, constraint, live UAT). Loaded by review, orchestration, and verification skills/agents that weigh reviewer verdicts or derive bead status from review outcomes.

## Core rules

| Rule | Detail |
| --- | --- |
| Review layers are non-substitutable | Each layer catches a disjoint defect class; a CLEAN verdict at one layer carries no information about the next. Same-family passes share blind spots. See [Layer independence](layer-independence.md). |
| Opposite-family fixes | A reviewer's findings are fixed by the opposite model family, never by the reviewer that surfaced them. |
| Findings are hypotheses | Every finding — including CRITICAL council findings — is adjudicated against live code and ground truth before it drives a fix. See [Finding adjudication](finding-adjudication.md). |
| Evidence contract over confidence | Final bead status derives from the complete evidence contract, not from reviewer confidence or pressure to finish. Unexecuted executable MoC is a VETO, not a skip. See [Evidence contract](evidence-contract.md). |
| Green tests are bounded evidence | Agreement-only tests, mocked I/O, hand-authored fixtures, and diff-scoped review each have documented blind spots; only live execution proves reachability. See [Test blind spots](test-blind-spots.md). |

## Related standards

- `orchestrator/scope-creep-policy.md` — dispatch tiers for out-of-scope findings.
- `orchestrator/review-quality-signals.md` — provider contract for heuristic quality signals.
