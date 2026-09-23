# Finding Adjudication

Adversarial and audit findings are hypotheses, not authority. Each finding is adjudicated against the canonical source of truth before it drives a fix, a block, or an escalation.

For repository delivery, adjudication is interrupt-only. Clean consistent perspectives
continue without an adjudicator. Disputed findings, contradictory recommendations,
suspicious summaries, or intent mismatch interrupt normal progression and return a
typed disposition to the repository delivery owner. Accepted Medium-or-higher findings
go directly to the implementation-owned repair lineage. Its current writing session
may change only through the validated compact committed handoff; the logical owner and
accepted findings remain unchanged.

## Adjudication rules

| Rule | Detail | Documented evidence |
| --- | --- | --- |
| Verify against the consuming code path | For any "audit found X is wrong" claim, the code path that actually uses the value decides — not the audit's reasoning | Claimed EBM URI mismatch was a non-issue: the evaluator joined on a different field than the audit assumed |
| A cited safeguard counts only if it is live | A finding (or a finding's rejection) that cites an ADR, spec, or code safeguard is only as good as verifying that mechanism is wired into the running pipeline — ADRs describe intent, not runtime behavior | Council CRITICAL cited an ADR-027 generalization safeguard that was dead code, never wired in (polaris-mz3wg); resolution deleted the dead code and amended the ADR in place |
| Reject, but trace upstream | A finding contradicted by the contract is rejected — yet the signal is traced upstream, because a false downstream accusation can still reveal a real producer defect | Verification-governance principle set (mira adapter chain) |
| BLOCKING requires a functional defect tied to a stated AC | Resilience, SQL-style, and MoC-documentation nitpicks are ADVISORY even when legitimate; review loops do not stall on non-blocking concerns | open-brain-brt review chain |
| Pre-existing vs introduced | A failing test is attributed to the current diff only after checking it at the base commit (git blame / checkout-base-and-rerun); identical failure at base = pre-existing flake, not a review blocker | Isolation-only DB failure predated the diff verbatim (open-brain-brt) |

## Out-of-scope findings

Discovered-but-out-of-scope issues become separate tracked beads in the same chain, not inline fixes — including real pre-existing bugs an adversarial round surfaces in adjacent code. Dispatch tiers: `orchestrator/scope-creep-policy.md`.
