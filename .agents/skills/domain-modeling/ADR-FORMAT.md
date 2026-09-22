# ADR Format

ADRs live in `docs/adr/` as `0001-slug.md`, `0002-slug.md`, and so on.

Create the directory lazily: only when the first ADR is needed.

## Template

```md
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

An ADR can be a single paragraph. Record *that* a decision was made and *why*.

## Optional sections

Only include these when they add genuine value:

- **Status** frontmatter (`proposed | accepted | deprecated | superseded`)
- **Considered Options**
- **Consequences**

## Numbering

Scan `docs/adr/` for the highest existing number and increment by one.

## When to offer an ADR

All three must be true:

1. **Hard to reverse**: changing your mind later has a meaningful cost
2. **Surprising without context**: a future reader will wonder why it is this way
3. **A real technical trade-off**: genuine alternatives, picked for specific reasons

Skip the ADR when any test is missing. Use a BDR instead when the commitment is about what we sell or what we will not sell, not how we built it.

After writing the ADR, add one index line under `CONTEXT.md` Decisions.
