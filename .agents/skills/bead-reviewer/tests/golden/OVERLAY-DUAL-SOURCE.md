# Expected Finding: OVERLAY-DUAL-SOURCE

**Fixture**: `fixtures/OVERLAY-DUAL-SOURCE.json`
**Library default**: `standards/workflow/bead-hygiene.md` (loaded from in-repo path, or `~/.agents/standards/workflow/bead-hygiene.md` if installed)
**Project overlay**: `fixtures/overlay-dual-source-project.md` (used as `.agents/standards/bead-hygiene.md`)
**Pattern**: Dual-source merge — library rule fires AND project rule fires; no duplicate findings for rules unique to each source

**Bead setup**:
- The bead is a feature with Out of Scope listed but NO MoC table in the description.
- The bead has no `## Rollback` section (violates project overlay rule).
- Library default contributes: MoC Table required (Pflichtfelder Critical), "Tests folgen später" (Anti-Patterns Critical), "IG-Version pinnen" (Anti-Patterns Critical).
- Project overlay contributes: Rollback plan required (Pflichtfelder Critical), Hardcoded environment references (Anti-Patterns Major).

**Expected findings**:

1. **Library rule fires** — Critical finding for missing MoC table. The bead has no pipe-table MoC section. Source tagged as `library`.
2. **Project rule fires** — Critical finding for missing `## Rollback` section. Source tagged as `project`.
3. **No duplicate findings** — "Tests folgen später" and "IG-Version pinnen" from the library default each appear at most once. The project overlay does not restate them, so no dedup conflict.
4. **Origin tagging** — The "Overlay Source" section in the report lists both sources with rule counts:
   - Library default: `~/.agents/standards/workflow/bead-hygiene.md` OR `standards/workflow/bead-hygiene.md` (N rules loaded)
   - Project overlay: `.agents/standards/bead-hygiene.md` (M rules loaded)

**Minimum required in output**:

- The "Pass 3: Project Overlay Findings" section is present (at least one source was loaded).
- At least two distinct Critical findings: one referencing the MoC table rule (library), one referencing the Rollback plan rule (project).
- The "Overlay Source" section shows TWO sources (library + project), each with a rule count > 0.
- The overall verdict is NEEDS INTERACTIVE WORK (Critical findings from both sources).
- No finding appears twice for the same rule (dedup holds for rules that only exist in one source).

**What this guards against**:
- Source A (library) loading silently skipped, leaving only project rules enforced.
- Source B (project) loading silently skipped, leaving only library rules enforced.
- Rule deduplication firing incorrectly when rules appear in only one source.
- Origin tagging absent from the report (reviewer cannot tell which source triggered a finding).
