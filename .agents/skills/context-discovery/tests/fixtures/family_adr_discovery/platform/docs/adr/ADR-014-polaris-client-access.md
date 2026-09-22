---
id: ADR-014
status: accepted
applies_to:
  - src/adapters
decision_summary: "Polaris client access is centralized in the platform client."
prohibits:
  - "Do not bypass the platform client from an adapter."
---

# ADR-014 — Polaris client access

Governing decision owned by the Polaris family repository. Adapters receive it
through their declared governing corpus, never as a local copy.
