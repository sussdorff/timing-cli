# Expected Finding: OK-narrow-scope

**Fixture**: `fixtures/OK-narrow-scope.json`
**Pattern**: (none — negative fixture)
**Expected severity**: n/a
**Expected outcome**: NO Pass 2 Critical or HIGH finding.

This fixture is the boundary case for the scope anti-patterns. The bead touches multiple test types (unit + integ) and two concerns at the implementation level (rotation logic + persistence of revoked state), but they share a single review path, a single owner (`TokenService.rotate`), and a single user-visible outcome (replay-window closed). This is "multi-concern with shared review outcome" which the SKILL.md explicitly calls OK.

- Single owner: `TokenService.rotate`.
- Explicit scope-out: token expiry, OAuth consent flow, session management.
- No forward dependency: no "this will be used by future bead X" justification.
- No docs-only output: the bead delivers code and tests.

**Minimum required in output**: Pass 2 reports "Anti-pattern check: CLEAN — no patterns triggered." SCOPE-EPIC, SCOPE-DOCS-ONLY, SCOPE-FORWARD-DEP, SCOPE-MULTI-CONCERN MUST NOT be flagged.

**Failure mode this fixture guards against**: Drift that causes the LLM to flag any bead with more than one AC or more than one MoC type as SCOPE-MULTI-CONCERN. The anti-pattern targets concerns requiring SEPARATE review sessions, not multiple tightly-coupled ACs under one review path.
