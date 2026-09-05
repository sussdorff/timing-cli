from __future__ import annotations

import os
import plistlib
import time as time_module
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from timing_cli import serve
from timing_cli.config import Config
from timing_cli.models import AppUsage, Project, ProjectSummary, TimeEntrySuggestion


@pytest.fixture(autouse=True)
def reset_mcp_auth():
    try:
        yield
    finally:
        serve.mcp.auth = None


@pytest.fixture
def berlin_timezone(monkeypatch):
    old_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "Europe/Berlin")
    if hasattr(time_module, "tzset"):
        time_module.tzset()
    try:
        yield
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        if hasattr(time_module, "tzset"):
            time_module.tzset()


@pytest.mark.parametrize(
    ("day", "expected_start", "expected_end", "elapsed_hours"),
    [
        ("2026-03-29", "2026-03-29T00:00:00+01:00", "2026-03-30T00:00:00+02:00", 23),
        ("2026-03-30", "2026-03-30T00:00:00+02:00", "2026-03-31T00:00:00+02:00", 24),
    ],
)
def test_mcp_local_day_window_follows_berlin_timezone_rules(
    berlin_timezone, day, expected_start, expected_end, elapsed_hours
):
    start, end = serve._window(day, None, None)

    assert start.isoformat() == expected_start
    assert end.isoformat() == expected_end
    assert end.timestamp() - start.timestamp() == elapsed_hours * 3600


def test_mcp_explicit_offset_window_is_preserved(berlin_timezone):
    start, end = serve._window(
        None,
        "2026-03-29T00:00:00+01:00",
        "2026-03-30T00:00:00+01:00",
    )

    assert start.isoformat() == "2026-03-29T00:00:00+01:00"
    assert end.isoformat() == "2026-03-30T01:00:00+02:00"
    assert start == datetime(2026, 3, 29, tzinfo=timezone(timedelta(hours=1)))
    assert end == datetime(2026, 3, 30, tzinfo=timezone(timedelta(hours=1)))
    assert end.timestamp() - start.timestamp() == 24 * 3600


def test_http_transport_requires_bearer_token(monkeypatch):
    monkeypatch.delenv("TIMING_MCP_TOKEN", raising=False)
    monkeypatch.setattr(serve, "load_config", lambda: Config())

    with pytest.raises(ValueError, match="HTTP transport requires"):
        serve.run_server(transport="http")


def test_http_transport_configures_auth(monkeypatch):
    monkeypatch.delenv("TIMING_MCP_TOKEN", raising=False)
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(serve, "load_config", lambda: Config(mcp_http_token="secret"))
    monkeypatch.setattr(serve.mcp, "run", fake_run)

    serve.run_server(transport="http", host="127.0.0.1", port=8321)

    assert calls == [((), {"transport": "http", "host": "127.0.0.1", "port": 8321})]
    assert isinstance(serve.mcp.auth, serve.StaticBearerTokenVerifier)


def test_existing_mcp_model_paths_use_lossless_decimal_string_ids(monkeypatch, tmp_path):
    local_id = 2**54 + 123
    start = datetime(2026, 7, 5, 9, 0).astimezone()
    end = start + timedelta(minutes=10)
    project = Project(id=local_id, title="Synthetic Project")
    usage = AppUsage(
        id=local_id,
        start=start,
        end=end,
        application_id=local_id,
        app="Synthetic Editor",
        project_id=local_id,
        project_title=project.title,
    )
    summary = ProjectSummary(
        project_id=local_id,
        project_title=project.title,
        seconds=600,
        entries=1,
    )
    suggestion = TimeEntrySuggestion(
        day="2026-07-05",
        start=start,
        end=end,
        project_id=local_id,
        project_title=project.title,
    )

    @contextmanager
    def fake_open_db(path):
        yield object()

    monkeypatch.setattr(serve, "load_config", lambda: Config(db_path=tmp_path / "Timing.db"))
    monkeypatch.setattr(serve, "open_db", fake_open_db)
    monkeypatch.setattr(
        serve, "list_projects", lambda conn, include_archived=False: [project]
    )
    monkeypatch.setattr(
        serve, "list_app_usage", lambda conn, lo, hi, project_id=None: [usage]
    )
    monkeypatch.setattr(serve, "list_timing_predicate_rules", lambda conn: [])
    monkeypatch.setattr(serve, "summarize_by_project", lambda *args, **kwargs: [summary])
    monkeypatch.setattr(serve, "aggregate", lambda *args, **kwargs: [suggestion])

    projects = serve.list_timing_projects()
    usage_rows = serve.list_app_usage_tool(day="2026-07-05")
    summaries = serve.daily_project_summary(day="2026-07-05")
    suggestions = serve.suggest_time_entries(day="2026-07-05")

    assert project.id == local_id
    assert projects[0]["id"] == str(local_id)
    assert usage_rows[0]["id"] == str(local_id)
    assert usage_rows[0]["application_id"] == str(local_id)
    assert usage_rows[0]["project_id"] == str(local_id)
    assert summaries[0]["project_id"] == str(local_id)
    assert suggestions[0]["project_id"] == str(local_id)


def test_reconstruct_mcp_emits_shared_versioned_schema_and_forwards_continuation(
    berlin_timezone, monkeypatch, tmp_path
):
    calls = []
    expected = {
        "schema_version": "timing.reconstruction.v1",
        "window": {"interval_semantics": "half-open"},
        "pagination": {"complete": False, "next_cursor": "next-page"},
        "metrics": {"scope": "window"},
        "records": [],
    }

    class FakeResponse:
        def model_dump(self, *, mode):
            assert mode == "json"
            return expected

    @contextmanager
    def fake_open_db(path):
        yield object()

    def fake_reconstruct(conn, start, end, classifier, **kwargs):
        calls.append((start, end, kwargs))
        return FakeResponse()

    monkeypatch.setattr(serve, "load_config", lambda: Config(db_path=tmp_path / "Timing.db"))
    monkeypatch.setattr(serve, "open_db", fake_open_db)
    monkeypatch.setattr(serve, "reconstruction_read_transaction", lambda conn: nullcontext())
    monkeypatch.setattr(serve, "list_timing_predicate_rules", lambda conn: [])
    monkeypatch.setattr(serve, "reconstruct_window", fake_reconstruct, raising=False)

    payload = serve.reconstruct_work(
        month="2026-07",
        limit=25,
        cursor="current-page",
    )

    assert payload == expected
    start, end, options = calls[0]
    assert start.isoformat() == "2026-07-01T00:00:00+02:00"
    assert end.isoformat() == "2026-08-01T00:00:00+02:00"
    assert options["limit"] == 25
    assert options["cursor"] == "current-page"


class TestLaunchAgentDeploy:
    """LaunchAgent install/uninstall for 'timing serve --transport http'."""

    def test_install_writes_launch_agent_plist(self, tmp_path, monkeypatch):
        fake_plist = tmp_path / "agent.plist"
        monkeypatch.setattr(serve, "LAUNCH_AGENT_PATH", fake_plist)
        monkeypatch.setattr(serve, "load_config", lambda: Config(mcp_http_token="secret"))

        with patch("timing_cli.serve.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="501", returncode=0)
            path = serve.install_launch_agent(host="127.0.0.1", port=8321)

        assert path == fake_plist
        assert fake_plist.exists()
        payload = plistlib.loads(fake_plist.read_bytes())
        assert payload["Label"] == "de.sussdorff.timing-serve"
        assert payload["LimitLoadToSessionType"] == "Aqua"
        assert payload["RunAtLoad"] is True
        assert payload["KeepAlive"] is True
        args = payload["ProgramArguments"]
        assert "serve" in args
        assert "--transport" in args
        assert "http" in args

    def test_install_without_token_raises(self, tmp_path, monkeypatch):
        fake_plist = tmp_path / "agent.plist"
        monkeypatch.setattr(serve, "LAUNCH_AGENT_PATH", fake_plist)
        monkeypatch.delenv("TIMING_MCP_TOKEN", raising=False)
        monkeypatch.setattr(serve, "load_config", lambda: Config())

        with pytest.raises(ValueError, match="HTTP transport requires"):
            serve.install_launch_agent()

        assert not fake_plist.exists()

    def test_uninstall_removes_plist(self, tmp_path, monkeypatch):
        fake_plist = tmp_path / "agent.plist"
        fake_plist.write_bytes(plistlib.dumps({"Label": "de.sussdorff.timing-serve"}))
        monkeypatch.setattr(serve, "LAUNCH_AGENT_PATH", fake_plist)

        with patch("timing_cli.serve.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="501", returncode=0)
            serve.uninstall_launch_agent()

        assert not fake_plist.exists()

    def test_uninstall_missing_plist_is_noop(self, tmp_path, monkeypatch):
        fake_plist = tmp_path / "agent.plist"
        monkeypatch.setattr(serve, "LAUNCH_AGENT_PATH", fake_plist)

        with patch("timing_cli.serve.subprocess.run") as mock_run:
            serve.uninstall_launch_agent()

        mock_run.assert_not_called()
