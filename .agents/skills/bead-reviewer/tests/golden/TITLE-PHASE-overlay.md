# Expected Finding: TITLE-PHASE-overlay

**Fixture**: `fixtures/TITLE-PHASE.json`
**Rule**: `TITLE-PHASE`
**Expected severity**: Critical
**Expected source**: `standards/workflow/bead-hygiene.md`
**Expected verdict label**: `NEEDS_INTERACTIVE_WORK_CRITICAL_OVERLAY`

This fixture now includes a valid MoC table so the title-shape violation remains the only promoted-rule failure under the shared contract.

**Minimum required in output**:
- A Critical finding referencing `TITLE-PHASE`.
- The finding cites the title text `Setup Database`.
- The report attributes the finding to the shared contract in `bead-hygiene.md`.
- The verdict uses `NEEDS_INTERACTIVE_WORK_CRITICAL_OVERLAY`, not the semantic suffix.

**Failure mode this fixture guards against**: The anti-pattern fires correctly but still reports the old semantic verdict suffix after the rule source moved into Pass 3.
