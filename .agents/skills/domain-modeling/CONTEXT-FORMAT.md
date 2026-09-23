# CONTEXT.md Format

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

## Decisions

- [ADR-0001 title](docs/adr/0001-slug.md) — one-line gist
- [BDR-001 title](docs/bdr/BDR-001-slug.md) — one-line gist
```

## Rules

- **Be opinionated.** When multiple words exist for the same concept, pick the best one and list the others under `_Avoid_`.
- **Keep definitions tight.** One or two sentences max. Define what it IS, not what it does.
- **Only include terms specific to this project's context.** General programming concepts do not belong.
- **Group terms under subheadings** when natural clusters emerge.
- **Decisions is an index, not a store.** Each ADR or BDR lives in its own file. CONTEXT.md gists and links. Do not restate the decision.

## Single vs multi-context repos

**Single context (most repos):** One `CONTEXT.md` at the repo root. `docs/adr/` and `docs/bdr/` sit beside it.

**Multiple contexts:** A `CONTEXT-MAP.md` at the repo root lists the contexts. System-wide ADRs and BDRs stay under `docs/`; context-specific records may live beside that context's `CONTEXT.md`.

Create files lazily: only when you have something to write.
