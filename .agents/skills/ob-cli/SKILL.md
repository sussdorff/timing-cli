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
| `ob get <id>` | Fetch full observation by ID | `ob get mem_abc123` |
| `ob context` | Recent session context for current project | `ob context --project=library --limit=10` |
| `ob timeline` | Timeline view of memories | `ob timeline --project=mira` |
| `ob stats` | Database statistics | `ob stats` |
| `ob doctor` | Run server diagnostics | `ob doctor` |
| `ob update <id>` | Update an existing memory | `ob update mem_abc123 --title="New title"` |
| `ob ingest` | Ingest from external sources | `ob ingest --help` |
| `ob people <sub>` | Manage people memories | `ob people list` |

All subcommands support `--json` for machine-readable output.

## Common Patterns

### Save a session summary (end of bead run)
```bash
ob save "Implemented X, discovered Y, decided Z because W." \
  --type=session_summary \
  --project=<project-name> \
  --title="Bead CL-xxx: <outcome>"
```

### Recall past work before starting
```bash
ob search "topic or feature area" --limit=5
ob context --project=<project-name>
```

### Save an architectural decision
```bash
ob save "Use Dolt for beads tracking — provides git-like versioning for structured data." \
  --type=decision \
  --project=library \
  --title="ADR: Use Dolt for beads"
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
