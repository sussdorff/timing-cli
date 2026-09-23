# Layer Independence

Repeated cross-project runs (mira, polaris, open-brain, cognovis-core) show each review layer catching a defect class the others miss. Overlap between layers is minimal; skipping a layer removes its class entirely.

## Observed catch profiles

| Layer | Distinct catch profile | Documented evidence |
| --- | --- | --- |
| In-loop review (implementer-paired, orchestrator family) | Quality/TDD completeness, duplicate-code-path omissions when explicitly checked | Repeatedly CLEAN while real regressions existed (polaris-lrgw3, open-brain-amq, CL-du1x) |
| Cold review (fresh context, no loop transcript) | Functional defects hidden by the implementation narrative and mock-based tests | Found 2 blocking defects after CLEAN in-loop (open-brain 5-stage run); still CLEAN on the same security gaps as in-loop |
| Adversarial review (implementer family, break-it framing) | Security regressions, trust-boundary and transactional gaps, partial-failure states, DDL atomicity races, serialization/path/parsing errors | Cross-org overwrite + auth bypass + impersonation (mira-0kxf); 8 Tier-0 trust-boundary regressions after CLEAN Phase 5 (open-brain-jhg); path traversal both same-family passes missed (CL-du1x); warning-instead-of-reject both same-family passes graded PASS (open-brain-amq); DDL race after CLEAN cold review (open-brain-75l) |
| Independent verification (orchestrator family, re-derives) | Gaps beyond the adversarial finding list — re-implements repros against exported functions with fresh inputs, never trusts completion reports or the adversarial recheck's scope | Dual-entry-point divergence and a silently-skipped exclusion case beyond all 4 adversarial findings (polaris-lrgw3) |
| Constraint checker | Dependency CVEs, security defaults, SLOs — out of scope for functional reviewers | open-brain 5-stage run |
| Live UAT (real stack, real data, browser) | Reachability — whether the changed code ever runs | Dead UI component survived 4 review layers (mira-4h07f); feature non-functional on live data despite all-green layers (mira-76rux) |

## Same-family correlation

Two same-family passes (in-loop + cold) are correlated on security-class blind spots when the diff's stated intent is legitimate: both evaluate "does this correctly implement the feature", not "what can an attacker do with it". Cold review is therefore not a substitute for adversarial review, and one adversarial pass is not redundant after a cold pass found issues in the same area (clc-hcdc: two different gaps, same area, different code paths).

## Opposite-family rule

A reviewer's findings route to the opposite model family for fixing (clc-dty AK3b): in-loop reviewer = orchestrator family, fixes route to implementer family; adversarial reviewer = implementer family, fixes route to orchestrator family. This yields cross-model coverage at every transition and prevents hidden self-review loops.

## Adversarial convergence

For guardrail, pattern-matching, or shared-surface changes, one patch-and-recheck cycle is not terminal:

- Successive adversarial rounds find progressively narrower bypasses; convergence is typically reached in 2-3 rounds (clc-wwai; DCG deny-rule hardening).
- A round-N fix is itself review input for round N+1 — a fix can introduce a new bypass or false positive.
- Each finding signals a pattern class to generalize ("any token of this shape"), not a single example to patch.
- Adversarial fix passes are routinely incomplete (5/8 resolved in one cycle, 2/4 still broken on the fixer's own recheck); the recheck is part of the layer, and the verifier re-probes beyond the flagged scope.
