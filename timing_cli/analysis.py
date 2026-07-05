"""Aggregate raw app usage into project time blocks and daily summaries."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from timing_cli.models import AppUsage, ProjectSummary, TimeEntrySuggestion
from timing_cli.rules import UNASSIGNED, Classification, Classifier


def _local_day(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def summarize_by_project(
    usage: list[AppUsage],
    classifier: Classifier,
    include_unassigned: bool = True,
) -> list[ProjectSummary]:
    """Total tracked seconds per project across the given usage."""
    totals: dict[tuple[int | None, str], ProjectSummary] = {}
    for slice_ in usage:
        c = classifier.classify(slice_)
        if not include_unassigned and c.project_title == UNASSIGNED:
            continue
        key = (c.project_id, c.project_title)
        summary = totals.get(key)
        if summary is None:
            summary = ProjectSummary(project_id=c.project_id, project_title=c.project_title)
            totals[key] = summary
        summary.seconds += slice_.duration_seconds
        summary.entries += 1
    return sorted(totals.values(), key=lambda s: s.seconds, reverse=True)


def _build_entry(
    day: str,
    classification: Classification,
    start: datetime,
    end: datetime,
    app_counter: Counter[str],
) -> TimeEntrySuggestion:
    top = [app for app, _ in app_counter.most_common(3)]
    title = classification.project_title
    if top:
        title = f"{classification.project_title}: {', '.join(top)}"
    notes = "Auto-generated from Timing app usage. Top apps: " + ", ".join(
        f"{app} ({count})" for app, count in app_counter.most_common(5)
    )
    return TimeEntrySuggestion(
        day=day,
        start=start,
        end=end,
        project_id=classification.project_id,
        project_title=classification.project_title,
        title=title,
        notes=notes,
        source_count=sum(app_counter.values()),
        top_apps=top,
    )


def aggregate(
    usage: list[AppUsage],
    classifier: Classifier,
    min_block_seconds: int = 120,
    gap_merge_seconds: int = 300,
    include_unassigned: bool = False,
) -> list[TimeEntrySuggestion]:
    """Merge consecutive same-project slices into time-entry suggestions.

    Slices are grouped per (local day, project). Within a group, slices are
    merged into a block as long as the gap between one slice's end and the next
    slice's start does not exceed ``gap_merge_seconds``. Blocks shorter than
    ``min_block_seconds`` are dropped as noise.
    """
    # Group by (day, project) preserving chronological order.
    groups: dict[tuple[str, int | None, str], list[tuple[AppUsage, Classification]]] = defaultdict(
        list
    )
    for slice_ in sorted(usage, key=lambda u: u.start):
        c = classifier.classify(slice_)
        if not include_unassigned and c.project_title == UNASSIGNED:
            continue
        groups[(_local_day(slice_.start), c.project_id, c.project_title)].append((slice_, c))

    suggestions: list[TimeEntrySuggestion] = []
    for (day, _pid, _ptitle), items in groups.items():
        block_start: datetime | None = None
        block_end: datetime | None = None
        block_class: Classification | None = None
        apps: Counter[str] = Counter()

        def flush() -> None:
            nonlocal block_start, block_end, block_class, apps
            if block_start is None or block_end is None or block_class is None:
                return
            if (block_end - block_start).total_seconds() >= min_block_seconds:
                suggestions.append(
                    _build_entry(day, block_class, block_start, block_end, apps)
                )
            block_start = block_end = block_class = None
            apps = Counter()

        for slice_, c in items:
            if block_end is not None and (slice_.start - block_end).total_seconds() > gap_merge_seconds:
                flush()
            if block_start is None:
                block_start = slice_.start
                block_class = c
            block_end = max(block_end, slice_.end) if block_end else slice_.end
            apps[slice_.app] += 1
        flush()

    suggestions.sort(key=lambda s: s.start)
    return suggestions
