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
  built-in predicate rules only cover ~15% of activity). It also reuses decoded
  Timing project predicate rules from the local database when Timing did not
  already assign a slice.
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
timing serve                                  # stdio
export TIMING_MCP_TOKEN=...
timing serve --transport http                 # HTTP on 127.0.0.1:8321
```

`timing push --yes` resolves every non-unassigned suggestion to a unique Web-API
project before creating anything. If a project is ambiguous or unmapped, the push
fails before the first write; add a `[project_mappings]` override. Re-running the
same push skips matching existing entries unless `--replace` is passed.

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

## Daily workflow

```bash
# 1. Inspect the day without writing anything.
timing summary --date 2026-07-05
timing suggest --date 2026-07-05

# 2. If push projects are unmapped, inspect remote project references.
export TIMING_API_KEY=...
timing projects --remote

# 3. Add missing [project_mappings] entries, then dry-run again.
timing push --date 2026-07-05

# 4. Create entries once the dry-run looks right.
timing push --date 2026-07-05 --yes
```

Re-running step 4 for the same day skips matching existing entries. Use
`--replace` only when you deliberately want Timing's API to replace overlapping
entries in the target window.

## Configuration

Optional config at `~/.config/timing-cli/config.toml`:

```toml
# Override the database path if Timing lives elsewhere.
# db_path = "~/Library/Application Support/info.eurocomp.Timing2/SQLite.db"

api_base_url = "https://web.timingapp.com/api/v1"
# api_token = "..."   # prefer the TIMING_API_KEY env var instead
# mcp_http_token = "..."   # prefer the TIMING_MCP_TOKEN env var instead

min_block_seconds = 120    # drop aggregated blocks shorter than this
gap_merge_seconds = 300    # merge same-project slices split by a gap up to this

# Optional overrides from local Timing projects to Web-API project references.
# Keys can be a local id ("id:42"), a full title chain, or a leaf title.
[project_mappings]
"Client / Polaris" = "/projects/123"
"id:42" = "/projects/456"

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

### Cognovis example

This is a real-world shape for Malte's local setup. Fill the Web-API project
references from `timing projects --remote`; local project ids can be discovered
with `timing projects`.

```toml
api_base_url = "https://web.timingapp.com/api/v1"
min_block_seconds = 120
gap_merge_seconds = 300

[project_mappings]
"cognovis Verwaltung" = "/projects/REMOTE_COGNOVIS_VERWALTUNG"
"]project-open[" = "/projects/REMOTE_PROJECT_OPEN"
"Home Electronic" = "/projects/REMOTE_HOME_ELECTRONIC"

[[rules]]
project = "cognovis Verwaltung"
title = "(timing|collmex|paperless|invoice|rechnung)"

[[rules]]
project = "cognovis Verwaltung"
path = "code/(cli-tools|library)"

[[rules]]
project = "]project-open["
app = "Mail"
title = "project-open"
```

Timing's own project predicates are loaded from the local `Project.predicate`
column automatically and applied after explicit config rules. Keep local rules
for repository paths, editor titles, and project-specific conventions that
Timing itself does not classify well.

## MCP tools

`timing serve` exposes: `list_timing_projects`, `list_app_usage_tool`,
`daily_project_summary`, `suggest_time_entries`, `create_time_entry` (write),
`recorded_date_range`.

HTTP transport requires bearer-token authentication via `TIMING_MCP_TOKEN` or
`mcp_http_token` in the config. Stdio transport remains local and does not require
an MCP token.

## Release

The repository includes a GitHub Actions release workflow at
`.github/workflows/release.yml`. Tag pushes run tests and lint only; published
GitHub releases or manual dispatches build the package and publish to PyPI using
Trusted Publishing. Configure a PyPI trusted publisher for the repository and
the `pypi` environment before running the publish job.

## Requirements

- macOS with Timing.app installed
- Python 3.12+ (installed automatically by `uv tool install`)
- A Timing Web API token for pushing entries (read-only commands need no token)

## License

MIT
