# Expected Finding: OVERLAY-MIRA-REDUCED

**Fixture**: `fixtures/OVERLAY-MIRA-REDUCED.json`
**Overlay fixture**: `fixtures/overlay-mira-reduced.md` (used as `.agents/standards/bead-hygiene.md`)
**Library default**: `fixtures/` directory does not include a library default; test verifies project overlay rules only. For combined testing, also load `standards/workflow/bead-hygiene.md` as the library default.
**Pattern**: mira project overlay — UAT-Szenario missing; Workspace-Surface missing; Telemetry missing
**Expected severity**: Critical (all three rules)

**Expected findings**:

The bead description is a feature bead (Cave widget) with MoC, API description, and ACs — but it contains no `## UAT-Szenario` section, no `## Workspace-Surface` section, and no `## Telemetry` section. All three are Critical Pflichtfelder in the mira overlay.

**Minimum required in output**:

- At least one Critical finding in the "Pass 3: Project Overlay Findings" section.
- Findings reference at least two of the three missing sections: UAT-Szenario, Workspace-Surface, Telemetry.
- Each finding cites the bead's feature content (e.g. "Cave widget", "POST /api/practitioner/cave") as evidence that the sections should be present.
- The overall verdict is NEEDS INTERACTIVE WORK (Critical Pass 3 findings override Pass 1 result).

**What this guards against**: After mira reduced its overlay to project-specific delta in clc-dyw.5, Pass 3 must still enforce the remaining mira-specific rules (UAT-Szenario, Workspace-Surface, Telemetry) — confirming the reduced file produces project-specific findings.
