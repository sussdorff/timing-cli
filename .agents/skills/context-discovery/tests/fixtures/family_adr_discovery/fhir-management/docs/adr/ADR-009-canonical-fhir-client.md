---
id: ADR-009
status: accepted
applies_to:
  - src/client
decision_summary: "All FHIR access goes through the canonical client."
prohibits:
  - "Do not call Aidbox REST endpoints directly."
---

# ADR-009 — Canonical FHIR client

Governing decision owned by the FHIR family repository. Child repositories
receive it through their declared governing corpus, never as a local copy.
