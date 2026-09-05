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
- **Reconstructs** bounded read-only work evidence from existing bookings and
  automatic activity without making a billing decision.

## Quickstart

```bash
# Install (globally, via uv)
uv tool install timing-cli

# See what's in your local database
timing info

# Daily project summary and suggested entries (read-only)
timing summary --date 2026-07-05
timing suggest --date 2026-07-05

# Reconstruct a synthetic example month as machine-readable evidence
timing reconstruct --month 2026-07 --limit 50 --json

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
| `timing usage [--date/--from/--to] [--project ID]` | Raw automatically tracked app usage |
| `timing summary [--date/--from/--to]` | Total time per project |
| `timing suggest [--date/--from/--to]` | Aggregated time-entry suggestions (read-only) |
| `timing push [--date/--from/--to] [--yes] [--replace]` | Create entries via Web API (dry-run by default) |
| `timing reconstruct (--month YYYY-MM | --from ISO --to ISO) [--limit N] [--cursor TOKEN] [--json]` | Page through bookings and automatic-activity reconstruction evidence |
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

## Reconstruction evidence contract

`timing reconstruct` and the MCP `reconstruct_work` tool share the
`timing.reconstruction.v1` response schema. Both are strictly read-only. Supply
either a local calendar month or both endpoints of an explicit half-open window:

```bash
timing reconstruct --month 2026-07 --limit 50 --json
timing reconstruct \
  --from 2026-07-14T09:00:00+02:00 \
  --to 2026-07-14T18:00:00+02:00 \
  --limit 50 --json
```

The equivalent MCP tool arguments are
`reconstruct_work(month="2026-07", limit=50, cursor=None)`.

A booking in that response might identify project `Synthetic Studio`, carry the
title `Synthetic design review`, and expose a lossless source ID such as
`"18014398509482083"`.

The top-level fields are:

| Field | Meaning |
| --- | --- |
| `schema_version` | Fixed value `timing.reconstruction.v1`. |
| `window` | Local timezone, exact `[start,end)` endpoints, half-open semantics, and extraction timestamp. |
| `pagination` | Requested limit, stable order (`start`, `source_type`, `source_id`), SQL total/returned counts, completeness, and opaque `next_cursor`. |
| `metrics` | Whole-window duration metrics; `scope` is always `window`, independent of the returned page. |
| `records` | At most `limit` page-scoped booking/activity records with full titles and paths, assignment evidence, relationships, conflicts, and uncovered candidate intervals. |

The maximum page size is 200. Continue with the returned cursor until
`pagination.complete` is true; this retrieves every source record in the month
without materializing the month as one list. Source rows use SQL keyset paging,
and whole-window calculations scan those rows in bounded batches. Relationship
lists on a record are also capped at 200 and carry their own `*_complete` flag,
so dense evidence is never silently presented as complete. Stable source
references have the form `booking:<decimal-id>` or `activity:<decimal-id>`.
Ordering uses the clipped `source.start`, then bookings before activities, then
the decimal source ID. Project title chains retain the 32 most-specific entries
and expose `project_title_chain_complete`; assignment alternatives are capped at
100 and expose `alternatives_complete` and `conflicts_complete`.
Every local SQLite identifier is serialized as a decimal string on CLI JSON and
MCP boundaries, including identifiers larger than JavaScript's safe integer
range; Python and SQLite continue to use integers internally.

Each assignment includes the current project, selected/proposed project,
origin (`existing`, `user_rule`, `packaged_rule`, `timing_predicate`, or
`unresolved`), stable rule identity, matched source field/value, bounded matching
alternatives with completeness metadata, conflict evidence, and an uncertainty
reason when applicable.
Existing assignments keep precedence, but a differently assigned booking stays
visible with its original project and proposed alternatives.

Duration fields are deliberately separate and never imply approval to charge:

| Metric | Scope and definition |
| --- | --- |
| `raw_cumulative_activity_seconds` | Window-scoped sum of every clipped automatic-activity duration; overlapping/identical slices count separately. |
| `activity_interval_union_seconds` | Window-scoped union of automatic-activity intervals; overlaps count once. |
| `elapsed_evidence_span_seconds` | Window-scoped elapsed time from the first evidence start to the last evidence end. |
| `gap_seconds` | Window-scoped evidence span not covered by either booking or automatic activity. |
| `recorded_service_seconds` | Window-scoped union of existing booking intervals; overlapping bookings count once. |
| `uncovered_candidate_seconds` | Window-scoped union of automatic activity outside every existing booking. It is evidence for review, not an approved charge. |
| `candidate_intervals[].duration_seconds` | Record-scoped uncovered portion of one automatic-activity source. |

Automatic activity covered by a booking appears as supporting evidence for that
single recorded service. Only uncovered portions appear in `candidate_intervals`.
Cross-project overlaps are retained as explicit source references rather than
being assigned to whichever row sorts first. The schema contains no rates,
rounding, invoicing, or persistent review decisions.

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
`recorded_date_range`, and `reconstruct_work` (read-only, bounded).

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
