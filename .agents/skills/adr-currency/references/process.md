# ADR currency process

## Verdicts

- **LIVE-ACCURATE** — current and matches code. Keep; trim pure history.
- **LIVE-DRIFTED** — decision still in force, wording or mechanism diverged. Rewrite in place and bump `date`.
- **ASPIRATIONAL** — unbuilt and not in force. Demote to a bead, then `git rm` the ADR.
- **DEAD-REMOVED** — describes something explicitly removed. `git rm`.
- **SUPERSEDED** — a newer ADR replaces it. `git rm` the old record (or rewrite the topic in place).
- **REDUNDANT** — overlaps another ADR. Merge, then `git rm` the duplicate.

## Trim rules for live ADRs

Strip revision notes, amendment logs, migration diaries, "not yet implemented"
sections, and inline bead-ID status blocks. Keep every live decision and every
valid `prohibits`. Follow `docs/adr/AUTHORING.md` when the repository has one.

## Grounding

Spawn breadth workers on ADR clusters. Each worker cites file paths as evidence
and uses the repository's `CONTEXT.md` / current architecture, not a remembered
product snapshot.

## Verification (when the repo has the scripts)

```bash
uv run --with pyyaml scripts/build-adr-index.py
uv run --with pyyaml --with pytest python -m pytest scripts/test_build_adr_index.py
```

If an ADR injector exists, smoke-test that it returns only accepted ADRs whose
`applies_to` covers the path under change.
