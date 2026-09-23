---
name: domain-modeling
description: Define codebase terminology or author CONTEXT.md, ADRs and BDRs. Use codebase-design for module interfaces.
requires_standards: [writing/plain-technical-english]
compatibility: {}
metadata: {}
---

# Domain Modeling

Actively sharpen the project's domain model. Challenge terms, invent edge-case
scenarios, and write the glossary and decision records the moment they crystallise.

## Inputs

- The current conversation, code, and any existing `CONTEXT.md` / `CONTEXT-MAP.md`.
- Existing `docs/adr/` and `docs/bdr/` when those directories exist.

## Outputs

- An updated `CONTEXT.md` glossary, created lazily.
- An ADR in `docs/adr/` or a BDR in `docs/bdr/` only when the offer tests pass.
- `CONTEXT.md` decision-index links to those records.

## Workflow

1. Challenge terms against `CONTEXT.md`. Call out conflicts immediately.
2. Sharpen fuzzy or overloaded language into a canonical term.
3. Stress-test relationships with concrete scenarios, including edge cases.
4. Check the code when the user states how something works. Surface contradictions.
5. Update `CONTEXT.md` inline when a term is resolved. Use [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md). Create the file lazily. `CONTEXT.md` is a glossary plus an index of ADRs and BDRs. It is not a spec and holds no implementation detail.
6. Offer a decision record only when the three tests in [ADR-FORMAT.md](ADR-FORMAT.md) or [BDR-FORMAT.md](BDR-FORMAT.md) all hold. Business and product commitments go to BDRs. Technical shape goes to ADRs. After writing either record, add one index line under `CONTEXT.md` Decisions.

## Do Not

- Batch glossary updates until the end of the session.
- Dump implementation notes into `CONTEXT.md`.
- Create an ADR or BDR when any offer test is missing.
- Use GitHub Issues, `UBIQUITOUS_LANGUAGE.md`, or a User-Scope copy of this skill.

## Resources

| File | Purpose |
|------|---------|
| `CONTEXT-FORMAT.md` | Glossary and decision-index shape |
| `ADR-FORMAT.md` | Technical decision records in `docs/adr/` |
| `BDR-FORMAT.md` | Business and product decision records in `docs/bdr/` |
