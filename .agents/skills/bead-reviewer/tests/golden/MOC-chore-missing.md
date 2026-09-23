# Expected Finding: MOC-chore-missing

**Fixture**: `fixtures/MOC-chore-missing.json`
**Rule**: `MoC Table required`
**Expected severity**: none

This fixture is a `chore` bead with no MoC table. The shared contract keeps the MoC rule unfiltered, but the rule text explicitly allows chores to omit the table.

**Minimum required in output**:
- No Critical finding that says the chore bead is missing a MoC table.
- No verdict override to `NEEDS_INTERACTIVE_WORK_CRITICAL_OVERLAY` due to the MoC rule.
- If Pass 3 output is shown, the MoC rule is treated as satisfied or not applicable for this chore bead.

**Failure mode this fixture guards against**: The reviewer applies the MoC Pflichtfeld as a blanket Critical requirement and blocks chores that are meant to stay exempt.
