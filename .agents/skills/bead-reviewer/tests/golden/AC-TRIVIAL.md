# Expected Finding: AC-TRIVIAL

**Fixture**: `fixtures/AC-TRIVIAL.json`
**Pattern**: AC-TRIVIAL — Trivial, unmeasurable AC
**Expected severity**: Critical
**Expected finding excerpt**: The acceptance criterion "The feature works correctly and all tests pass. Functions as expected without errors." is trivially true for any feature and provides no observable, measurable criterion. "Works correctly" and "functions as expected" are circular and cannot be verified.
**Anti-pattern code in finding**: [AC-TRIVIAL]
**Minimum required in output**: A Critical finding referencing AC-TRIVIAL, citing text such as "works correctly" or "all tests pass" or "functions as expected", noting that these phrases are unmeasurable and do not define a verifiable outcome.
