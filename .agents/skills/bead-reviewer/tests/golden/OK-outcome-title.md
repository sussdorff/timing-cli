# Expected Finding: OK-outcome-title

**Fixture**: `fixtures/OK-outcome-title.json`
**Pattern**: (none — negative fixture)
**Expected severity**: n/a
**Expected outcome**: NO Pass 2 Critical or HIGH finding.

This fixture exists to prevent over-flagging regressions in Pass 2. The bead is well-formed:
- Title names a user outcome ("Users can register with email and password") — does NOT match TITLE-PHASE / TITLE-ACTIVITY / TITLE-PATH / TITLE-VAGUE.
- ACs describe observable outcomes (registration completes, duplicate-email returns 409, weak password returns 422) — does NOT match AC-STEP / AC-ZERO / AC-TRIVIAL / AC-REF.
- Single concern (registration flow), explicit scope-out list, no forward dependency — does NOT match SCOPE-EPIC / SCOPE-DOCS-ONLY / SCOPE-FORWARD-DEP / SCOPE-MULTI-CONCERN.
- No conflict with any ADR — does NOT match ADR-VIOLATION.

**Minimum required in output**: Pass 2 reports "Anti-pattern check: CLEAN — no patterns triggered." and "ADR check: CLEAN — no ADR violations detected." The 5-category rubric may produce PASS or WARN entries but MUST NOT produce FAIL.

**Failure mode this fixture guards against**: If a future Pass 2 prompt drift causes the LLM to flag well-formed beads as Critical (over-flagging), this fixture's golden file is violated.
