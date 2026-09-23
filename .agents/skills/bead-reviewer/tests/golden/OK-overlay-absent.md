# Expected Finding: OK-overlay-absent

**Fixture**: `fixtures/OK-outcome-title.json` (any well-formed fixture)
**Overlay**: absent (no `.agents/standards/bead-hygiene.md` present in repo)
**Pattern**: (none — graceful-skip test)
**Expected severity**: n/a

This golden file documents the expected behavior when Pass 3 finds no overlay file.

**Expected outcome**: Pass 3 silently skips without error. The output report does NOT include a "Pass 3: Project Overlay Findings" section (or includes it with a note that no overlay was found). The Pass 1 and Pass 2 verdicts are unaffected.

**Minimum required in output**:
- No error message about a missing `.agents/standards/bead-hygiene.md`.
- No empty "Pass 3" section with broken content.
- If a Pass 3 section appears, it must say something like "No project overlay found — skipping." or be omitted entirely.
- The overall verdict matches what Pass 1 + Pass 2 would produce without Pass 3.

**Failure mode this fixture guards against**: Pass 3 raises an error or crashes when `.agents/standards/bead-hygiene.md` is absent, blocking review of beads in repos that have not adopted the overlay convention.
