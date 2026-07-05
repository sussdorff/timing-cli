"""Typer CLI for timing-cli."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import typer

from timing_cli import __version__
from timing_cli.analysis import aggregate, summarize_by_project
from timing_cli.api import TimingApiClient, TimingApiError
from timing_cli.config import Config, load_config
from timing_cli.db import (
    TimingDatabaseError,
    date_range,
    list_app_usage,
    list_projects,
    list_timing_predicate_rules,
    open_db,
)
from timing_cli.models import TimeEntrySuggestion
from timing_cli.output import console, err_console, render_suggestions, render_summary, render_usage
from timing_cli.rules import UNASSIGNED, Classifier

app = typer.Typer(
    name="timing",
    help="Read the local Timing.app database and generate/push time entries.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"timing-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit"
    ),
) -> None:
    """timing-cli - local Timing.app activity to Timing time entries."""


def _resolve_window(
    date_opt: str | None,
    from_opt: str | None,
    to_opt: str | None,
) -> tuple[datetime, datetime]:
    """Resolve a local [start, end) window from the CLI date options.

    Precedence: explicit --from/--to override --date; --date selects a whole
    local day; with nothing given, defaults to today.
    """
    try:
        if from_opt or to_opt:
            start = (
                datetime.fromisoformat(from_opt).astimezone()
                if from_opt
                else _day_start(date.today())
            )
            end = (
                datetime.fromisoformat(to_opt).astimezone()
                if to_opt
                else datetime.now().astimezone()
            )
        else:
            day = date.fromisoformat(date_opt) if date_opt else date.today()
            start = _day_start(day)
            end = start + timedelta(days=1)
    except ValueError as exc:
        raise typer.BadParameter("Use ISO-8601 dates, e.g. 2026-07-05") from exc

    if end <= start:
        raise typer.BadParameter("--to must be after --from")
    return start, end


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min).astimezone()


def _load() -> Config:
    return load_config()


def _exit_with_error(message: str) -> None:
    err_console.print(f"[red]{message}[/red]")
    raise typer.Exit(1)


DateOpt = typer.Option(None, "--date", "-d", help="Local day YYYY-MM-DD (default: today)")
FromOpt = typer.Option(None, "--from", "-f", help="Start datetime (ISO 8601), overrides --date")
ToOpt = typer.Option(None, "--to", "-t", help="End datetime (ISO 8601), overrides --date")


@app.command()
def info() -> None:
    """Show the database location and the recorded activity date range."""
    cfg = _load()
    console.print(f"Database: [cyan]{cfg.db_path}[/cyan]")
    try:
        with open_db(cfg.db_path) as conn:
            rng = date_range(conn)
            projects = list_projects(conn, include_archived=False)
    except TimingDatabaseError as exc:
        _exit_with_error(str(exc))
    if rng:
        console.print(
            f"Recorded: [green]{rng[0]:%Y-%m-%d}[/green] -> "
            f"[green]{rng[1]:%Y-%m-%d}[/green]"
        )
    console.print(f"Active projects: {len(projects)}")
    console.print(f"API token: {'set' if cfg.resolved_token() else '[yellow]not set[/yellow]'}")


@app.command()
def projects(
    remote: bool = typer.Option(False, "--remote", help="List projects from the Web API instead"),
    archived: bool = typer.Option(False, "--archived", help="Include archived projects"),
) -> None:
    """List projects (local database by default, or the Web API with --remote)."""
    cfg = _load()
    if remote:
        try:
            with TimingApiClient(cfg.api_base_url, cfg.resolved_token()) as client:
                for p in client.list_projects(hide_archived=not archived):
                    chain = " / ".join(p.get("title_chain") or [p.get("title", "")])
                    console.print(f"[magenta]{p.get('self')}[/magenta]  {chain}")
        except TimingApiError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        return
    try:
        with open_db(cfg.db_path) as conn:
            for p in list_projects(conn, include_archived=archived):
                marker = " [dim](archived)[/dim]" if p.is_archived else ""
                console.print(f"[magenta]{p.id}[/magenta]  {p.title}{marker}")
    except TimingDatabaseError as exc:
        _exit_with_error(str(exc))


@app.command()
def usage(
    date_opt: str | None = DateOpt,
    from_opt: str | None = FromOpt,
    to_opt: str | None = ToOpt,
    project_id: int | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Filter by local project id",
    ),
) -> None:
    """Show raw automatically tracked app usage for a window."""
    cfg = _load()
    start, end = _resolve_window(date_opt, from_opt, to_opt)
    try:
        with open_db(cfg.db_path) as conn:
            slices = list_app_usage(conn, start, end, project_id=project_id)
    except TimingDatabaseError as exc:
        _exit_with_error(str(exc))
    render_usage(slices)


@app.command()
def summary(
    date_opt: str | None = DateOpt,
    from_opt: str | None = FromOpt,
    to_opt: str | None = ToOpt,
    include_unassigned: bool = typer.Option(
        True, "--unassigned/--no-unassigned", help="Include time not mapped to any project"
    ),
) -> None:
    """Show total tracked time per project for a window."""
    cfg = _load()
    start, end = _resolve_window(date_opt, from_opt, to_opt)
    try:
        with open_db(cfg.db_path) as conn:
            slices = list_app_usage(conn, start, end)
            timing_rules = list_timing_predicate_rules(conn)
    except TimingDatabaseError as exc:
        _exit_with_error(str(exc))
    classifier = Classifier(cfg.rules, timing_rules=timing_rules)
    summaries = summarize_by_project(slices, classifier, include_unassigned=include_unassigned)
    render_summary(summaries, title=f"Project summary {start:%Y-%m-%d} .. {end:%Y-%m-%d}")


@app.command()
def suggest(
    date_opt: str | None = DateOpt,
    from_opt: str | None = FromOpt,
    to_opt: str | None = ToOpt,
    include_unassigned: bool = typer.Option(
        False, "--unassigned/--no-unassigned", help="Also suggest entries for unassigned time"
    ),
) -> None:
    """Show suggested time entries aggregated from app usage (does not write)."""
    cfg = _load()
    start, end = _resolve_window(date_opt, from_opt, to_opt)
    try:
        with open_db(cfg.db_path) as conn:
            slices = list_app_usage(conn, start, end)
            timing_rules = list_timing_predicate_rules(conn)
    except TimingDatabaseError as exc:
        _exit_with_error(str(exc))
    classifier = Classifier(cfg.rules, timing_rules=timing_rules)
    suggestions = aggregate(
        slices,
        classifier,
        min_block_seconds=cfg.min_block_seconds,
        gap_merge_seconds=cfg.gap_merge_seconds,
        include_unassigned=include_unassigned,
    )
    render_suggestions(suggestions)


@app.command()
def push(
    date_opt: str | None = DateOpt,
    from_opt: str | None = FromOpt,
    to_opt: str | None = ToOpt,
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Actually create entries (default: dry-run)",
    ),
    replace: bool = typer.Option(False, "--replace", help="Replace overlapping existing entries"),
    include_unassigned: bool = typer.Option(
        False, "--unassigned/--no-unassigned", help="Also push unassigned time"
    ),
) -> None:
    """Create Timing time entries from suggestions via the Web API.

    Defaults to a dry-run. Pass --yes to actually create entries. Non-unassigned
    projects must resolve to one unique Web-API project before anything is
    written.
    """
    cfg = _load()
    start, end = _resolve_window(date_opt, from_opt, to_opt)
    try:
        with open_db(cfg.db_path) as conn:
            slices = list_app_usage(conn, start, end)
            timing_rules = list_timing_predicate_rules(conn)
    except TimingDatabaseError as exc:
        _exit_with_error(str(exc))
    classifier = Classifier(cfg.rules, timing_rules=timing_rules)
    suggestions = aggregate(
        slices,
        classifier,
        min_block_seconds=cfg.min_block_seconds,
        gap_merge_seconds=cfg.gap_merge_seconds,
        include_unassigned=include_unassigned,
    )
    render_suggestions(suggestions)

    if not suggestions:
        console.print("[yellow]Nothing to push.[/yellow]")
        return
    if not yes:
        console.print(
            f"[yellow]Dry-run:[/yellow] would create {len(suggestions)} entries. "
            "Re-run with --yes to push."
        )
        return

    try:
        with TimingApiClient(cfg.api_base_url, cfg.resolved_token()) as client:
            ref_cache: dict[tuple[int | None, tuple[str, ...], str], str | None] = {}
            planned: list[tuple[TimeEntrySuggestion, str | None]] = []
            unmapped: list[str] = []

            for s in suggestions:
                project_ref = None
                if s.project_title != UNASSIGNED:
                    key = (s.project_id, tuple(s.project_title_chain), s.project_title)
                    if key not in ref_cache:
                        ref_cache[key] = client.resolve_project_ref(
                            s.project_title,
                            title_chain=s.project_title_chain,
                            project_id=s.project_id,
                            overrides=cfg.project_mappings,
                        )
                    project_ref = ref_cache[key]
                    if project_ref is None:
                        label = " / ".join(s.project_title_chain) or s.project_title
                        unmapped.append(label)
                planned.append((s, project_ref))

            if unmapped:
                projects = ", ".join(sorted(set(unmapped)))
                _exit_with_error(
                    "Could not map local projects to Timing Web API projects: "
                    f"{projects}. Add [project_mappings] entries or rename projects."
                )

            existing_entries = [] if replace else client.list_time_entries(start, end)
            created = 0
            skipped = 0
            for s, project_ref in planned:
                if not replace and client.has_matching_time_entry(
                    existing_entries,
                    s.start,
                    s.end,
                    s.title,
                    project_ref,
                ):
                    skipped += 1
                    continue
                client.create_time_entry(
                    start=s.start,
                    end=s.end,
                    project_ref=project_ref,
                    title=s.title,
                    notes=s.notes,
                    replace_existing=replace,
                )
                created += 1
            message = f"Created {created} time entries."
            if skipped:
                message += f" Skipped {skipped} existing entries."
            console.print(f"[green]{message}[/green]")
    except TimingApiError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


@app.command()
def serve(
    transport: str = typer.Option("stdio", "--transport", help="MCP transport: stdio or http"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host for http transport"),
    port: int = typer.Option(8321, "--port", help="Bind port for http transport"),
) -> None:
    """Run the Timing MCP server so agents (e.g. Hermes) can query it."""
    from timing_cli.serve import run_server

    try:
        run_server(transport=transport, host=host, port=port)
    except ValueError as exc:
        _exit_with_error(str(exc))


if __name__ == "__main__":
    app()
