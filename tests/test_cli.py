from __future__ import annotations

import json
import re
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from typer.testing import CliRunner

import timing_cli.cli as cli
from timing_cli.cli import app
from timing_cli.config import Config
from timing_cli.models import AppUsage, Project, ProjectSummary, TimeEntrySuggestion

runner = CliRunner()


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
