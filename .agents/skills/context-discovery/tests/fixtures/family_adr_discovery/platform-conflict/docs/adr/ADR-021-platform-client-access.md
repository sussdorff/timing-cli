---
id: ADR-021
status: accepted
decides: polaris-client-access
applies_to:
  - src/adapters
decision_summary: "Adapters reach Polaris only through the platform client."
prohibits:
  - "Do not open a direct Polaris connection from an adapter."
---

# ADR-021 — Platform client access

Governing decision for the `polaris-client-access` topic.
