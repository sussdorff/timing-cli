"""Keep tests independent of the developer's home and Git configuration."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def _set_isolated_environment(monkeypatch, home):
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local" / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # Product defaults are bound while test modules import, before fixtures run.
    session_home = TemporaryDirectory(prefix="timing-cli-test-home-")
    session_patch = pytest.MonkeyPatch()
    _set_isolated_environment(session_patch, Path(session_home.name))
    config._timing_cli_test_isolation = (session_patch, session_home)


def pytest_unconfigure(config):
    isolation = getattr(config, "_timing_cli_test_isolation", None)
    if isolation is not None:
        session_patch, session_home = isolation
        session_patch.undo()
        session_home.cleanup()


@pytest.fixture(autouse=True)
def _isolated_environment(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("home")
    _set_isolated_environment(monkeypatch, home)
