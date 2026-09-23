# Context Pointers — Canonical Schema

`## Context Pointers` is an optional section in a bead description that gives the implementing
agent an explicit, deterministic list of files, symbols, and memory hints to seed Phase 1
(context gathering). When present, the bead-orchestrator passes the pointer list into the
context provider. The provider may expand it with code graph results, but it must preserve
the sanitized pointer paths in the returned context bundle.

## Canonical Schema

The block is written directly under the `## Context Pointers` heading in YAML-ish indented list
syntax. Both `- foo` (dash-prefixed) and bare `foo` (no dash) are accepted per item.

```markdown
## Context Pointers
primary_files:
  - meta/library_cli.py
  - meta/catalog.py
test_files:
  - tests/test_catalog.py
symbols:
  - get_entries
  - default_scope
memory_search: "library catalog default_scope"
```

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `primary_files` | list of paths | no | Source files the context provider must include and the agent must inspect. Paths are relative to the repo root. |
| `test_files` | list of paths | no | Test files the context provider must include. Paths are relative to the repo root. |
| `symbols` | list of strings | no | Function names, class names, or identifiers the context provider should resolve. Free-form; not validated. |
| `memory_search` | string | no | Search query the agent should run against open-brain memory before starting implementation. Free-form; not validated. |

## Validation Rules

- **Absolute paths rejected**: Any path in `primary_files` or `test_files` that is absolute
  (starts with `/`) is rejected immediately. No existence check is performed on it. This
  generates a `warning`-level finding and the path is **excluded from the sanitized pointer
  output** — it will not be passed to the implementing agent.

- **Traversal escape rejected**: Relative paths that resolve outside the repo root via `..`
  sequences (e.g. `../sibling-repo/file.py`) are rejected after canonical resolution. They
  generate a `CONTEXT_POINTER_PATH_ESCAPE` warning and are **excluded from the sanitized
  pointer output**.

- **Path existence check**: Paths that are within the repo root but do not yet exist on disk
  generate a `CONTEXT_POINTER_PATH_NOT_FOUND` warning (non-blocking). The path **is still
  included** in the sanitized pointer output — it may refer to a file that will be created
  during implementation.

- **Sanitized output**: The `pointers` field returned by the validator contains only paths
  that passed both the containment check and the absolute-path check. Downstream consumers
  (orchestrator Phase 1, quick-fix `files_from_bead`, context provider seed input) receive
  only this sanitized list.

- **Missing block (factory-ready)**: If `## Context Pointers` is absent and the bead is
  factory-ready (label `factory:ready` or `metadata.factory_ready: true`), a `blocking`
  finding is generated.

- **Missing block (non-factory)**: If `## Context Pointers` is absent and the bead is not
  factory-ready, an `advisory` finding is generated (non-blocking).

- `symbols` and `memory_search` are free-form; no validation is performed.

## Parser Behavior

The block ends at the next `##` heading or end of document. The parser is lenient:
- Accepts both `- item` and `item` (bare) syntax within list sections.
- Ignores non-indented prose inside the block; only indented entries or dash-prefixed entries are
  treated as list items.
- Ignores blank lines.
- `memory_search` value may optionally be quoted with double quotes; quotes are stripped.

## Example — Full Block

```markdown
## Context Pointers
primary_files:
  - meta/library_cli.py
  - meta/catalog.py
test_files:
  - tests/test_catalog.py
symbols:
  - get_entries
  - default_scope
memory_search: "library catalog default_scope"
```

## Example — Minimal Block

```markdown
## Context Pointers
primary_files:
  - src/auth.py
```
