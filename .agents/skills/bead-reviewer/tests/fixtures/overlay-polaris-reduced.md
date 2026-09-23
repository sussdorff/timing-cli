# Bead Hygiene Overlay — Polaris Project (Reduced)

> **Library defaults:** Universal contract rules are auto-loaded from the cognovis-core library
> default. This file contains only polaris-specific additions.

## Pflichtfelder

- <!-- severity: critical -->Aidbox-Schema-Impact required: every bead that modifies an Aidbox resource schema MUST include a section "## Aidbox-Schema-Impact" with: new/changed resource types or profiles (Nein/Ja: list), whether aidbox-reset.sh is required (Ja/Nein, if Ja: why), and any provisioning changes (CodeSystems, ValueSets, ConceptMaps). If no Aidbox impact: write explicitly "Aidbox-Schema-Impact: keiner — nur Adapter-Logik".
- <!-- severity: critical -->Adapter-Test-Tier required: every bead MUST include a section "## Adapter-Test-Tier" with a statement per tier: unit (pure mapper/logic tests with mock data), integ (Live-MSSQL queries against test DBs with INTEGRATION_TESTS=true; explicit ja/nein), smoke (full sync-loop dryRun; only for architecture changes). State which tier is mandatory for the review pass of this bead.
- <!-- severity: major -->IG-Capabilities required: every bead referencing FHIR profiles or CodeSystems MUST include a section "## IG-Capabilities" listing what the IG must provide (profile names, CodeSystems, Extensions) — not which version.

## Anti-Patterns

- <!-- severity: critical -->"aidbox-reset.sh wird's schon richten" without explicit documentation in Aidbox-Schema-Impact — the schema impact section forces clarification before implementation.
- <!-- severity: critical -->Adapter-Test-Tier omitted — reviewer must know whether Live-MSSQL is required for the review pass.
