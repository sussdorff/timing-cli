# TDD Real-Fixture Rule

When a bead **parses production output** — HTML/CSV/JSON from external tools,
validator reports, ETL source data, API responses, generated build artifacts —
a TDD suite built on self-written fixtures is **not enough**.

Synthetic fixture drift is a recurring trap: tests green, first production run
red. The implementer builds their idea of the output as a fixture, turns all 15
tests green against it — and the real format is different.

## Concrete Example (fpde-838, 2026-05-12)

Bead: CI release gate for the IG Publisher's qa.html.

| Assumption in fixture | Real format | Consequence |
|-----------------------|-------------|-------------|
| `background-color: #ffe6e6` | `#ffcccc` | Parser matched no error row at all |
| Row has 3 cells (file, message, ctx) | Row has 4 cells with a severity column | Counter cells with `<b>N</b>` counted as errors |
| Allowlist pattern "IG URL should refer" | Real message "The URL should refer" | Allowlist did not match, error treated as internal |

Result: tests 15/15 green, the v0.60.0 release blocked itself, and a hotfix bead was needed.

## Mandatory for Parser/Gate/Adapter/ETL Beads

Beads that parse external production output MUST:

1. **Sample a real fixture** when implementation starts:
   ```bash
   # HTML/JSON from a production URL
   curl -s https://<prod-host>/<artifact> > tests/fixtures/real_<artifact>_<YYYY-MM-DD>.<ext>

   # Local production output (e.g. fsh-generated/, output/, dist/)
   cp <project>/output/<artifact> tests/fixtures/real_<artifact>_<YYYY-MM-DD>.<ext>
   ```

2. **At least one test** named `test_against_real_fixture()`:
   - Asserts against the *known values* of the sampled fixture (for example
     "v0.59.0 qa.html: 7 errors, all external, internal_count=0")
   - Fails immediately when the parser makes wrong assumptions

3. **Fixture source documented** in the test docstring:
   ```python
   def test_against_real_fixture():
       """Tests against real qa.html sampled from
       https://cognovis.github.io/fhir-praxis-de/qa.html on 2026-05-12.
       Source-of-truth at sample time: errors=7, internal=0 (all 7 allowlisted)."""
   ```

4. **Acceptance criterion** added explicitly:
   ```
   - Tests include at least one integration test against a real production
     fixture sampled at implementation time (file documented in test docstring).
   ```

## Detection Triggers

These bead contents point to a parser, gate, or adapter:
- ACs mention: parse, gate, qa.html, output/, .yml workflow, ETL, scrape, validator, adapter
- Bead description mentions: HTML report, JSON API response, CSV import, build artifact
- Tool output is consumed: IG Publisher, SUSHI, npm registry, GitHub API

When in doubt, use a real fixture rather than skipping it.

## Skip Conditions

A real fixture is not needed when:
- Pure refactor without a new parser
- Documentation-only bead
- The bead works exclusively against self-generated output structure (FSH to JSON
  via SUSHI is a grey area — SUSHI is external, but the output format is
  FHIR-specified and therefore stable)
- The implementation uses an established library with a well-documented format
  (for example `lxml` for XML)

## Anti-Patterns

**Guessing:** "I know what qa.html looks like from earlier sessions."

HTML output changes between IG Publisher versions. Memory is not production truth.
The same rule holds for databases: a committed schema inventory or a hand-authored
fixture is not production truth. Database-backed fixtures are generated from the
live source through a declared anonymization boundary; see `workflow/etl-development`.

**Quick synthesis:** "Here is a fixture for roughly how this presents."

Format drift is guaranteed. The tests get trained on wrong assumptions.

**Skipping with "CI will catch it":** "Tests are green, CI is the real test."

Wrong — CI is production. When the bead is reported done and CI then crashes,
a hotfix bead follows. Sampling a fixture is cheaper than a hotfix bead.

## Validation at Bead Close

The verification agent should check:
- Does at least one test function have "real" or "production" in its name?
- Does it reference a fixture from `tests/fixtures/real_*`?
- If the bead trigger matches but there is no real-fixture test, the verdict is DISPUTED.
