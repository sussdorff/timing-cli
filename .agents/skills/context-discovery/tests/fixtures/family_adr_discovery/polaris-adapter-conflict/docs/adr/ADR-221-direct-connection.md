---
id: ADR-221
status: accepted
decides: polaris-client-access
applies_to:
  - src/adapters
decision_summary: "This adapter opens its own direct Polaris connection."
prohibits:
  - "Do not route this adapter through the platform client."
---

# ADR-221 — Direct connection

Local decision for the same `polaris-client-access` topic, contradicting the
governing decision.
