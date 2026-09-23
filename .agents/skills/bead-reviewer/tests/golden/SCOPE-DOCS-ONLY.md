# Expected Finding: SCOPE-DOCS-ONLY

**Fixture**: `fixtures/SCOPE-DOCS-ONLY.json`
**Pattern**: SCOPE-DOCS-ONLY — Pure docs-bead inside feature work
**Expected severity**: Critical
**Expected finding excerpt**: The bead description states "No code changes are required — this bead is purely documentation updates for functionality already shipped." The bead's only output is documentation for a feature delivered in another bead (clc-xyz.3). Documentation updates should accompany the implementation bead rather than exist as a standalone bead during active feature work.
**Anti-pattern code in finding**: [SCOPE-DOCS-ONLY]
**Minimum required in output**: A Critical finding referencing SCOPE-DOCS-ONLY, citing text such as "purely documentation updates" or "No code changes are required", noting that documentation for an already-delivered feature should have accompanied the implementation bead.
