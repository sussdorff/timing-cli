"""Aggregate raw app usage into project time blocks and daily summaries."""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from timing_cli.models import (
    MAX_RECONSTRUCTION_PAGE_SIZE,
    MAX_RECORD_REFERENCES,
    AppUsage,
    AssignmentExplanation,
    EvidenceInterval,
    ProjectSummary,
    ReconstructionEvidence,
    ReconstructionMetrics,
    ReconstructionPagination,
    ReconstructionRecord,
    ReconstructionResponse,
    ReconstructionSource,
    ReconstructionWindow,
    TimeEntrySuggestion,
)
from timing_cli.rules import UNASSIGNED, Classification, Classifier, assignments_equivalent


def _local_day(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _next_local_midnight(dt: datetime) -> datetime:
    next_day = dt.astimezone().date() + timedelta(days=1)
    return _local_midnight(next_day)


def _local_midnight(day: date) -> datetime:
    # Build local wall-clock midnight through the platform timezone database so
    # DST offset changes between ``dt`` and the next day are applied correctly.
    naive_midnight = datetime.combine(day, time.min)
    return datetime.fromtimestamp(naive_midnight.timestamp()).astimezone()


def local_day_window(day: date) -> tuple[datetime, datetime]:
    """Return timezone-rule-aware local midnights bounding a calendar day."""
    return _local_midnight(day), _local_midnight(day + timedelta(days=1))


def resolve_reconstruction_query_window(
    month: str | None,
    start: str | None,
    end: str | None,
) -> tuple[datetime, datetime]:
    """Resolve either a local YYYY-MM month or an explicit half-open window."""
    if month:
        if start or end:
            raise ValueError("use --month or explicit --from/--to, not both")
        try:
            first_day = date.fromisoformat(f"{month}-01")
        except ValueError as exc:
            raise ValueError("month must use YYYY-MM") from exc
        if first_day.strftime("%Y-%m") != month:
            raise ValueError("month must use YYYY-MM")
        next_month = (
            date(first_day.year + 1, 1, 1)
            if first_day.month == 12
            else date(first_day.year, first_day.month + 1, 1)
        )
        return _local_midnight(first_day), _local_midnight(next_month)

    if not start or not end:
        raise ValueError("provide --month or both --from and --to")
    try:
        resolved_start = datetime.fromisoformat(start).astimezone()
        resolved_end = datetime.fromisoformat(end).astimezone()
    except ValueError as exc:
        raise ValueError("explicit windows must use ISO-8601 datetimes") from exc
    if resolved_end <= resolved_start:
        raise ValueError("reconstruction window end must be after start")
    return resolved_start, resolved_end


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


def _source_reference(source: ReconstructionSource) -> str:
    return f"{source.source_type}:{source.source_id}"


def _source_as_usage(source: ReconstructionSource) -> AppUsage:
    return AppUsage(
        id=source.source_id,
        start=source.start,
        end=source.end,
        application_id=source.application_id,
        app=source.app or "",
        bundle_id=source.bundle_id,
        title=source.title,
        path=source.path,
        project_id=source.project_id,
        project_title=source.project_title,
        project_title_chain=source.project_title_chain,
        project_title_chain_complete=source.project_title_chain_complete,
    )


def _overlap(left: ReconstructionSource, right: ReconstructionSource) -> bool:
    return left.start < right.end and right.start < left.end


@dataclass
class _RecordAnalysisState:
    source: ReconstructionSource
    assignment: AssignmentExplanation
    supporting: list[str] = field(default_factory=list)
    supporting_complete: bool = True
    covered_by: list[str] = field(default_factory=list)
    covered_by_complete: bool = True
    conflicts: list[str] = field(default_factory=list)
    conflicts_complete: bool = True
    candidates: list[EvidenceInterval] = field(default_factory=list)
    candidates_complete: bool = True
    candidate_cursor: datetime | None = None

    def add_reference(self, collection: list[str], reference: str, complete_field: str) -> None:
        if reference in collection:
            return
        if len(collection) < MAX_RECORD_REFERENCES:
            collection.append(reference)
        else:
            setattr(self, complete_field, False)

    def add_candidate(self, start: datetime, end: datetime) -> None:
        if end <= start:
            return
        if len(self.candidates) < MAX_RECORD_REFERENCES:
            self.candidates.append(EvidenceInterval(start=start, end=end))
        else:
            self.candidates_complete = False

    def cover_with(self, booking: ReconstructionSource) -> None:
        if self.source.source_type != "activity":
            return
        overlap_start = max(self.source.start, booking.start)
        overlap_end = min(self.source.end, booking.end)
        if overlap_end <= overlap_start:
            return
        cursor = self.candidate_cursor or self.source.start
        if overlap_start > cursor:
            self.add_candidate(cursor, overlap_start)
        self.candidate_cursor = max(cursor, overlap_end)

    def finish_candidates(self) -> None:
        if self.source.source_type != "activity":
            return
        cursor = self.candidate_cursor or self.source.start
        self.add_candidate(cursor, self.source.end)


@dataclass
class _MetricAccumulator:
    last_ts: float | None = None
    activity_end_ts: float = float("-inf")
    booking_end_ts: float = float("-inf")
    first_evidence_ts: float | None = None
    last_evidence_ts: float | None = None
    raw_activity_seconds: float = 0.0
    activity_union_seconds: float = 0.0
    evidence_union_seconds: float = 0.0
    recorded_service_seconds: float = 0.0
    uncovered_candidate_seconds: float = 0.0

    def _advance(self, target_ts: float) -> None:
        if self.last_ts is None:
            self.last_ts = target_ts
            return
        while self.last_ts < target_ts:
            boundaries = [target_ts]
            if self.last_ts < self.activity_end_ts < target_ts:
                boundaries.append(self.activity_end_ts)
            if self.last_ts < self.booking_end_ts < target_ts:
                boundaries.append(self.booking_end_ts)
            boundary = min(boundaries)
            seconds = boundary - self.last_ts
            activity_active = self.activity_end_ts > self.last_ts
            booking_active = self.booking_end_ts > self.last_ts
            if activity_active:
                self.activity_union_seconds += seconds
            if booking_active:
                self.recorded_service_seconds += seconds
            if activity_active or booking_active:
                self.evidence_union_seconds += seconds
            if activity_active and not booking_active:
                self.uncovered_candidate_seconds += seconds
            self.last_ts = boundary

    def add(self, source: ReconstructionSource) -> None:
        start_ts = source.start.timestamp()
        end_ts = source.end.timestamp()
        if end_ts <= start_ts:
            return
        self._advance(start_ts)
        self.first_evidence_ts = (
            start_ts if self.first_evidence_ts is None else min(self.first_evidence_ts, start_ts)
        )
        self.last_evidence_ts = (
            end_ts if self.last_evidence_ts is None else max(self.last_evidence_ts, end_ts)
        )
        if source.source_type == "activity":
            self.raw_activity_seconds += end_ts - start_ts
            self.activity_end_ts = max(self.activity_end_ts, end_ts)
        else:
            self.booking_end_ts = max(self.booking_end_ts, end_ts)

    def finish(self) -> ReconstructionMetrics:
        final_ts = max(self.activity_end_ts, self.booking_end_ts)
        if final_ts != float("-inf"):
            self._advance(final_ts)
        elapsed = 0.0
        if self.first_evidence_ts is not None and self.last_evidence_ts is not None:
            elapsed = self.last_evidence_ts - self.first_evidence_ts
        return ReconstructionMetrics(
            raw_cumulative_activity_seconds=self.raw_activity_seconds,
            activity_interval_union_seconds=self.activity_union_seconds,
            elapsed_evidence_span_seconds=elapsed,
            gap_seconds=max(0.0, elapsed - self.evidence_union_seconds),
            recorded_service_seconds=self.recorded_service_seconds,
            uncovered_candidate_seconds=self.uncovered_candidate_seconds,
        )


def reconstruct_evidence(
    page_sources: list[ReconstructionSource],
    all_sources: Iterable[ReconstructionSource],
    classifier: Classifier,
) -> ReconstructionEvidence:
    """Analyze one bounded page against a bounded-batch stream for the full window."""
    if len(page_sources) > MAX_RECONSTRUCTION_PAGE_SIZE:
        raise ValueError(f"page sources exceed cap of {MAX_RECONSTRUCTION_PAGE_SIZE}")

    states: dict[str, _RecordAnalysisState] = {}
    for source in page_sources:
        reference = _source_reference(source)
        states[reference] = _RecordAnalysisState(
            source=source,
            assignment=classifier.explain(
                _source_as_usage(source),
                source_reference=reference,
            ),
        )

    metrics = _MetricAccumulator()
    for other in all_sources:
        metrics.add(other)
        other_reference = _source_reference(other)
        other_assignment = classifier.explain(
            _source_as_usage(other),
            source_reference=other_reference,
        )
        other_selected = other_assignment.selected_assignment
        for reference, state in states.items():
            if reference == other_reference or not _overlap(state.source, other):
                continue
            if state.source.source_type == "booking" and other.source_type == "activity":
                state.add_reference(
                    state.supporting,
                    other_reference,
                    "supporting_complete",
                )
            elif state.source.source_type == "activity" and other.source_type == "booking":
                state.add_reference(
                    state.covered_by,
                    other_reference,
                    "covered_by_complete",
                )
                state.cover_with(other)

            state_selected = state.assignment.selected_assignment
            if (
                state_selected is not None
                and other_selected is not None
                and not assignments_equivalent(state_selected, other_selected)
            ):
                state.add_reference(
                    state.conflicts,
                    other_reference,
                    "conflicts_complete",
                )

    records: list[ReconstructionRecord] = []
    for source in page_sources:
        state = states[_source_reference(source)]
        state.finish_candidates()
        records.append(
            ReconstructionRecord(
                source=state.source,
                assignment=state.assignment,
                supporting_activity_references=state.supporting,
                supporting_activity_references_complete=state.supporting_complete,
                covered_by_booking_references=state.covered_by,
                covered_by_booking_references_complete=state.covered_by_complete,
                conflict_references=state.conflicts,
                conflict_references_complete=state.conflicts_complete,
                candidate_intervals=state.candidates,
                candidate_intervals_complete=state.candidates_complete,
            )
        )
    return ReconstructionEvidence(records=records, metrics=metrics.finish())


def reconstruct_window(
    conn: sqlite3.Connection,
    start: datetime,
    end: datetime,
    classifier: Classifier,
    *,
    limit: int,
    cursor: str | None = None,
    extracted_at: datetime | None = None,
    timezone_name: str | None = None,
) -> ReconstructionResponse:
    """Build one versioned response page with whole-window metrics."""
    if start.utcoffset() is None or end.utcoffset() is None:
        raise ValueError("reconstruction windows must be timezone-aware")
    if end <= start:
        raise ValueError("reconstruction window end must be after start")

    from timing_cli.db import (
        iter_reconstruction_sources,
        list_reconstruction_sources,
        reconstruction_read_transaction,
        reconstruction_snapshot,
    )

    with reconstruction_read_transaction(conn):
        snapshot = reconstruction_snapshot(conn, start, end)
        page = list_reconstruction_sources(
            conn,
            start,
            end,
            limit=limit,
            cursor=cursor,
            snapshot=snapshot,
        )
        evidence = reconstruct_evidence(
            page.records,
            iter_reconstruction_sources(conn, start, end, snapshot=snapshot),
            classifier,
        )
    return ReconstructionResponse(
        window=ReconstructionWindow(
            timezone=timezone_name or str(start.tzinfo),
            start=start,
            end=end,
            extracted_at=extracted_at or datetime.now(UTC),
        ),
        pagination=ReconstructionPagination(
            limit=limit,
            total_count=page.total_count,
            returned_count=page.returned_count,
            complete=page.complete,
            next_cursor=page.next_cursor,
        ),
        metrics=evidence.metrics,
        records=evidence.records,
    )
