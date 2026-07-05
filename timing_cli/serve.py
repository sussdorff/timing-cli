"""FastMCP server exposing the local Timing database to agents.

The server runs on the machine where the Timing database lives, so agents (e.g.
the Hermes personal agent) can query real local app usage and push time entries
WITHOUT ever copying or sharing the raw ``SQLite.db``.

Run it via ``timing serve`` (stdio by default, or ``--transport http``).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from fastmcp import FastMCP

from timing_cli.analysis import aggregate, summarize_by_project
from timing_cli.api import TimingApiClient, TimingApiError
from timing_cli.config import load_config
from timing_cli.db import date_range, list_app_usage, list_projects, open_db
from timing_cli.rules import Classifier

mcp: FastMCP = FastMCP("timing-cli")


def _day_window(day: str | None) -> tuple[datetime, datetime]:
    d = date.fromisoformat(day) if day else date.today()
    start = datetime.combine(d, time.min).astimezone()
    return start, start + timedelta(days=1)


def _window(day: str | None, start: str | None, end: str | None) -> tuple[datetime, datetime]:
    if start or end:
        lo = datetime.fromisoformat(start).astimezone() if start else _day_window(day)[0]
        hi = datetime.fromisoformat(end).astimezone() if end else datetime.now().astimezone()
        return lo, hi
    return _day_window(day)


@mcp.tool
def list_timing_projects(include_archived: bool = False) -> list[dict[str, Any]]:
    """List Timing projects from the local database."""
    cfg = load_config()
    with open_db(cfg.db_path) as conn:
        projects = list_projects(conn, include_archived=include_archived)
    return [p.model_dump() for p in projects]


@mcp.tool
def list_app_usage_tool(
    day: str | None = None,
    start: str | None = None,
    end: str | None = None,
    project_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return raw automatically tracked app usage for a local day or window.

    Provide either ``day`` (YYYY-MM-DD, defaults to today) or an explicit
    ``start``/``end`` ISO-8601 window.
    """
    cfg = load_config()
    lo, hi = _window(day, start, end)
    with open_db(cfg.db_path) as conn:
        slices = list_app_usage(conn, lo, hi, project_id=project_id)
    return [s.model_dump(mode="json") for s in slices]


@mcp.tool
def daily_project_summary(day: str | None = None, include_unassigned: bool = True) -> list[dict[str, Any]]:
    """Total tracked time per project for a local day (defaults to today)."""
    cfg = load_config()
    lo, hi = _day_window(day)
    classifier = Classifier(cfg.rules)
    with open_db(cfg.db_path) as conn:
        slices = list_app_usage(conn, lo, hi)
    summaries = summarize_by_project(slices, classifier, include_unassigned=include_unassigned)
    return [s.model_dump() for s in summaries]


@mcp.tool
def suggest_time_entries(
    day: str | None = None,
    start: str | None = None,
    end: str | None = None,
    include_unassigned: bool = False,
) -> list[dict[str, Any]]:
    """Aggregate app usage into suggested time entries. Read-only (does not write)."""
    cfg = load_config()
    lo, hi = _window(day, start, end)
    classifier = Classifier(cfg.rules)
    with open_db(cfg.db_path) as conn:
        slices = list_app_usage(conn, lo, hi)
    suggestions = aggregate(
        slices,
        classifier,
        min_block_seconds=cfg.min_block_seconds,
        gap_merge_seconds=cfg.gap_merge_seconds,
        include_unassigned=include_unassigned,
    )
    return [s.model_dump(mode="json") for s in suggestions]


@mcp.tool
def create_time_entry(
    start: str,
    end: str,
    title: str,
    project_title: str | None = None,
    notes: str = "",
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Create a single time entry via the Timing Web API (write operation).

    ``start``/``end`` are ISO-8601 datetimes. When ``project_title`` is given it
    is matched against Web-API projects by title; if unmatched the entry is
    created without a project link.
    """
    cfg = load_config()
    lo = datetime.fromisoformat(start).astimezone()
    hi = datetime.fromisoformat(end).astimezone()
    try:
        with TimingApiClient(cfg.api_base_url, cfg.resolved_token()) as client:
            project_ref = client.find_project_ref(project_title) if project_title else None
            return client.create_time_entry(
                start=lo,
                end=hi,
                project_ref=project_ref,
                title=title,
                notes=notes,
                replace_existing=replace_existing,
            )
    except TimingApiError as exc:
        return {"error": str(exc)}


@mcp.tool
def recorded_date_range() -> dict[str, str] | None:
    """Return the earliest and latest recorded activity timestamps."""
    cfg = load_config()
    with open_db(cfg.db_path) as conn:
        rng = date_range(conn)
    if rng is None:
        return None
    return {"start": rng[0].isoformat(), "end": rng[1].isoformat()}


def run_server(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8321) -> None:
    """Start the MCP server over the requested transport."""
    if transport == "stdio":
        mcp.run()
    elif transport in ("http", "streamable-http"):
        mcp.run(transport="http", host=host, port=port)
    else:  # pragma: no cover - guarded by CLI
        raise ValueError(f"Unknown transport: {transport}")


if __name__ == "__main__":
    run_server()
