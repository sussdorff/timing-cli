# Expected Finding: OVERLAY-POLARIS-REDUCED

**Fixture**: `fixtures/OVERLAY-POLARIS-REDUCED.json`
**Overlay fixture**: `fixtures/overlay-polaris-reduced.md` (used as `.agents/standards/bead-hygiene.md`)
**Library default**: `fixtures/` directory does not include a library default; test verifies project overlay rules only. For combined testing, also load `standards/workflow/bead-hygiene.md` as the library default.
**Pattern**: polaris project overlay — Aidbox-Schema-Impact section missing; Adapter-Test-Tier section missing
**Expected severity**: Critical (both rules)

**Expected findings**:

The bead description modifies an Aidbox Encounter resource (adds billing context field, updates FHIR profile) but contains no `## Aidbox-Schema-Impact` section and no `## Adapter-Test-Tier` section. Both are Critical Pflichtfelder in the polaris overlay.

**Minimum required in output**:

- At least one Critical finding in the "Pass 3: Project Overlay Findings" section.
- One finding references the "Aidbox-Schema-Impact" rule and cites a text fragment confirming the Aidbox schema change is present (e.g. "Aidbox Encounter resource", "FHIR profile", "billing context field").
- One finding references the "Adapter-Test-Tier" rule as missing.
- The overall verdict is NEEDS INTERACTIVE WORK (Critical Pass 3 finding overrides Pass 1 result).

**What this guards against**: After polaris reduced its overlay to project-specific delta in clc-dyw.5, Pass 3 must still enforce the remaining polaris-specific rules (Aidbox-Schema-Impact, Adapter-Test-Tier) — confirming the reduced file produces project-specific findings.
