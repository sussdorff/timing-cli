# timing-cli

A command-line interface **and MCP server** for [Timing.app](https://timingapp.com/)
on macOS. Unlike the Timing Web API — which cannot see your locally recorded app
usage — `timing-cli` reads Timing's **local activity database directly**
(read-only) and turns real app usage into aggregated time entries, which it can
then push back to Timing via the Web API.

Because it ships an embedded MCP server, agents (e.g. the Hermes personal agent)
can query your activity and create entries **without ever copying or exposing
the raw `SQLite.db`** — the server runs locally, next to the database.

> **Not affiliated with Timing.** Independent tool. It only ever *reads* the
> local database; all writes go through the official Web API.

## What it does

- **Reads** the local Timing store (`~/Library/Application Support/info.eurocomp.Timing2/SQLite.db`)
  read-only: automatic app activity, window titles, document paths, projects.
- **Classifies** unassigned activity onto projects with your own rules (Timing's
  built-in predicate rules only cover ~15% of activity).
- **Aggregates** consecutive same-project slices into clean time blocks
  (gap-merging + minimum-duration filtering).
- **Pushes** the resulting suggestions to Timing as real time entries via the
  Web API (with a safe dry-run default).
- **Serves** all of this over MCP (`timing serve`) for agents.

## Quickstart

```bash
# Install (globally, via uv)
uv tool install timing-cli

# See what's in your local database
timing info

# Daily project summary and suggested entries (read-only)
timing summary --date 2026-07-05
timing suggest --date 2026-07-05

# Push suggestions to Timing (dry-run first, then --yes)
export TIMING_API_KEY=...    # from https://web.timingapp.com/integrations/tokens
timing push --date 2026-07-05          # dry-run
timing push --date 2026-07-05 --yes    # actually create entries

# Run the MCP server (for Hermes / other agents)
timing serve                    # stdio
timing serve --transport http   # streamable HTTP on 127.0.0.1:8321
```

## Commands

| Command | Description |
| --- | --- |
| `timing info` | Database location, recorded date range, token status |
| `timing projects [--remote] [--archived]` | List projects (local DB or Web API) |
| `timing usage [--date/--from/--to] [--project ID]` | Raw automatically tracked app usage |
| `timing summary [--date/--from/--to]` | Total time per project |
| `timing suggest [--date/--from/--to]` | Aggregated time-entry suggestions (read-only) |
| `timing push [--date/--from/--to] [--yes] [--replace]` | Create entries via Web API (dry-run by default) |
| `timing serve [--transport] [--host] [--port]` | Run the MCP server |

## Configuration

Optional config at `~/.config/timing-cli/config.toml`:

```toml
# Override the database path if Timing lives elsewhere.
# db_path = "~/Library/Application Support/info.eurocomp.Timing2/SQLite.db"

api_base_url = "https://web.timingapp.com/api/v1"
# api_token = "..."   # prefer the TIMING_API_KEY env var instead

min_block_seconds = 120    # drop aggregated blocks shorter than this
gap_merge_seconds = 300    # merge same-project slices split by a gap up to this

# Classification rules: map unassigned activity onto projects.
# First match wins. `app`/`bundle_id` are case-insensitive substrings;
# `title`/`path` are regexes.
[[rules]]
project = "Polaris"
title = "polaris"

[[rules]]
project = "Cognovis"
path = "code/mira"
```

## MCP tools

`timing serve` exposes: `list_timing_projects`, `list_app_usage_tool`,
`daily_project_summary`, `suggest_time_entries`, `create_time_entry` (write),
`recorded_date_range`.

## Requirements

- macOS with Timing.app installed
- Python 3.12+ (installed automatically by `uv tool install`)
- A Timing Web API token for pushing entries (read-only commands need no token)

## License

MIT
