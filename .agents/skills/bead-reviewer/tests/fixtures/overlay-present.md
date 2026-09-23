# Bead Hygiene Overlay — Test Fixture

This is a mock `.agents/standards/bead-hygiene.md` file for testing Pass 3 overlay loading in bead-reviewer.

## Pflichtfelder

- <!-- severity: critical -->Every bead that touches the Aidbox data layer MUST reference Aidbox-Schema-Impact in metadata.constraints. Beads that omit this field when modifying FHIR resources are non-compliant.
- Every feature bead MUST include a rollback note in description or metadata.constraints describing how the change can be reverted.

## Anti-Patterns

- <!-- severity: critical -->Aidbox-Schema-Impact omitted: A bead modifies an Aidbox resource schema (adds/removes fields, changes cardinality) but does not note the migration impact in constraints.
- <!-- severity: major -->Hardcoded tenant IDs: Bead description or ACs reference a specific tenant ID (e.g. "tenant-abc", "org-123") rather than parameterizing by tenant.
- Missing rollback plan: A bead describing a data migration or schema change includes no rollback or recovery procedure.
