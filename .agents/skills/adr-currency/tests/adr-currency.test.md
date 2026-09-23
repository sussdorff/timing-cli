# Test Fixture: adr-currency

## Test 1 — Happy path

**Input:** "Are the ADRs current? Re-baseline the corpus."
**Expected behavior:** Inventory `docs/adr/`, ground against code, present a cut-list, and stop for approval before any `git rm` or rewrite.
**Pass criteria:** No ADR file is deleted or rewritten before the table is approved.

## Test 2 — Adjacent skill

**Input:** "Write an ADR for this new store identity decision."
**Expected behavior:** Do not run the currency audit. Hand off to domain-modeling.
**Pass criteria:** No corpus-wide triage table is produced.
