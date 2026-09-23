# Evidence Contract

Final status derives from the complete evidence contract, not from reviewer confidence, reviewer verdicts, or pressure to finish. The bead status and dependency graph — not archived reports — encode the operational truth: archived evidence nobody reads has no risk-control value, so a missing required Means of Compliance keeps the bead open and the defect visible even when code, CI, and reviewers are green.

## The no-skip rule

| Situation | Classification |
| --- | --- |
| Executable MoC (integration test, script, real-infra run) ran to completion and passed | AC verified with that evidence |
| Executable MoC could not execute (missing schema bootstrap, missing fixture, missing infra) or was interrupted before exercising the code path | DISPUTED with fixability=human — not PARTIAL, not UNVERIFIABLE, not a narrative pass, not a disclosed skip. Hard VETO; the bead stays in_progress. Missing prerequisites become blocking beads (open-brain-y4b → open-brain-fhb) |
| A failing test points at a concrete code bug an agent can fix autonomously | DISPUTED with fixability=auto |
| Integration test self-skips in the verification environment | Counts as never executed — the no-skip rule applies |

PARTIAL implies passing evidence exists; UNVERIFIABLE implies the AC is inherently unattestable. Interrupted execution is neither — zero live evidence was gathered, which is a genuine dispute.

## Human waiver of a VETO

A DISPUTED hard VETO may be overridden by an explicit human waiver only when both hold (polaris-oavrs):

1. Non-completion is demonstrably unrelated to the bead's own change — e.g. a pre-existing infra defect filed as its own bead, or known live-environment flakiness that passed the same credential/sanity check earlier in the run.
2. All code-level ACs are independently verified with strong evidence (full test suite, typecheck, adversarial review with zero regressions).

## Label vs delivered evidence

When a MoC label and the delivered test level disagree (MoC says `integ`, delivery is unit-level), the surrounding domain's test conventions decide — neither auto-fail on the literal label nor auto-accept the downgrade. A label judged a mislabel is reclassified, not padded out with new test surface that violates domain conventions.

## Re-derive, never trust

- Self-reported test counts and "this fixes it" claims are independently re-run: the full suite once, plus the specific regression tests per fix commit. A matching count is meaningful because it was re-derived, not because it matched.
- Diagnostic artifacts prove only what they directly observed: a screenshot of an authentication failure is diagnosis evidence, never successful-UAT evidence.
- A fixed adversarial-review cap has honest terminal semantics: confirmed findings repaired within the cap, remaining advisories recorded explicitly, no invented extra clean round, and the last reviewer output never outranks deterministic evidence.
