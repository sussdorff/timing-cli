from __future__ import annotations

from typer.testing import CliRunner

from timing_cli.cli import app

runner = CliRunner()


def test_usage_rejects_invalid_date_without_traceback():
    result = runner.invoke(app, ["usage", "--date", "not-a-date"])

    assert result.exit_code != 0
    assert "Invalid value" in result.output
    assert "Traceback" not in result.output


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
    )

    assert result.exit_code != 0
    assert "--to must be after --from" in result.output
    assert "Traceback" not in result.output


def test_serve_rejects_unknown_transport_without_traceback():
    result = runner.invoke(app, ["serve", "--transport", "nope"])

    assert result.exit_code == 1
    assert "Unknown transport: nope" in result.output
    assert "Traceback" not in result.output
