# Expected Finding: ADR-VIOLATION

**Fixture**: `fixtures/ADR-VIOLATION.json`
**Pattern**: ADR-VIOLATION — Conflicts with an Architecture Decision Record
**Expected severity**: Critical
**Expected finding excerpt**: The bead proposes "Python + uv for the CLI script" for the citation auditor implementation. ADR-0002 Decision 1 mandates Bun + TypeScript as the runtime for all cognovis-core skill scripts, explicitly considering and rejecting Python + uv ("mismatches our skill-script convention"). The proposed approach directly contradicts the accepted ADR decision.
**ADR reference**: `docs/adr/ADR-0002-citation-auditor-architecture.md` — Decision 1 (Runtime: Bun + TypeScript)
**Anti-pattern code in finding**: [ADR-VIOLATION]
**Minimum required in output**: A Critical finding referencing ADR-VIOLATION and ADR-0002 Decision 1, citing bead text such as "Python + uv" or "use Python", noting the conflict with the Bun + TypeScript mandate established in the ADR. Finding must reference the specific ADR file and decision number.
