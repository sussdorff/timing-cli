from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import UTC, datetime

from typer.testing import CliRunner

import timing_cli.cli as cli
from timing_cli.cli import app
from timing_cli.config import Config
from timing_cli.models import AppUsage

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


def test_usage_show_path_displays_document_path(monkeypatch):
    path = "file:///Users/example/Notes/reflections.md"
    slice_ = AppUsage(
        id=1,
        start=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
        end=datetime(2026, 8, 28, 12, 5, tzinfo=UTC),
        app="MarkEdit",
        path=path,
    )

    @contextmanager
    def fake_open_db(_path):
        yield object()

    monkeypatch.setattr(cli, "_load", lambda: Config())
    monkeypatch.setattr(cli, "open_db", fake_open_db)
    monkeypatch.setattr(cli, "list_app_usage", lambda *_args, **_kwargs: [slice_])

    result = runner.invoke(app, ["usage", "--date", "2026-08-28", "--show-path"], color=False)
    output = _plain_output(result.output)

    assert result.exit_code == 0
    assert "Path" in output
    assert "reflections.md" in output
