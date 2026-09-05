# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Plain `--json` output for every data-producing CLI command, with lossless
  decimal-string local identifiers on CLI and MCP boundaries.
- A global `--no-color` option, automatic ANSI suppression for non-TTY stdout,
  and non-TTY-safe handling that avoids progress indicators and spinners.
- Versioned, bounded CLI/MCP reconstruction of existing bookings and automatic
  activity with lossless local identifiers, assignment evidence, interval
  metrics, conflicts, and continuation cursors.
- A credential-free Executive Pack UAT registry with a CLI resource restricted
  to `--help` and the read-only local `info`, `projects`, `usage`, `summary`,
  `suggest`, and `reconstruct` prefixes, including explicit `--no-color` forms,
  plus a read-only artifact resource limited to `evidence`, `README.md`, and
  `CHANGELOG.md` with source, tests, Git metadata, and writes excluded; `push`
  and `serve` remain outside the CLI allowlist.
- Initial scaffold of `timing-cli`.
- Read-only access to the local Timing.app SQLite database (`db.py`).
- Rule-based classification of app usage onto projects (`rules.py`).
- Aggregation of app usage into gap-merged time-entry suggestions (`analysis.py`).
- Timing Web API client for pushing time entries (`api.py`).
- Typer CLI: `info`, `projects`, `usage`, `summary`, `suggest`, `push`, `serve`.
- FastMCP server exposing local activity and entry creation to agents (`serve.py`).

### Fixed

- Local calendar-day windows in CLI and MCP queries now end at the next local
  midnight with the applicable timezone offset, including daylight-saving
  transitions.
