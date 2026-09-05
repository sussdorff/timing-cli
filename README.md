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
- **Classifies** unassigned activity onto projects with your own rules, plus a
  packaged default Cognovis ruleset that already covers most of a normal
  workday (Timing's built-in predicate rules only cover ~15% of activity). It
  also reuses decoded Timing project predicate rules from the local database
  when neither user nor default rules already assigned a slice.
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

# Install a LaunchAgent so the HTTP server auto-starts at login
timing serve --install                        # requires TIMING_MCP_TOKEN / mcp_http_token
timing serve --uninstall
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
| `timing usage [--date/--from/--to] [--project ID] [--show-path]` | Raw automatically tracked app usage. Paths stay hidden unless `--show-path` is supplied. |
| `timing summary [--date/--from/--to]` | Total time per project |
| `timing suggest [--date/--from/--to]` | Aggregated time-entry suggestions (read-only) |
| `timing push [--date/--from/--to] [--yes] [--replace]` | Create entries via Web API (dry-run by default) |
| `timing serve [--transport] [--host] [--port]` | Run the MCP server |
| `timing serve --install` / `--uninstall` | Install/remove a LaunchAgent that runs `timing serve --transport http` at login |

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
"Client / MIRA" = "/projects/123"
"id:42" = "/projects/456"

# Classification rules: map unassigned activity onto projects.
# First match wins. `app`/`bundle_id` are case-insensitive substrings;
# `title`/`path` are regexes (already matched case-insensitively, so don't
# add an inline `(?i)`).
[[rules]]
project = "MIRA"
title = "polaris"

[[rules]]
project = "Cognovis"
path = "code/mira"
```

### Default classification rules

Even with **no config file at all**, `timing-cli` ships a ready-to-use ruleset
tuned for Malte's local setup (`timing_cli/default_rules.py`,
`DEFAULT_COGNOVIS_RULES`) that maps common cmux/editor window titles and repo
paths onto real Timing projects:

- **MIRA** — Polaris/MIRA work: titles matching `polaris|mira|diagnos|isynet|
  patient|anonymiz|de-id|gc50`, or paths containing `polaris`/`mira`. (There is
  no Timing project literally named "Polaris" — it's tracked as "MIRA".)
- **Client projects** — title keywords for Syntegon, Romelag, MCN, ATR, C4B,
  NTS, BBW, Kolibri, FUD, Eubylon, Solutio, DST, Agiler Norden.
- **`]project-open[`** — title/path containing `project-open`.
- **Home Electronic** — title/path containing `home-infra` or `open-brain`.
- **cognovis Verwaltung** — internal tooling/admin keywords (`timing-cli`,
  `collmex`, `paperless`, `invoice`, `rechnung`, `library`, `beads`, `claude`,
  `codex`, `agent`, `skill`, `acp`), repo paths under `code/(cli-tools|
  library|timing-cli|collmex-cli|mm-cli)`, `.agents`, or `/skills/`, and
  finally a catch-all for any remaining `cmux` activity.

These defaults are appended **after** your own `[[rules]]` (user rules always
win, since the first matching rule wins) and are controlled by:

```toml
use_default_rules = true   # default; set to false to rely solely on your own [[rules]]
```

Timing's own project predicates are loaded from the local `Project.predicate`
column automatically and applied after both explicit config rules and the
packaged defaults. Keep local rules for repository paths, editor titles, and
project-specific conventions that neither Timing nor the packaged defaults
classify well.

### Cognovis example

This is a real-world shape for Malte's local setup. Fill the Web-API project
references from `timing projects --remote`; local project ids can be discovered
with `timing projects`. With `use_default_rules` left at its default `true`,
most of this is already covered — these overrides just fill in
`project_mappings` and add a couple of extra keywords the defaults don't know
about yet.

```toml
api_base_url = "https://web.timingapp.com/api/v1"
min_block_seconds = 120
gap_merge_seconds = 300

[project_mappings]
"MIRA" = "/projects/REMOTE_MIRA"
"cognovis Verwaltung" = "/projects/REMOTE_COGNOVIS_VERWALTUNG"
"]project-open[" = "/projects/REMOTE_PROJECT_OPEN"
"Home Electronic" = "/projects/REMOTE_HOME_ELECTRONIC"

# Extra project-specific keyword not covered by the packaged defaults.
[[rules]]
project = "cognovis Verwaltung"
title = "confluence|jira"
```

## MCP tools

`timing serve` exposes: `list_timing_projects`, `list_app_usage_tool`,
`daily_project_summary`, `suggest_time_entries`, `create_time_entry` (write),
`recorded_date_range`.

HTTP transport requires bearer-token authentication via `TIMING_MCP_TOKEN` or
`mcp_http_token` in the config. Stdio transport remains local and does not require
an MCP token.

### LaunchAgent (persistent local HTTP server)

`timing serve --install` writes a LaunchAgent plist
(`~/Library/LaunchAgents/de.sussdorff.timing-serve.plist`, label
`de.sussdorff.timing-serve`) that runs `timing serve --transport http` at login
(`RunAtLoad`/`KeepAlive`, `LimitLoadToSessionType=Aqua`). Logs go to
`~/Library/Logs/timing-serve.log` / `.err.log`. Installing requires
`TIMING_MCP_TOKEN` or `mcp_http_token` to already be set — the command raises an
error otherwise instead of silently generating a token. `timing serve --uninstall`
unloads the agent (`launchctl bootout`) and removes the plist.

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
