# bead-reviewer — Test Fixtures

This directory contains fixture-based tests for the bead-reviewer skill.

## Structure

```
tests/
  fixtures/     JSON bead objects — one per anti-pattern + one ADR violation
  golden/       Expected findings — one markdown file per fixture
  README.md     This file
```

## Fixture Format

Each fixture is a minimal bead JSON object that represents the structure returned by `bd show <id> --json`:

```json
{
  "id": "test-PATTERN-CODE",
  "title": "<title>",
  "description": "<description>",
  "acceptance_criteria": "<ACs>",
  "type": "feature",
  "metadata": {
    "intent": "<non-empty for features>"
  }
}
```

The `acceptance_criteria` field is intentionally omitted in the `AC-ZERO` fixture to trigger that specific anti-pattern.

## Golden File Format

Each golden file documents the minimum expected output when bead-reviewer runs Pass 2 against the corresponding fixture:

- **Fixture**: which JSON file triggers the finding
- **Pattern**: the anti-pattern code and name
- **Expected severity**: Critical (default for all 12 anti-patterns + ADR violations)
- **Expected finding excerpt**: a description of what the finding should contain
- **Anti-pattern code in finding**: the code that must appear in the finding (e.g. `[TITLE-PHASE]`)
- **Minimum required in output**: the minimum content required for the finding to be valid

Golden files describe the *shape* of the expected output, not the exact text. This allows LLM-generated findings to pass validation as long as the key elements are present.

## Fixtures Inventory

### Positive fixtures — each MUST trigger the listed finding

| Fixture | Anti-pattern | Category |
|---|---|---|
| `TITLE-PHASE.json` | TITLE-PHASE — Phase-name without outcome | Title-Shape |
| `TITLE-ACTIVITY.json` | TITLE-ACTIVITY — Activity-named instead of outcome-named | Title-Shape |
| `TITLE-PATH.json` | TITLE-PATH — File/path as title | Title-Shape |
| `TITLE-VAGUE.json` | TITLE-VAGUE — Vague title | Title-Shape |
| `AC-STEP.json` | AC-STEP — AC as implementation step | AC-Shape |
| `AC-ZERO.json` | AC-ZERO — Zero ACs present | AC-Shape |
| `AC-TRIVIAL.json` | AC-TRIVIAL — Trivial, unmeasurable AC | AC-Shape |
| `AC-REF.json` | AC-REF — AC references only other beads | AC-Shape |
| `SCOPE-EPIC.json` | SCOPE-EPIC — Epic-scope in single bead | Scope |
| `SCOPE-DOCS-ONLY.json` | SCOPE-DOCS-ONLY — Pure docs-bead inside feature work | Scope |
| `SCOPE-FORWARD-DEP.json` | SCOPE-FORWARD-DEP — Forward-dependency on unplanned work | Scope |
| `SCOPE-MULTI-CONCERN.json` | SCOPE-MULTI-CONCERN — Multi-concern requiring separate review | Scope |
| `ADR-VIOLATION.json` | ADR-VIOLATION — Conflicts with ADR-0002 Decision 1 | ADR |

### Negative fixtures — each MUST NOT trigger any finding

These guard against over-flagging regressions. If Pass 2 prompt drift causes the reviewer to become too aggressive, these fixtures fail before real beads get blocked unnecessarily.

| Fixture | Boundary case it guards | Category |
|---|---|---|
| `OK-outcome-title.json` | Well-formed feature bead overall | all categories |
| `OK-setup-with-outcome.json` | "Setup X so users can Y" — phase-name + explicit outcome | Title-Shape (TITLE-PHASE boundary) |
| `OK-observable-acs.json` | ACs with action verbs but observable outcomes | AC-Shape boundary |
| `OK-narrow-scope.json` | Multi-AC bead with shared review path and single owner | Scope (SCOPE-MULTI-CONCERN boundary) |
| `OK-adr-aligned.json` | Bead in the ADR-0002 domain that follows all 9 decisions | ADR-VIOLATION boundary |

### Pass 3 fixtures — project overlay loader

| Fixture | What it tests | Golden file |
|---|---|---|
| `overlay-present.md` | Mock bead-hygiene.md overlay (generic) with Pflichtfelder + Anti-Patterns containing Aidbox-Schema-Impact rules | (used as overlay input, not a bead fixture) |
| `overlay-polaris-reduced.md` | Reduced polaris overlay (post clc-dyw.5) — project-specific rules only (Aidbox-Schema-Impact, Adapter-Test-Tier, IG-Capabilities) | (used as overlay input) |
| `overlay-mira-reduced.md` | Reduced mira overlay (post clc-dyw.5) — project-specific rules only (UAT-Szenario, Workspace-Surface, Telemetry, IG-Capabilities) | (used as overlay input) |
| `OVERLAY-AIDBOX-MISSING.json` | Bead that modifies Aidbox Encounter schema but omits Aidbox-Schema-Impact — MUST trigger Critical Pass 3 finding with generic overlay | `OVERLAY-AIDBOX-MISSING.md` |
| `OVERLAY-POLARIS-REDUCED.json` | Polaris feature bead missing Aidbox-Schema-Impact and Adapter-Test-Tier — MUST trigger Critical findings with reduced polaris overlay | `OVERLAY-POLARIS-REDUCED.md` |
| `OVERLAY-MIRA-REDUCED.json` | mira feature bead (Cave widget) missing UAT-Szenario, Workspace-Surface, Telemetry — MUST trigger Critical findings with reduced mira overlay | `OVERLAY-MIRA-REDUCED.md` |
| `OVERLAY-DUAL-SOURCE.json` | Feature bead missing MoC table AND missing Rollback section — MUST trigger Critical findings from BOTH library default (MoC) and project overlay (Rollback); verifies merge, dedup, and origin tagging | `OVERLAY-DUAL-SOURCE.md` |
| (any OK fixture, e.g. `OK-outcome-title.json`) | Both overlay and library default absent — Pass 3 MUST skip silently with no error | `OK-overlay-absent.md` |
| `PASS3-TYPE-EXEMPT-CHORE.json` | Chore bead with `<!-- types: feature -->` rule in overlay — Pass 3 MUST NOT trigger the rule because chore is not in the types filter | `PASS3-TYPE-EXEMPT-CHORE.md` |

## Validation Approach

These fixtures are designed for LLM-in-the-loop validation. To validate:

1. Feed each fixture to bead-reviewer as the bead input (simulating `bd show <id> --json` output).
2. Run bead-reviewer Pass 2 (semantic evaluation + anti-pattern checklist + ADR-gap integration) AND Pass 3 (project overlay, if an overlay file is present — see below).
3. Compare the output against the corresponding golden file.
4. A finding is valid if it contains:
   - The correct anti-pattern code (e.g. `[TITLE-PHASE]`) or overlay rule reference
   - The correct severity (Critical for all fixtures)
   - A citation of the triggering text fragment from the fixture

### Validating Pass 3 fixtures

Pass 3 loads rules from two sources: the library default (`~/.agents/standards/workflow/bead-hygiene.md`)
and the project overlay (`$REPO_ROOT/.agents/standards/bead-hygiene.md`). Either or both may be absent.

- **`OVERLAY-AIDBOX-MISSING.json`**: Copy `fixtures/overlay-present.md` to `$REPO_ROOT/.agents/standards/bead-hygiene.md`. Feed `OVERLAY-AIDBOX-MISSING.json` as the bead input. Pass 3 must report a Critical finding for the missing Aidbox-Schema-Impact constraint. Compare against `golden/OVERLAY-AIDBOX-MISSING.md`.

- **`OVERLAY-POLARIS-REDUCED.json`**: Copy `fixtures/overlay-polaris-reduced.md` to `$REPO_ROOT/.agents/standards/bead-hygiene.md`. Feed `OVERLAY-POLARIS-REDUCED.json` as the bead input. Pass 3 must report Critical findings for missing Aidbox-Schema-Impact and Adapter-Test-Tier sections. Compare against `golden/OVERLAY-POLARIS-REDUCED.md`.

- **`OVERLAY-MIRA-REDUCED.json`**: Copy `fixtures/overlay-mira-reduced.md` to `$REPO_ROOT/.agents/standards/bead-hygiene.md`. Feed `OVERLAY-MIRA-REDUCED.json` as the bead input. Pass 3 must report Critical findings for missing UAT-Szenario, Workspace-Surface, and Telemetry sections. Compare against `golden/OVERLAY-MIRA-REDUCED.md`.

- **Graceful-skip test (using any OK fixture, e.g. `OK-outcome-title.json`)**: Ensure no `bead-hygiene.md` exists at `$REPO_ROOT/.agents/standards/` and no library default at `~/.agents/standards/workflow/bead-hygiene.md`. Run bead-reviewer. Pass 3 must be silently skipped — no error, no "Pass 3" section in the report. Compare against `golden/OK-overlay-absent.md`.

- **Library default auto-load test**: Install the library default at `~/.agents/standards/workflow/bead-hygiene.md` and ensure no project overlay exists. Run bead-reviewer on a bead with no MoC table. Pass 3 must load the library default and report a Critical finding for the missing MoC table (universal rule). The "Overlay Source" line in the report must show "Library default: ~/.agents/standards/workflow/bead-hygiene.md (N rules loaded)" and "Project overlay: not found — skipped".

- **`OVERLAY-DUAL-SOURCE.json`**: Set up `fixtures/overlay-dual-source-project.md` as the project overlay AND the library default (`standards/workflow/bead-hygiene.md` from the repo, or the installed path). Feed `OVERLAY-DUAL-SOURCE.json` as the bead input. The bead lacks both a MoC table (library rule) and a Rollback section (project rule). Pass 3 must report Critical findings from BOTH sources, list both sources with rule counts in the Overlay Source section, and NOT duplicate any rule that appears only in one source. Compare against `golden/OVERLAY-DUAL-SOURCE.md`.

- **`PASS3-TYPE-EXEMPT-CHORE.json`**: Copy `fixtures/overlay-type-exempt.md` to `$REPO_ROOT/.agents/standards/bead-hygiene.md`. Feed `PASS3-TYPE-EXEMPT-CHORE.json` as the bead input. The overlay contains a single rule restricted to `<!-- types: feature -->`. Since the bead type is `chore`, Pass 3 must NOT report any Critical finding for the rule. The report must either show "Project overlay check: CLEAN" or omit the Pass 3 findings section. Compare against `golden/PASS3-TYPE-EXEMPT-CHORE.md`.

## ADR-VIOLATION fixture note

The `ADR-VIOLATION.json` fixture requires the reviewer to have access to `docs/adr/ADR-0002-citation-auditor-architecture.md` in the working repository. The fixture proposes using "Python + uv" for the citation auditor scripts, which directly contradicts ADR-0002 Decision 1 (Bun + TypeScript mandated). The expected finding must reference ADR-0002 Decision 1 by name.
