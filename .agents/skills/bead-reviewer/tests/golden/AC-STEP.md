# Expected Finding: AC-STEP

**Fixture**: `fixtures/AC-STEP.json`
**Pattern**: AC-STEP — AC as implementation step
**Expected severity**: Critical
**Expected finding excerpt**: The acceptance criterion starts with "Write a function that validates user email format" — this describes an implementation step (writing a function) rather than an observable system outcome. A valid AC would state what the system does or refuses to do, not how to implement it.
**Anti-pattern code in finding**: [AC-STEP]
**Minimum required in output**: A Critical finding referencing AC-STEP, citing the AC text beginning with "Write a function", noting that the AC describes an implementation action rather than an observable outcome.
