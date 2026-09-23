# Expected Finding: AC-REF

**Fixture**: `fixtures/AC-REF.json`
**Pattern**: AC-REF — AC references only other beads without stating the criterion
**Expected severity**: Critical
**Expected finding excerpt**: The acceptance criterion "See bead clc-abc.1 for the acceptance criteria. The implementation must satisfy all criteria documented in that bead." defers entirely to another bead without stating what the actual criterion is. An agent cannot evaluate completion without following the external reference.
**Anti-pattern code in finding**: [AC-REF]
**Minimum required in output**: A Critical finding referencing AC-REF, citing text such as "See bead clc-abc.1 for the acceptance criteria", noting that the AC body contains no criterion and defers entirely to an external bead reference.
