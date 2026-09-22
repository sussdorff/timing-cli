# Expected Finding: NLSpec-task-missing

**Fixture**: `fixtures/NLSpec-task-missing.json`
**Rule**: `NLSpec Intent required`
**Expected severity**: none

This fixture is a `task` bead with no `metadata.intent`. The NLSpec Pflichtfeld must NOT fire because the shared contract restricts that rule to `feature,epic`.

**Minimum required in output**:
- No Critical finding that references missing `metadata.intent`.
- No verdict override to `NEEDS_INTERACTIVE_WORK_CRITICAL_OVERLAY` due to the NLSpec rule.
- If Pass 3 output is shown, the NLSpec rule is either skipped silently or the report remains CLEAN for that rule.

**Failure mode this fixture guards against**: The type filter is ignored and task beads start failing on feature/epic-only NLSpec requirements.
