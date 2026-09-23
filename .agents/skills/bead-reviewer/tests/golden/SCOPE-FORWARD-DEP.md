# Expected Finding: SCOPE-FORWARD-DEP

**Fixture**: `fixtures/SCOPE-FORWARD-DEP.json`
**Pattern**: SCOPE-FORWARD-DEP — Forward-dependency on unplanned work
**Expected severity**: Critical
**Expected finding excerpt**: The description states "This will be used by future bead X once it is created" and "enables future bead Y (multi-repo audit mode) once that work is planned." The bead justifies itself by speculative future work that does not yet exist. Work built solely to support unplanned future beads is premature and may never be integrated.
**Anti-pattern code in finding**: [SCOPE-FORWARD-DEP]
**Minimum required in output**: A Critical finding referencing SCOPE-FORWARD-DEP, citing phrases such as "will be used by future bead X once it is created" or "once that work is planned", noting that the bead's justification relies on unplanned speculative future work.
