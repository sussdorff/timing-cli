# Expected Finding: C3-large-task-no-moc

**Fixture**: `fixtures/C3-large-task-no-moc.json`
**Rule**: `MoC Table required (task/bug medium+)`
**Expected severity**: critical

This fixture is a `task` bead with `routed_effort=large` and no MoC table.
With Step 0.5 populating routed_effort before Pass 3 evaluation, the effort-filtered
MoC rule MUST fire as a Critical finding.

**Minimum required in output**:
- Critical finding citing the missing MoC table.
- `spec_verdict` must be `NEEDS_INTERACTIVE_WORK` or stricter.

**Failure mode this fixture guards against**: Step 0.5 not populating routed_effort
before Pass 3 evaluation, causing the effort-filtered MoC rule to silently skip.
