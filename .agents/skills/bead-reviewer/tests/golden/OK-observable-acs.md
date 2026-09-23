# Expected Finding: OK-observable-acs

**Fixture**: `fixtures/OK-observable-acs.json`
**Pattern**: (none — negative fixture)
**Expected severity**: n/a
**Expected outcome**: NO Pass 2 Critical or HIGH finding.

This fixture is the boundary case for the AC-shape anti-patterns. Each AC describes a precise observable outcome ("creates exactly one audit record with these fields", "returns failed-login records filtered by username", "records older than 90 days are not returned"). None starts with "Write", "Implement", or "Create"; none is trivial ("works correctly"); none defers to another bead.

**Minimum required in output**: Pass 2 reports "Anti-pattern check: CLEAN — no patterns triggered." Specifically AC-STEP, AC-ZERO, AC-TRIVIAL, AC-REF MUST NOT be flagged.

**Failure mode this fixture guards against**: Drift that causes the LLM to flag any AC mentioning a verb of action (e.g. "creates", "returns", "purges") as AC-STEP. The anti-pattern targets implementation-step phrasing ("Write a function that..."), not observable-action phrasing.
