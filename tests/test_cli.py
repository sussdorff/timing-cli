from __future__ import annotations

import re

from typer.testing import CliRunner

from timing_cli.cli import app

runner = CliRunner()


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
