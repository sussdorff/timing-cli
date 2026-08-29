"""Rich-based rendering helpers for the CLI."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from timing_cli.models import AppUsage, ProjectSummary, TimeEntrySuggestion

console = Console()
err_console = Console(stderr=True)


def _fmt_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def render_usage(usage: list[AppUsage], *, show_path: bool = False) -> None:
    table = Table(title="App usage", show_lines=False)
    table.add_column("Start", style="cyan", no_wrap=True)
    table.add_column("Dur", justify="right")
    table.add_column("App", style="green")
    table.add_column("Title")
    if show_path:
        table.add_column("Path", overflow="fold")
    table.add_column("Project", style="magenta")
    for u in usage:
        row = [
            u.start.strftime("%H:%M:%S"),
            _fmt_duration(u.duration_seconds),
            u.app,
            (u.title or "")[:50],
        ]
        if show_path:
            row.append(u.path or "")
        row.append(u.project_title or "")
        table.add_row(*row)
    console.print(table)


def render_summary(summaries: list[ProjectSummary], title: str = "Project summary") -> None:
    table = Table(title=title)
    table.add_column("Project", style="magenta")
    table.add_column("Time", justify="right")
    table.add_column("Slices", justify="right", style="dim")
    total = 0.0
    for s in summaries:
        table.add_row(s.project_title, _fmt_duration(s.seconds), str(s.entries))
        total += s.seconds
    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{_fmt_duration(total)}[/bold]", "")
    console.print(table)


def render_suggestions(suggestions: list[TimeEntrySuggestion]) -> None:
    table = Table(title="Suggested time entries")
    table.add_column("Day", style="cyan", no_wrap=True)
    table.add_column("Start", no_wrap=True)
    table.add_column("End", no_wrap=True)
    table.add_column("Dur", justify="right")
    table.add_column("Project", style="magenta")
    table.add_column("Title")
    total = 0.0
    for s in suggestions:
        table.add_row(
            s.day,
            s.start.strftime("%H:%M"),
            s.end.strftime("%H:%M"),
            _fmt_duration(s.duration_seconds),
            s.project_title,
            (s.title or "")[:50],
        )
        total += s.duration_seconds
    table.add_section()
    table.add_row("", "", "", f"[bold]{_fmt_duration(total)}[/bold]", "", "")
    console.print(table)
