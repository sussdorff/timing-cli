# Bead Hygiene Overlay — mira (Reduced)

> **Library defaults:** Universal contract rules are auto-loaded from the cognovis-core library
> default. This file contains only mira-specific additions.

## Pflichtfelder

- <!-- severity: critical -->UAT-Szenario required: every bead of type feature/task/bug MUST include a section "## UAT-Szenario" with at least one end-to-end path (numbered steps: login, navigate, action, expected result). Backend-only features MUST include a "Tester calls X via API/CLI, expects Y in DB" scenario. Links to Matrix-Fixture or test-data beads where applicable.
- <!-- severity: critical -->Workspace-Surface required: every bead MUST include a section "## Workspace-Surface" listing all UI and API touchpoints (UI files new/changed, API endpoints new/changed, tables accessed, Aidbox resources). If no UI is touched: write explicitly "Workspace-Surface: backend-only — keine UI-Änderung".
- <!-- severity: critical -->Telemetry required: every bead MUST include a section "## Telemetry" listing all new/changed OTel spans (with attributes), metrics (with labels), and log entries. If no telemetry is needed: write explicitly "Telemetry: keine — <reason>". Even a single OTel span per new endpoint is mandatory.
- <!-- severity: major -->IG-Capabilities required: every bead referencing FHIR profiles or Aidbox resources MUST include a section "## IG-Capabilities" listing what the IG/Aidbox must provide (profile names, CodeSystems, Extensions) — not which version.

## Anti-Patterns

- <!-- severity: critical -->UAT-Szenario omitted because "Backend-Feature" — backend features still require a UAT scenario via API/CLI. Missing UAT-Szenario = review reject.
- <!-- severity: critical -->Telemetry omitted because "klein" — even a single OTel span per new endpoint is mandatory. Write "Telemetry: keine" explicitly when genuinely not needed.
- <!-- severity: critical -->Workspace-Surface not listed — reviewer must know which UI files are affected. Missing section = review reject.
