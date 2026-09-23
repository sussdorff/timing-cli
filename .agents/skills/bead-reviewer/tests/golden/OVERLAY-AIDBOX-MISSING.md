# Expected Finding: OVERLAY-AIDBOX-MISSING

**Fixture**: `fixtures/OVERLAY-AIDBOX-MISSING.json`
**Overlay fixture**: `fixtures/overlay-present.md` (used as a stand-in for `.agents/standards/bead-hygiene.md`)
**Pattern**: Project overlay rule — Aidbox-Schema-Impact omitted from metadata.constraints
**Expected severity**: Critical
**Expected finding excerpt**: The bead modifies an Aidbox resource schema (adds CareTeam reference to Encounter, includes FHIR profile update and migration) but the `metadata.constraints` field does not mention Aidbox-Schema-Impact.
**Minimum required in output**:

- A Critical finding in the "Pass 3: Project Overlay Findings" section.
- The finding references the rule "Aidbox-Schema-Impact" (from the `## Pflichtfelder` or `## Anti-Patterns` section of the overlay).
- The finding cites a text fragment from the bead confirming the Aidbox schema change is present (e.g. "Aidbox Encounter resource", "FHIR profile", "migrate").
- The overall verdict is NEEDS INTERACTIVE WORK (Critical Pass 3 finding overrides Pass 1 result).

**Failure mode this fixture guards against**: Pass 3 silently drops project overlay rules and allows beads that violate project-specific constraints to pass undetected.
