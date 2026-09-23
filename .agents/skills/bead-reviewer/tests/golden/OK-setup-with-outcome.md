# Expected Finding: OK-setup-with-outcome

**Fixture**: `fixtures/OK-setup-with-outcome.json`
**Pattern**: (none — negative fixture)
**Expected severity**: n/a
**Expected outcome**: NO Pass 2 Critical or HIGH finding.

This fixture exists to prevent over-flagging regressions in Pass 2. It is the boundary case for TITLE-PHASE: the title starts with "Setup" (a phase-name verb) but is qualified by an explicit outcome ("so users can register"). The SKILL.md anti-pattern definition explicitly calls this case OK.

The rest of the bead is also clean:
- ACs are observable (connection works, migration applies cleanly).
- Single concern (database substrate for registration).
- No ADR conflict.

**Minimum required in output**: Pass 2 reports "Anti-pattern check: CLEAN — no patterns triggered." TITLE-PHASE MUST NOT be flagged.

**Failure mode this fixture guards against**: Drift that causes the LLM to match TITLE-PHASE on any title starting with "Setup" / "Refactor" / "Migration" without checking whether an outcome qualifier follows.
