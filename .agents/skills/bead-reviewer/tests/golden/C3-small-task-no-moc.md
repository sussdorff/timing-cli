# Expected Finding: C3-small-task-no-moc

**Fixture**: `fixtures/C3-small-task-no-moc.json`
**Rule**: `MoC Table required (task/bug medium+)` - EXEMPT because effort=small
**Expected severity**: none

This fixture is a `task` bead with `routed_effort=small` and no MoC table.
The effort-filtered MoC rule must NOT fire because small effort is below the threshold.

**Minimum required in output**:
- NO Critical finding about missing MoC table for this task.
- The task with small effort passes Criterion 3 (skipped/exempt).

**Failure mode this fixture guards against**: Effort filter ignored - all task beads
flagged for missing MoC regardless of routed_effort.
