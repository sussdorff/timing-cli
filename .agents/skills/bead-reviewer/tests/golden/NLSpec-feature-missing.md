# Expected Finding: NLSpec-feature-missing

**Fixture**: `fixtures/NLSpec-feature-missing.json`
**Rule**: `NLSpec Intent required`
**Expected severity**: Critical
**Expected source**: `standards/workflow/bead-hygiene.md`
**Expected verdict label**: `NEEDS_INTERACTIVE_WORK_CRITICAL_OVERLAY`

This fixture is otherwise clean on description, AC shape, MoC, and sizing. The only promoted-rule failure is the missing `metadata.intent` field for a `feature` bead.

**Minimum required in output**:
- A Critical Pass 3 finding that cites missing `metadata.intent`.
- The finding references the shared contract rule from `bead-hygiene.md`.
- The report uses the overlay verdict suffix `NEEDS_INTERACTIVE_WORK_CRITICAL_OVERLAY`.

**Failure mode this fixture guards against**: The NLSpec Pflichtfeld loses its `feature,epic` filter or stops blocking feature beads that omit `metadata.intent`.
