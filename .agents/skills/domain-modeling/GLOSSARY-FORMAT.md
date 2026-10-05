# GLOSSARY.md Format

## Structure

```md
# {Context Name}

{One or two sentence description of what this context is and why it exists.}

## Language

**Order**:
{A one or two sentence description of the term}
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request
```

## Rules

- **Be opinionated.** When multiple words exist for the same concept, pick the best one and list the others under `_Avoid_`.
- **Keep definitions tight.** One or two sentences max. Define what it IS, not what it does.
- **Only include terms specific to this project's context.** General programming concepts do not belong.
- **Group terms under subheadings** when natural clusters emerge.
- **It is a glossary and nothing else.** Decision records are indexed in `docs/decisions.md`, not here.

## Decision index

`docs/decisions.md` lists every ADR and BDR of the context, one line per record: a link and a one-line gist. It is an index, not a store; do not restate the decision. Upstream skills write ADRs without adding a line here, so reconcile on every touch: list each record in `docs/adr/` and `docs/bdr/` that the index is missing. Links are relative to `docs/decisions.md`.

```md
# Decisions

- [ADR-0001 title](adr/0001-slug.md) — one-line gist
- [BDR-001 title](bdr/BDR-001-slug.md) — one-line gist
```

## Single vs multi-context repos

**Single context (most repos):** One `GLOSSARY.md` at the repo root. `docs/adr/`, `docs/bdr/` and `docs/decisions.md` sit beside it.

**Multiple contexts:** A `GLOSSARY-MAP.md` at the repo root lists the contexts. System-wide ADRs and BDRs stay under `docs/` and are indexed in the root `docs/decisions.md`. Context-specific records live beside that context's `GLOSSARY.md` and are indexed in `<context>/docs/decisions.md`.

Create files lazily: only when you have something to write.
