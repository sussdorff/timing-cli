# Expected Finding: AC-ZERO

**Fixture**: `fixtures/AC-ZERO.json`
**Pattern**: AC-ZERO — Zero ACs present
**Expected severity**: Critical
**Expected finding excerpt**: The bead has no acceptance_criteria field. Without any acceptance criteria, an agent cannot determine when the work is complete or how to verify the outcome.
**Anti-pattern code in finding**: [AC-ZERO]
**Minimum required in output**: A Critical finding referencing AC-ZERO, noting that no acceptance criteria are present in the bead. The finding may cite the absence of the field or an empty value.
