"""Aggregate raw app usage into project time blocks and daily summaries."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, time, timedelta

from timing_cli.models import AppUsage, ProjectSummary, TimeEntrySuggestion
from timing_cli.rules import UNASSIGNED, Classification, Classifier


def _local_day(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _next_local_midnight(dt: datetime) -> datetime:
    return datetime.combine(dt.date() + timedelta(days=1), time.min, tzinfo=dt.tzinfo)


def _split_at_local_midnight(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    pieces: list[tuple[datetime, datetime]] = []
    current = start
    while current < end:
        next_midnight = _next_local_midnight(current)
        piece_end = min(end, next_midnight)
        pieces.append((current, piece_end))
        current = piece_end
    return pieces


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
        day=_local_day(start),
        start=start,
        end=end,
        project_id=classification.project_id,
        project_title=classification.project_title,
        project_title_chain=list(
            classification.project_title_chain or (classification.project_title,)
        ),
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
    """Merge chronological same-project slices into time-entry suggestions.

    Blocks are built in wall-clock order and never cross local-day boundaries.
    Same-project slices are merged when no other included project appears
    between them and the wall-clock gap does not exceed ``gap_merge_seconds``.
    Skipped unassigned slices behave like idle gaps; different included projects
    always break the current block. Overlapping included slices are clipped to
    the already-consumed cursor so suggestions cannot overlap.
    """
    suggestions: list[TimeEntrySuggestion] = []
    block_start: datetime | None = None
    block_end: datetime | None = None
    block_class: Classification | None = None
    apps: Counter[str] = Counter()
    cursor: datetime | None = None

    def flush() -> None:
        nonlocal block_start, block_end, block_class, apps
        if block_start is None or block_end is None or block_class is None:
            return
        if (block_end - block_start).total_seconds() >= min_block_seconds:
            suggestions.append(_build_entry(block_class, block_start, block_end, apps))
        block_start = block_end = block_class = None
        apps = Counter()

    def start_block(
        classification: Classification,
        start: datetime,
        end: datetime,
        app: str,
    ) -> None:
        nonlocal block_start, block_end, block_class, apps
        block_start = start
        block_end = end
        block_class = classification
        apps = Counter({app: 1})

    for slice_ in sorted(usage, key=lambda u: (u.start, u.end, u.id)):
        if slice_.end <= slice_.start:
            continue

        c = classifier.classify(slice_)
        if not include_unassigned and c.project_title == UNASSIGNED:
            continue

        for segment_start, segment_end in _split_at_local_midnight(slice_.start, slice_.end):
            if cursor is not None and segment_start < cursor:
                segment_start = cursor
            if segment_end <= segment_start:
                continue
            cursor = segment_end

            if block_class is None or block_end is None or block_start is None:
                start_block(c, segment_start, segment_end, slice_.app)
                continue

            same_project = (block_class.project_id, block_class.project_title) == (
                c.project_id,
                c.project_title,
            )
            same_day = _local_day(block_start) == _local_day(segment_start)
            gap_seconds = (segment_start - block_end).total_seconds()
            if not same_project or not same_day or gap_seconds > gap_merge_seconds:
                flush()
                start_block(c, segment_start, segment_end, slice_.app)
                continue

            block_end = max(block_end, segment_end)
            apps[slice_.app] += 1

    flush()

    suggestions.sort(key=lambda s: s.start)
    return suggestions
