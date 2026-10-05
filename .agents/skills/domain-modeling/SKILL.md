---
name: domain-modeling
description: Library domain-modeling - writes BDRs and ADRs, keeps their docs/decisions.md decision index, migrates a legacy CONTEXT.md to GLOSSARY.md, and edits GLOSSARY.md terms. Prefer it over upstream domain-modeling in Library repositories. Use when a domain term, a GLOSSARY.md entry, an ADR or a BDR is decided or edited.
requires_standards: [writing/plain-technical-english]
compatibility: {}
metadata: {}
---

# Domain Modeling

Actively build and sharpen the project's domain model as you design. Challenge terms,
invent edge-case scenarios, and write the glossary and decision records the moment
they crystallise. Merely reading `GLOSSARY.md` for vocabulary is not this skill; this
skill changes the domain model.

## Inputs

- The current conversation, code, and any existing `GLOSSARY.md` / `GLOSSARY-MAP.md`.
- Existing `docs/adr/`, `docs/bdr/` and `docs/decisions.md` when they exist.

## Outputs

- An updated `GLOSSARY.md`, created lazily. It is a glossary and nothing else.
- An ADR in `docs/adr/` or a BDR in `docs/bdr/` only when the offer tests pass.
- One line per record in the `docs/decisions.md` decision index.

## Workflow

1. Before writing, migrate a legacy glossary on touch, all in one change. Paths are relative to the context root.
   - With `CONTEXT.md` and no `GLOSSARY.md`, run `git mv CONTEXT.md GLOSSARY.md`. With both, merge the `CONTEXT.md` terms into `GLOSSARY.md`, ask the user about conflicting definitions, then `git rm CONTEXT.md`.
   - Move the old `## Decisions` lines into that context's `docs/decisions.md` and rewrite each link relative to `docs/decisions.md`: `docs/adr/x.md` becomes `adr/x.md`, `docs/bdr/x.md` becomes `bdr/x.md`. Merge into an existing `docs/decisions.md`; never overwrite it.
   - With `CONTEXT-MAP.md`, run `git mv CONTEXT-MAP.md GLOSSARY-MAP.md` and migrate every context it lists in the same change, so the map never mixes old and new names.
   - Update references to the renamed files in `AGENTS.md`, `CLAUDE.md`, `docs/agents/domain.md` and the per-context links of `GLOSSARY-MAP.md`.
2. Challenge terms against `GLOSSARY.md`. Call out conflicts immediately.
3. Sharpen fuzzy or overloaded language into a canonical term.
4. Stress-test relationships with concrete scenarios, including edge cases.
5. Check the code when the user states how something works. Surface contradictions.
6. Update `GLOSSARY.md` inline when a term is resolved. Use [GLOSSARY-FORMAT.md](GLOSSARY-FORMAT.md). Create the file lazily. It holds terms only: no decision index, no spec, no implementation detail.
7. Offer a decision record only when the three tests in [ADR-FORMAT.md](ADR-FORMAT.md) or [BDR-FORMAT.md](BDR-FORMAT.md) all hold. Business and product commitments go to BDRs. Technical shape goes to ADRs. After writing either record, add one index line to `docs/decisions.md`. Whenever you touch decisions, also add index lines for records in `docs/adr/` and `docs/bdr/` that the index does not list yet; upstream `domain-modeling` writes ADRs without indexing them.

## Do Not

- Batch glossary updates until the end of the session.
- Dump implementation notes or decision links into `GLOSSARY.md`.
- Create an ADR or BDR when any offer test is missing.
- Use GitHub Issues, `UBIQUITOUS_LANGUAGE.md`, or a User-Scope copy of this skill.

## Resources

| File | Purpose |
|------|---------|
| `GLOSSARY-FORMAT.md` | Glossary shape and the `docs/decisions.md` index shape |
| `ADR-FORMAT.md` | Technical decision records in `docs/adr/` |
| `BDR-FORMAT.md` | Business and product decision records in `docs/bdr/` |
