"""Typer CLI for timing-cli."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import rich.traceback
import typer

from timing_cli import __version__, output
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
from timing_cli.output import render_suggestions, render_summary, render_usage
from timing_cli.rules import UNASSIGNED, Classifier

rich.traceback.install(show_locals=False)

app = typer.Typer(
    name="timing",
    help="Read the local Timing.app database and generate/push time entries.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        output.console.print(f"timing-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit"
    ),
    no_color: bool = typer.Option(
        False, "--no-color", is_eager=True, help="Disable ANSI color codes"
    ),
) -> None:
    """timing-cli - local Timing.app activity to Timing time entries."""
    output.configure_output(no_color=no_color)


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
    output.err_console.print(f"[red]{message}[/red]")
    raise typer.Exit(1)


DateOpt = typer.Option(None, "--date", "-d", help="Local day YYYY-MM-DD (default: today)")
FromOpt = typer.Option(None, "--from", "-f", help="Start datetime (ISO 8601), overrides --date")
ToOpt = typer.Option(None, "--to", "-t", help="End datetime (ISO 8601), overrides --date")


@app.command()
def info(
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """Show the database location and the recorded activity date range."""
    cfg = _load()
    try:
        with open_db(cfg.db_path) as conn:
            rng = date_range(conn)
            projects = list_projects(conn, include_archived=False)
    except TimingDatabaseError as exc:
        _exit_with_error(str(exc))
    if json_output:
        output.print_json(
            {
                "active_projects": len(projects),
                "api_token_set": bool(cfg.resolved_token()),
                "database": str(cfg.db_path),
                "recorded_end": rng[1].isoformat() if rng else None,
                "recorded_start": rng[0].isoformat() if rng else None,
            }
        )
        return
    output.console.print(f"Database: [cyan]{cfg.db_path}[/cyan]")
    if rng:
        output.console.print(
            f"Recorded: [green]{rng[0]:%Y-%m-%d}[/green] -> "
            f"[green]{rng[1]:%Y-%m-%d}[/green]"
        )
    output.console.print(f"Active projects: {len(projects)}")
    output.console.print(
        f"API token: {'set' if cfg.resolved_token() else '[yellow]not set[/yellow]'}"
    )


@app.command()
def projects(
    remote: bool = typer.Option(False, "--remote", help="List projects from the Web API instead"),
    archived: bool = typer.Option(False, "--archived", help="Include archived projects"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """List projects (local database by default, or the Web API with --remote)."""
    cfg = _load()
    if remote:
        try:
            with TimingApiClient(cfg.api_base_url, cfg.resolved_token()) as client:
                projects = client.list_projects(hide_archived=not archived)
                if json_output:
                    output.print_json(projects)
                    return
                for p in projects:
                    chain = " / ".join(p.get("title_chain") or [p.get("title", "")])
                    output.console.print(f"[magenta]{p.get('self')}[/magenta]  {chain}")
        except TimingApiError as exc:
            output.err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        return
    try:
        with open_db(cfg.db_path) as conn:
            projects = list_projects(conn, include_archived=archived)
    except TimingDatabaseError as exc:
        _exit_with_error(str(exc))
    if json_output:
        output.print_json([project.model_dump(mode="json") for project in projects])
        return
    for project in projects:
        marker = " [dim](archived)[/dim]" if project.is_archived else ""
        output.console.print(f"[magenta]{project.id}[/magenta]  {project.title}{marker}")


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
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """Show raw automatically tracked app usage for a window."""
    cfg = _load()
    start, end = _resolve_window(date_opt, from_opt, to_opt)
    try:
        with open_db(cfg.db_path) as conn:
            slices = list_app_usage(conn, start, end, project_id=project_id)
    except TimingDatabaseError as exc:
        _exit_with_error(str(exc))
    render_usage(slices, json_output=json_output)


@app.command()
def summary(
    date_opt: str | None = DateOpt,
    from_opt: str | None = FromOpt,
    to_opt: str | None = ToOpt,
    include_unassigned: bool = typer.Option(
        True, "--unassigned/--no-unassigned", help="Include time not mapped to any project"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
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
    render_summary(
        summaries,
        title=f"Project summary {start:%Y-%m-%d} .. {end:%Y-%m-%d}",
        json_output=json_output,
    )


@app.command()
def suggest(
    date_opt: str | None = DateOpt,
    from_opt: str | None = FromOpt,
    to_opt: str | None = ToOpt,
    include_unassigned: bool = typer.Option(
        False, "--unassigned/--no-unassigned", help="Also suggest entries for unassigned time"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
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
    render_suggestions(suggestions, json_output=json_output)


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
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
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
    if not json_output:
        render_suggestions(suggestions)

    if not suggestions:
        if json_output:
            output.print_json(
                {"created": 0, "dry_run": not yes, "skipped": 0, "suggestions": []}
            )
        else:
            output.console.print("[yellow]Nothing to push.[/yellow]")
        return
    if not yes:
        if json_output:
            output.print_json(
                {
                    "created": 0,
                    "dry_run": True,
                    "skipped": 0,
                    "suggestions": [
                        suggestion.model_dump(mode="json") for suggestion in suggestions
                    ],
                }
            )
        else:
            output.console.print(
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
            if json_output:
                output.print_json(
                    {
                        "created": created,
                        "dry_run": False,
                        "skipped": skipped,
                        "suggestions": [
                            suggestion.model_dump(mode="json") for suggestion in suggestions
                        ],
                    }
                )
            else:
                output.console.print(f"[green]{message}[/green]")
    except TimingApiError as exc:
        output.err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


@app.command()
def serve(
    install: bool = typer.Option(
        False, "--install", help="Install LaunchAgent for GUI-session auto-start"
    ),
    uninstall: bool = typer.Option(
        False, "--uninstall", help="Remove LaunchAgent and stop background server"
    ),
    transport: str = typer.Option("stdio", "--transport", help="MCP transport: stdio or http"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host for http transport"),
    port: int = typer.Option(8321, "--port", help="Bind port for http transport"),
) -> None:
    """Run the Timing MCP server so agents (e.g. Hermes) can query it."""
    from timing_cli.serve import install_launch_agent, run_server, uninstall_launch_agent

    if install and uninstall:
        _exit_with_error("Use either --install or --uninstall, not both.")

    if uninstall:
        uninstall_launch_agent()
        output.console.print("[green]timing serve LaunchAgent removed.[/green]")
        return

    if install:
        try:
            path = install_launch_agent(host=host, port=port)
        except ValueError as exc:
            _exit_with_error(str(exc))
            return
        output.console.print(f"[green]timing serve LaunchAgent installed: {path}[/green]")
        return

    try:
        run_server(transport=transport, host=host, port=port)
    except ValueError as exc:
        _exit_with_error(str(exc))


if __name__ == "__main__":
    app()
