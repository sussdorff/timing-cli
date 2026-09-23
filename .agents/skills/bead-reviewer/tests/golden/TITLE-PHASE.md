# Expected Finding: TITLE-PHASE

**Fixture**: `fixtures/TITLE-PHASE.json`
**Pattern**: TITLE-PHASE — Phase-name without outcome
**Expected severity**: Critical
**Expected verdict label after contract promotion**: `NEEDS_INTERACTIVE_WORK_CRITICAL_OVERLAY`
**Expected finding excerpt**: The title "Setup Database" starts with a phase-name verb ("Setup") without naming the user or system outcome delivered. The title describes an activity phase rather than the value the work produces.
**Anti-pattern code in finding**: [TITLE-PHASE]
**Minimum required in output**: A Critical finding referencing TITLE-PHASE, citing the title text "Setup Database", noting that a phase-name verb is present without a stated outcome. After the rule move into `bead-hygiene.md`, the report should use the overlay verdict suffix rather than the semantic suffix.
