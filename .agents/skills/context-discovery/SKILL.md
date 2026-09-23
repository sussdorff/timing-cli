---
name: context-discovery
description: Retrieve bounded repository and ADR context for read-only review or planning without Bead admission.
tags: [beads, adr, context-provider]
requires_standards:
  - beads/context-pointers
  - adr-location
---

# context-discovery

An on-demand, read-only route to the same bounded repository/ADR context
engine the repository delivery entry (`executive-pack`) uses for gate admission
(`skills/context-discovery/scripts/context_provider.py`). This skill does not
implement discovery itself; it calls the provider's existing functions
unchanged so a second implementation can never drift from loop admission.

This skill never writes loop state and never opens or claims a Bead. It is
purely read-only: no file is created, no `bd` mutation is issued beyond a
read-only `bd show`. When the registry entry declares a tracker, use `ccore tracker`
instead of `bd`; with no tracker field, keep `bd` for the Beads archive.

## When to Use

- A reviewer or planner needs to know which ADRs govern a set of paths before
  a Bead exists for the work.
- Someone wants to inspect exactly the context bundle the implementation loop
  would build for a live Bead, without running the loop.
- A session needs bounded ADR guidance for ad-hoc exploration instead of an
  unbounded scan of `docs/adr`.

Do NOT use this skill to:

- Feed a delivery session's own context step -- it resolves and calls the
  provider itself; do not route its context through this skill.
- Change ADR selector matching, ranking, or the manifest bound -- those are
  owned by the provider and `adr-context.py`, out of scope here.
- Claim, update, or close a Bead -- this skill only reads.

## Two Modes

### Path-scoped (no live Bead)

Given an explicit set of candidate or changed paths, return the bounded ADR
manifest and candidate surface as deterministic JSON. Uses a synthetic
empty-text bead internally (`build_adr_context` only needs Bead text for
`bead:ADR-xxx` matching and freshness digesting, both irrelevant with no live
Bead). Path-based ADR matching still applies in full.

```bash
uv run python skills/context-discovery/scripts/context_discovery.py \
  path-scoped --repo-root . --candidate-path src/service.py --candidate-path tests/test_service.py
```

Or via stdin (candidate paths and repo root as one JSON object):

```bash
echo '{"candidate_paths": ["src/service.py"], "repo_root": "."}' | \
  uv run python skills/context-discovery/scripts/context_discovery.py path-scoped --request-stdin
```

Output:

```json
{
  "mode": "path-scoped",
  "repo_root": "/abs/path/to/repo",
  "candidate_surface": ["src/service.py"],
  "adr_context": {
    "schema_version": 1,
    "status": "complete",
    "candidate_surface_count": 1,
    "manifest": [{"id": "ADR-057", "path": "docs/adr/ADR-057-binding.md", "origin": "local", "corpus": "local", "precedence": "local", "match_reasons": ["path:src/service.py"], "decision_summary": "...", "prohibitions": ["..."], "read_pointers": [...]}],
    "gaps": [],
    "freshness": {"...": "..."}
  }
}
```

When the repository has no `docs/adr` directory, `adr_context.status` is
`"gap"` and `adr_context.gaps` carries a resolved `ADR_CORPUS_NOT_FOUND` entry
-- never an exception.

### Governing family corpora

A child repository sees the decisions that govern it as well as its own. It
declares the governing corpora in `.adr-governance.json` at its root; the
format is owned by the `adr-location` standard. Each declared corpus is
discovered through the same selector, matched against the child's candidate
surface, and every manifest entry then carries its provenance:

| field | local corpus | declared corpus |
| --- | --- | --- |
| `origin` | `local` | `family` |
| `corpus` | `local` | the declared corpus identity |
| `precedence` | `local` | `governing` |

`path` stays relative to its own corpus for both origins, so no machine path
reaches a manifest. Repositories without a declaration keep local-only
discovery unchanged.

A `workspace_path` resolves after symlinks and must identify a direct sibling
of the declaring repository beneath that repository's resolved parent. The
supported `../fhir-management` shape remains valid. Traversal beyond that
family root, a declaration of the repository itself, and a sibling symlink
that resolves outside the family are invalid declarations.

Two conditions of a declared family are reported as unresolved typed gaps
rather than silently absorbed, both leaving `status` at `"gap"`:

- `ADR_GOVERNING_CORPUS_MISSING` -- a declared `workspace_path` has no
  `docs/adr`. It names the `corpus` and `workspace_path` to repair, and is
  distinct from `ADR_CORPUS_NOT_FOUND`, which is the *accepted* absence of a
  repository's own local corpus.
- `ADR_DECISION_CONFLICT` -- two or more applicable ADRs with
  `status: accepted` declare the same frontmatter `decides` topic in different
  corpora. The gap names the `topic` and every conflicting side
  (`origin`, `corpus`, `id`). Both sides stay in the manifest with their own
  precedence: discovery picks no winner. A record that is not accepted claims
  no decision and is not a conflicting side.
- `ADR_GOVERNING_DECLARATION_INVALID` -- a malformed declaration, including a
  `workspace_path` that does not resolve to a direct family sibling, is
  rejected before corpus discovery. Its `reason`, `corpus`, and
  `workspace_path` identify the declaration to repair without recording a
  machine path.
- `ADR_GOVERNING_CORPUS_OUTSIDE_ROOT` -- a direct sibling's `docs/adr`
  directory or any candidate ADR Markdown file resolves outside its declared
  corpus root, for example through a symlink. The corpus is excluded and the
  gap names the declaration to repair.
- `ADR_CORPUS_OUTSIDE_ROOT` -- the local `docs/adr` directory or a candidate
  Markdown file resolves outside the repository root. The local corpus is
  excluded without exposing the external path or content.

### Bead-scoped (exact loop bundle)

Given a Bead ID, shell non-interactive `bd show <id> --json` (with `cwd` bound
to `--repo-root`) and return the same context bundle a delivery session would
build and consume -- byte-for-byte the result of `build_context_bundle` called
with the fixed arguments this repository binds for bead context:
`provider="fallback"`, `cbm_command="codebase-memory-mcp"`, `allow_index=False`.
Writes nothing: no state file, no bead claim or mutation.

```bash
uv run python skills/context-discovery/scripts/context_discovery.py \
  bead-scoped clc-b9wq --repo-root .
```

`--bead-json <path>` accepts pre-fetched `bd show --json` output instead of
shelling `bd`, for testing or when a bead dict is already in hand.

## Manual CLI Alternative

`adr-context.py discover --request-stdin` is an existing, already-working CLI
route on the same ADR selector, documented here rather than replaced:

```bash
echo '{"changed_paths": ["src/service.py"], "bead_description": ""}' | \
  uv run --script skills/context-discovery/scripts/adr-context.py discover \
  --adr-dir docs/adr --request-stdin --output json
```

It returns an execution-result envelope (`data.adrs_in_scope`) rather than the
provider's bounded-manifest shape, and does not compute candidate surface or
freshness digests. Use `context-discovery` when you want the same shape the
implementation loop consumes; use `adr-context.py` directly for a raw ADR
selector query.

## Script Resolution

`context_discovery.py` resolves `context_provider.py` project-local first,
then global, using the canonical probe order: repo `.agents/skills/...`, repo
`.claude/skills/...`, repo `skills/...`, this marketplace's `skills/...`, user
`.agents/skills/...`, user `.claude/skills/...`. It fails loudly with every
probed path if none resolve -- never an unbounded filesystem scan.

## Frontmatter contract

Bounded admission consumes ADR (and, when present, BDR) YAML frontmatter.
The canonical field contract — including ADR package/path `applies_to` versus
BDR conceptual scopes, manifest fields, and cross-record `related` /
`supersedes` — lives in the `adr-gap` skill:

`skills/adr-gap/references/adr-frontmatter.md`

Validate a repository corpus with the documented Marketplace doctor, passing
that repository's root (never a hard-coded foreign corpus path):

```bash
uv run skills/adr-gap/scripts/adr-gap.py doctor <repo_root> [--ci] [--fix]
```

This skill does not repair frontmatter; `adr-gap` `doctor --fix` may insert
only derivable metadata and must not change `applies_to` or record bodies.

## Out of Scope

- ADR selector semantics (`_matches_glob`, `discover_adrs`) and the manifest
  bound (`ADR_MANIFEST_LIMIT`) -- owned by `context_provider.py` /
  `adr-context.py`.
- Bead claim, delivery admission, and any part of the single-bead lifecycle --
  owned by `executive-pack` in `solo` mode over `implementation-loop`.
- Introducing a subagent, a cache, or new ADR ranking/scoring.
