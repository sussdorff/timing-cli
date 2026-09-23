# Test Fixture: tdd-authoring

## Test 1 — Happy path

**Input:** Author a RED slice whose Then comes from a pinned IG element.
**Expected behavior:** Load skill `tdd` for seams; write only under the declared
test tree; run VERIFY then `classify_author_slice`; return `tdd_evidence_v1`.
**Pass criteria:** Envelope lists structured provenance; RED command is non-zero
for the expected reason.

## Test 2 — Relabeled tautology

**Input:** Expected value labeled `worked_example` but sourced from
"implementation output".
**Expected behavior:** `verify_expected_sources.py` rejects; not accepted RED.
**Pass criteria:** status is rejected; no GREEN handoff.
