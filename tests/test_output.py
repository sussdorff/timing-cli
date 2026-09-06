from __future__ import annotations

import importlib.metadata
import json
import sys
from datetime import datetime, timedelta

from typer.testing import CliRunner

from timing_cli import output
from timing_cli.cli import app
from timing_cli.models import AppUsage, ProjectSummary, TimeEntrySuggestion

runner = CliRunner()


def test_configure_output_disables_color_when_requested(monkeypatch):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    output.configure_output(no_color=True)

    assert output.console.no_color is True
    assert output.err_console.no_color is True


def test_configure_output_disables_color_for_non_tty(monkeypatch):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

    output.configure_output(no_color=False)

    assert output.console.no_color is True
    assert output.err_console.no_color is True


def test_cli_accepts_global_no_color_option():
    result = runner.invoke(app, ["--no-color", "--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f'timing-cli {importlib.metadata.version("timing-cli")}'


def test_regression_cli_version_matches_distribution_metadata():
    # Guard against the CLI version drifting from installed package metadata.
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f'timing-cli {importlib.metadata.version("timing-cli")}'


def test_data_renderers_emit_plain_model_json_without_rich(monkeypatch, capsys):
    start = datetime(2026, 7, 5, 9, 0).astimezone()
    usage = AppUsage(
        id=2**54,
        start=start,
        end=start + timedelta(minutes=10),
        app="Editor",
        project_title="Client",
    )
    summary = ProjectSummary(project_id=2**54, project_title="Client", seconds=600, entries=1)
    suggestion = TimeEntrySuggestion(
        day="2026-07-05",
        start=start,
        end=start + timedelta(minutes=10),
        project_id=2**54,
        project_title="Client",
        title="Client: Editor",
    )

    def fail_rich(*args, **kwargs):
        raise AssertionError("JSON output touched Rich")

    monkeypatch.setattr(output.console, "print", fail_rich)
    monkeypatch.setattr(output.err_console, "print", fail_rich)

    output.render_usage([usage], json_output=True)
    usage_payload = json.loads(capsys.readouterr().out)
    output.render_summary([summary], json_output=True)
    summary_payload = json.loads(capsys.readouterr().out)
    output.render_suggestions([suggestion], json_output=True)
    suggestion_payload = json.loads(capsys.readouterr().out)

    assert usage_payload == [usage.model_dump(mode="json")]
    assert summary_payload == [summary.model_dump(mode="json")]
    assert suggestion_payload == [suggestion.model_dump(mode="json")]
