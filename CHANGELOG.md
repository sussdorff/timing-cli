# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial scaffold of `timing-cli`.
- Read-only access to the local Timing.app SQLite database (`db.py`).
- Rule-based classification of app usage onto projects (`rules.py`).
- Aggregation of app usage into gap-merged time-entry suggestions (`analysis.py`).
- Timing Web API client for pushing time entries (`api.py`).
- Typer CLI: `info`, `projects`, `usage`, `summary`, `suggest`, `push`, `serve`.
- FastMCP server exposing local activity and entry creation to agents (`serve.py`).
