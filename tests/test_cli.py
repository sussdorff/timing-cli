from __future__ import annotations

import json
import os
import re
import time as time_module
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from typer.testing import CliRunner

import timing_cli.cli as cli
from timing_cli.cli import app
from timing_cli.config import Config
from timing_cli.models import AppUsage, Project, ProjectSummary, TimeEntrySuggestion

runner = CliRunner()


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


@pytest.fixture
def json_command_data(monkeypatch, tmp_path):
    start = datetime(2026, 7, 5, 9, 0).astimezone()
    end = start + timedelta(minutes=10)
    project = Project(id=2**54, title="Client")
    usage = AppUsage(
        id=2**54,
        start=start,
        end=end,
        app="Editor",
        project_id=project.id,
        project_title=project.title,
    )
    summary = ProjectSummary(
        project_id=project.id,
        project_title=project.title,
        seconds=600,
        entries=1,
    )
    suggestion = TimeEntrySuggestion(
        day="2026-07-05",
        start=start,
        end=end,
        project_id=project.id,
        project_title=project.title,
        title="Client: Editor",
    )

    @contextmanager
    def fake_open_db(path):
        yield object()

    monkeypatch.setattr(cli, "_load", lambda: Config(db_path=tmp_path / "Timing.db"))
    monkeypatch.setattr(cli, "open_db", fake_open_db)
    monkeypatch.setattr(cli, "date_range", lambda conn: (start, end))
    monkeypatch.setattr(cli, "list_projects", lambda conn, include_archived=False: [project])
    monkeypatch.setattr(cli, "list_app_usage", lambda conn, start, end, project_id=None: [usage])
    monkeypatch.setattr(cli, "list_timing_predicate_rules", lambda conn: [])
    monkeypatch.setattr(cli, "summarize_by_project", lambda *args, **kwargs: [summary])
    monkeypatch.setattr(cli, "aggregate", lambda *args, **kwargs: [suggestion])

    return {
        "project": project,
        "usage": usage,
        "summary": summary,
        "suggestion": suggestion,
        "start": start,
        "end": end,
        "db_path": tmp_path / "Timing.db",
    }


def _plain_output(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_usage_rejects_invalid_date_without_traceback():
    result = runner.invoke(app, ["usage", "--date", "not-a-date"], color=False)
    output = _plain_output(result.output)

    assert result.exit_code != 0
    assert "Invalid value" in output
    assert "Traceback" not in output


def test_summary_rejects_inverted_window():
    result = runner.invoke(
        app,
        [
            "summary",
            "--from",
            "2026-07-05T23:59:00",
            "--to",
            "2026-07-05T00:00:00",
        ],
        color=False,
    )
    output = _plain_output(result.output)

    assert result.exit_code != 0
    assert "must be after" in output
    assert "Traceback" not in output


@pytest.mark.parametrize(
    ("day", "expected_start", "expected_end", "elapsed_hours"),
    [
        ("2026-03-29", "2026-03-29T00:00:00+01:00", "2026-03-30T00:00:00+02:00", 23),
        ("2026-03-30", "2026-03-30T00:00:00+02:00", "2026-03-31T00:00:00+02:00", 24),
    ],
)
def test_cli_local_day_window_follows_berlin_timezone_rules(
    berlin_timezone, day, expected_start, expected_end, elapsed_hours
):
    start, end = cli._resolve_window(day, None, None)

    assert start.isoformat() == expected_start
    assert end.isoformat() == expected_end
    assert end.timestamp() - start.timestamp() == elapsed_hours * 3600


def test_cli_explicit_offset_window_is_preserved(berlin_timezone):
    start, end = cli._resolve_window(
        None,
        "2026-03-29T00:00:00+01:00",
        "2026-03-30T00:00:00+01:00",
    )

    assert start.isoformat() == "2026-03-29T00:00:00+01:00"
    assert end.isoformat() == "2026-03-30T01:00:00+02:00"
    assert start == datetime(2026, 3, 29, tzinfo=timezone(timedelta(hours=1)))
    assert end == datetime(2026, 3, 30, tzinfo=timezone(timedelta(hours=1)))
    assert end.timestamp() - start.timestamp() == 24 * 3600


def test_serve_rejects_unknown_transport_without_traceback():
    result = runner.invoke(app, ["serve", "--transport", "nope"], color=False)
    output = _plain_output(result.output)

    assert result.exit_code == 1
    assert "Unknown transport: nope" in output
    assert "Traceback" not in output


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["info", "--json"], dict),
        (["projects", "--json"], list),
        (["usage", "--json"], list),
        (["summary", "--json"], list),
        (["suggest", "--json"], list),
        (["push", "--json"], dict),
    ],
)
def test_every_data_command_emits_plain_json(json_command_data, arguments, expected):
    result = runner.invoke(app, arguments)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert isinstance(payload, expected)


def test_info_json_has_stable_machine_fields(json_command_data):
    result = runner.invoke(app, ["info", "--json"])

    assert json.loads(result.stdout) == {
        "active_projects": 1,
        "api_token_set": False,
        "database": str(json_command_data["db_path"]),
        "recorded_end": json_command_data["end"].isoformat(),
        "recorded_start": json_command_data["start"].isoformat(),
    }


def test_push_json_reports_dry_run_and_suggestions(json_command_data):
    result = runner.invoke(app, ["push", "--json"])

    assert json.loads(result.stdout) == {
        "created": 0,
        "dry_run": True,
        "skipped": 0,
        "suggestions": [json_command_data["suggestion"].model_dump(mode="json")],
    }


@pytest.mark.parametrize(
    ("arguments", "field_path"),
    [
        (["projects", "--json"], (0, "id")),
        (["usage", "--json"], (0, "id")),
        (["summary", "--json"], (0, "project_id")),
        (["suggest", "--json"], (0, "project_id")),
        (["push", "--json"], ("suggestions", 0, "project_id")),
    ],
)
def test_existing_cli_json_uses_lossless_decimal_string_ids(
    json_command_data, arguments, field_path
):
    payload = json.loads(runner.invoke(app, arguments).stdout)
    value = payload
    for component in field_path:
        value = value[component]

    assert value == str(json_command_data["project"].id)
    assert json_command_data["project"].id == 2**54


def test_reconstruct_cli_emits_shared_versioned_schema_and_forwards_continuation(
    berlin_timezone, monkeypatch, tmp_path
):
    calls = []
    expected = {
        "schema_version": "timing.reconstruction.v1",
        "window": {
            "timezone": "Synthetic/Local",
            "interval_semantics": "half-open",
            "start": "2026-07-01T00:00:00+02:00",
            "end": "2026-08-01T00:00:00+02:00",
            "extracted_at": "2026-08-02T12:00:00Z",
        },
        "pagination": {
            "limit": 25,
            "stable_order": ["start", "source_type", "source_id"],
            "total_count": 40,
            "returned_count": 25,
            "complete": False,
            "next_cursor": "next-page",
        },
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

    monkeypatch.setattr(cli, "_load", lambda: Config(db_path=tmp_path / "Timing.db"))
    monkeypatch.setattr(cli, "open_db", fake_open_db)
    monkeypatch.setattr(cli, "list_timing_predicate_rules", lambda conn: [])
    monkeypatch.setattr(cli, "reconstruct_window", fake_reconstruct, raising=False)

    result = runner.invoke(
        app,
        [
            "reconstruct",
            "--month",
            "2026-07",
            "--limit",
            "25",
            "--cursor",
            "current-page",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == expected
    start, end, options = calls[0]
    assert start.isoformat() == "2026-07-01T00:00:00+02:00"
    assert end.isoformat() == "2026-08-01T00:00:00+02:00"
    assert options["limit"] == 25
    assert options["cursor"] == "current-page"


def test_reconstruct_cli_rejects_uncapped_limit():
    result = runner.invoke(app, ["reconstruct", "--month", "2026-07", "--limit", "201"])

    assert result.exit_code == 2
    assert "200" in result.output
