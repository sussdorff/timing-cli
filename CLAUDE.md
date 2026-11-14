# Project Instructions for AI Agents

Read `AGENTS.md` for the tracker and pull request rules.

## Build & Test

Run these before a push; `.github/workflows/ci.yml` runs the same checks:

```bash
uv run pytest -q
uv run ruff check .
uv run bandit -r timing_cli -q
uv build
bash scripts/dev/preflight.sh   # toolchain version check
```

`scripts/dev/check_toolchain_versions.py` is a copy of the shared toolchains check;
ruff excludes it.
