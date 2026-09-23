# BDR Format

BDRs live in `docs/bdr/` as `BDR-NNN-slug.md`.

Create the directory lazily: only when the first BDR is needed.

## Template

```md
---
status: accepted
date: "YYYY-MM-DD"
type: business-decision
record_id: BDR-NNN
decision_summary: "{one sentence}"
---

# BDR-NNN: {Short title}

{1-3 sentences: what we sell or will not sell, for whom, and why that commitment holds until superseded.}
```

Keep the body short unless the trade-off needs the rejected alternative on the record.

## Numbering

Scan `docs/bdr/` for the highest existing `BDR-NNN` and increment by one. Three digits, then a kebab-case slug.

## When to offer a BDR

All three must be true:

1. **Hard to reverse**: this is a product or business commitment, not a reversible implementation choice
2. **Surprising without context**: a future reader, reviewer, or agent would re-open the boundary
3. **A real commercial or product trade-off**: what we sell, what we will not sell, for whom, or where the product stops

Skip the BDR when any test is missing. Use an ADR instead when the commitment is about technical shape, integration, or lock-in.

After writing the BDR, add one index line under `CONTEXT.md` Decisions.
