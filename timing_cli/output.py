"""Rich-based rendering helpers for the CLI."""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console
from rich.table import Table

from timing_cli.models import (
    AppUsage,
    ProjectSummary,
    ReconstructionResponse,
    TimeEntrySuggestion,
)


def _make_consoles(*, no_color: bool) -> tuple[Console, Console]:
    if no_color:
        return (
            Console(highlight=False, no_color=True),
            Console(stderr=True, highlight=False, no_color=True),
        )
    return Console(), Console(stderr=True)


_no_color = not sys.stdout.isatty()
console, err_console = _make_consoles(no_color=_no_color)


def configure_output(no_color: bool = False) -> None:
    """Reconfigure output consoles for no-color mode."""
    global console, err_console
    disable_color = no_color or not sys.stdout.isatty()
    console, err_console = _make_consoles(no_color=disable_color)


def _fmt_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _print_models(models: list[AppUsage | ProjectSummary | TimeEntrySuggestion]) -> None:
    payload = [model.model_dump(mode="json") for model in models]
    print_json(payload)


def print_json(payload: Any) -> None:
    """Emit stable machine-readable JSON without passing through Rich."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def render_usage(usage: list[AppUsage], *, json_output: bool = False) -> None:
    if json_output:
        _print_models(usage)
        return
    table = Table(title="App usage", show_lines=False)
    table.add_column("Start", style="cyan", no_wrap=True)
    table.add_column("Dur", justify="right")
    table.add_column("App", style="green")
    table.add_column("Title")
    table.add_column("Project", style="magenta")
    for u in usage:
        table.add_row(
            u.start.strftime("%H:%M:%S"),
            _fmt_duration(u.duration_seconds),
            u.app,
            (u.title or "")[:50],
            u.project_title or "",
        )
    console.print(table)


def render_summary(
    summaries: list[ProjectSummary],
    title: str = "Project summary",
    *,
    json_output: bool = False,
) -> None:
    if json_output:
        _print_models(summaries)
        return
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


def render_suggestions(
    suggestions: list[TimeEntrySuggestion], *, json_output: bool = False
) -> None:
    if json_output:
        _print_models(suggestions)
        return
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


def render_reconstruction(response: ReconstructionResponse) -> None:
    """Render one bounded reconstruction page for a human reader."""
    metrics = response.metrics
    metric_table = Table(title=f"Reconstruction ({response.schema_version})")
    metric_table.add_column("Window metric")
    metric_table.add_column("Seconds", justify="right")
    metric_table.add_row(
        "Raw cumulative activity", f"{metrics.raw_cumulative_activity_seconds:.3f}"
    )
    metric_table.add_row(
        "Activity interval union", f"{metrics.activity_interval_union_seconds:.3f}"
    )
    metric_table.add_row("Elapsed evidence span", f"{metrics.elapsed_evidence_span_seconds:.3f}")
    metric_table.add_row("Evidence gaps", f"{metrics.gap_seconds:.3f}")
    metric_table.add_row("Recorded service", f"{metrics.recorded_service_seconds:.3f}")
    metric_table.add_row("Uncovered candidates", f"{metrics.uncovered_candidate_seconds:.3f}")
    console.print(metric_table)

    records = Table(title="Reconstruction source records")
    records.add_column("Source", no_wrap=True)
    records.add_column("Start", no_wrap=True)
    records.add_column("End", no_wrap=True)
    records.add_column("Existing project")
    records.add_column("Selected project")
    records.add_column("Title")
    records.add_column("Path")
    for record in response.records:
        source = record.source
        existing = record.assignment.existing_assignment
        selected = record.assignment.selected_assignment
        records.add_row(
            f"{source.source_type}:{source.source_id}",
            source.start.isoformat(),
            source.end.isoformat(),
            existing.project_title if existing else "",
            selected.project_title if selected else "Unresolved",
            source.title or "",
            source.path or "",
        )
    console.print(records)
    pagination = response.pagination
    console.print(
        f"Returned {pagination.returned_count} of {pagination.total_count}. "
        f"Complete: {'yes' if pagination.complete else 'no'}."
    )
    if pagination.next_cursor:
        console.print(f"Next cursor: {pagination.next_cursor}")
