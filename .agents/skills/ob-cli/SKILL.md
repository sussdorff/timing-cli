---
name: ob-cli
description: Search or save open-brain memories with ob in coding sessions; use MCP for mobile and administrative operations.
argument-hint: "[subcommand] [args]"
---

# ob CLI — open-brain in Coding Harnesses

## Routing Rule (Static)

| Context | Tool |
|---|---|
| **Coding harness** (Claude Code CLI, Codex CLI) | `ob` CLI — direct connection, no MCP round-trip |
| **Mobile** (claude.ai, iOS) | `mcp__open-brain__*` tools |
| **Admin / bulk operations** (ingest, migrate, lifecycle) | MCP or HTTP API |

The rule is static: if you are running inside a coding harness (terminal-launched Claude or Codex),
always prefer `ob` over MCP. MCP is only required when no CLI is available.

## Installation

`ob` is available at `~/.local/bin/ob`. No `uv run` needed.

Verify: `ob doctor`

## Subcommands

| Subcommand | Purpose | Example |
|---|---|---|
| `ob search <query>` | Hybrid search (vector + FTS) across memories | `ob search "ADR database migration" --limit=5` |
| `ob concept <query>` | Semantic-only (vector) search | `ob concept "authentication patterns"` |
| `ob save <text>` | Save a new observation/memory | `ob save "Decided to use JWT" --type=decision --project=mira` |
| `ob get <id> [<id> ...]` | Fetch full observations by ID | `ob get 27733` |
| `ob context` | Recent session context for current project | `ob context --project=library --limit=10` |
| `ob timeline` | Timeline view of memories | `ob timeline --project=mira` |
| `ob stats` | Database statistics | `ob stats` |
| `ob doctor` | Run server diagnostics | `ob doctor` |
| `ob update <id>` | Update an existing memory | `ob update 27733 --title="New title"` |
| `ob ingest` | Ingest from external sources | `ob ingest --help` |
| `ob people <sub>` | Manage people memories | `ob people list` |

## `--json` Is a Global Option

`--json` belongs before the subcommand: `ob --json search "query"`. Placed after
the subcommand it is an unrecognized argument and `ob` exits 2.

```bash
ob --json search "library sync" --limit=5    # machine-readable
ob --json get 27733                          # full record for one ID
```

## Bounded Recall

`ob --json search` returns whole records, so an unfiltered search floods the
context with long memories and inline image payloads. Bounded excerpts shipped in
a later open-brain release, so a hit carries either a server-side `excerpt` or
only the full `content` depending on the version answering this host. Project
`.excerpt // .content` and the same command stays bounded on both. Sanitize
before you cap, so an image or data URI cannot survive as a truncated blob:

```bash
# bounded-projection: ob-search
ob --json search "library sync" --limit=5 | jq -c '[.results[]
  | {id, title, excerpt: ((.excerpt // .content // "")
      | gsub("!\\[\\[[^]]*\\]\\]"; "[image]")
      | gsub("data:[^\\s\")]+"; "[inline-data]")
      | .[0:300])}]'
```

Read the excerpts, decide which IDs matter, then fetch only those in full with
`ob --json get <id>`. Never loop a full `get` over an arbitrary result set. There
is no excerpt flag to pass; `ob get --inspect` fetches without logging the
retrieval or changing recall priority. `ob --version` reports the CLI and
`ob --json doctor` reports the store's `server_version` — they are different
things, so record whichever one your claim is about, or just note whether the
response carried `excerpt`.

## Continuing Earlier Work

Before recommending an access change, a deployment or the next step of work
someone already started, recover what that work established: search for the prior
session summary, read bounded excerpts, fetch in full only the few records that
matter, and separate decisions and completed actions from what is still open.

A memory records what was true when it was written. Re-check the live state
before acting on it, and treat a recorded authorization *request* as a request —
never as a granted permission. Keep the recovered scope bound to the exact target
it names.

Read [continuation](references/continuation.md) for the procedure and a worked
example.

## Common Patterns

### Save a session summary (end of a delivery)
```bash
ob save "Implemented X, discovered Y, decided Z because W." \
  --type=session_summary \
  --project=<project-name> \
  --title="cognovis/<repo>#<N>: <outcome>"
```

### Recall past work before starting
```bash
ob search "topic or feature area" --limit=5
ob context --project=<project-name>
```

### Save an architectural decision
```bash
ob save "Track work in hosted Forgejo issues through ccore tracker — one tracker per repository." \
  --type=decision \
  --project=library \
  --title="ADR: Track work in hosted issues"
```

### Search with filters
```bash
ob search "deployment" --project=mira --type=session_summary --limit=10
```

## When to Use MCP Instead

Use `mcp__open-brain__*` tools when:
- Running in claude.ai web interface or iOS app (no CLI available)
- Performing admin operations: `mcp__open-brain__run_lifecycle_pipeline`, `mcp__open-brain__ingest_transcript`
- The agent prompt explicitly requires MCP tool access (e.g., `mcpServers: [open-brain]` in frontmatter)

Do NOT configure `mcpServers: [open-brain]` in agent frontmatter for coding harness agents —
they should rely on the `ob` CLI instead.
