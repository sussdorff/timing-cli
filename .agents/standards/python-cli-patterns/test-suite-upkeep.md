# Test Suite Upkeep

A CLI built test-first accumulates one test per RED step. Once the feature is
green, some of those tests have done their job. Keep the suite honest, run it in
parallel, and isolate it from the developer's machine.

## Value Review

The installed `tdd` skill owns the general testing method — what a good test is,
where seams go, the anti-patterns. It does not cover a suite that already exists.
The keep, repair, replace and remove dispositions and the evidence each one needs
are the `test-audit` skill's procedure, and this standard does not hold a second
copy of them.

A value review starts when a person runs `/test-audit` for this repository or a
path set in it; the skill is explicit-only, so no agent begins one off an ordinary
test edit. Bring that review to the suite at least once per release train, and
follow the dispositions it returns.

`test-audit` is distributed by the `cognovis-daily` Workspace. Where a repository's
Workspace does not carry it, it has to be installed explicitly; report the missing
command as a setup gap rather than installing it, running it unasked, or rebuilding
its dispositions here.

Two runtime signals say the audit is overdue sooner:

- a serial local run exceeding about one minute
- CI and local runtimes differing by more than a factor of three, which means the
  developer's environment is leaking into the tests; see Isolation below

As part of an authorized repair in the existing delivery, delete fixtures and helpers
that no remaining test references, and update any document that lists test files by
path. An audit-only review recommends that cleanup in its report and changes nothing.

## Parallel Execution

Run the suite with pytest-xdist by default:

```toml
[dependency-groups]
dev = ["pytest>=8.0", "pytest-xdist>=3.8", "ruff>=0.9"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-n auto"
```

`-n0` runs serially for debugging. A test that fails only in parallel shares
state through the home directory, a fixed port, a fixed path or the working
directory. Fix the sharing; do not mark the test serial.

## Isolation

One autouse fixture in `tests/conftest.py` keeps every test and every worker
away from the real home directory and the developer's git configuration:

```python
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_environment(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local" / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
```

Without `GIT_CONFIG_GLOBAL`, a global `core.hooksPath`, commit signing or
templates run on every fixture commit. In ccore that took a commit from
0.03 s to 3.8 s, and a 90-second CI suite took 27 minutes locally. Add any
tool-specific state paths (metrics databases, journals) to the same fixture.

## Subprocess Calls

Tests that exercise the CLI as a process call the installed entry point of the
test environment directly:

```python
import sys
from pathlib import Path

TOOL = str(Path(sys.executable).with_name("my-tool"))
```

Do not call `uv run my-tool` from a test. Each call resolves and syncs the
environment again, and parallel workers contend for the same lock. Prefer
calling `main(argv)` in-process where the test does not need a real process
boundary.

## Lint Scope

`ruff check .` lints only the project's own sources. Library-managed copies of
skills and standards (`.agents/`, `.claude/`) are linted in their source
repository:

```toml
[tool.ruff]
extend-exclude = [".agents", ".claude"]
```

Otherwise the first Library sync that tracks those directories fails every CI
run for reasons outside the project.
