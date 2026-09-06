"""Tests for the aggregation and classification logic (no database needed)."""

from __future__ import annotations

import os
import time as time_module
from datetime import datetime, timedelta, timezone

from timing_cli.analysis import aggregate, summarize_by_project
from timing_cli.config import Rule
from timing_cli.models import AppUsage, ReconstructionSource
from timing_cli.rules import UNASSIGNED, Classifier

BASE = datetime(2026, 7, 5, 9, 0, 0).astimezone()


def _slice(offset_min: float, dur_min: float, app: str, title: str = "", project=None) -> AppUsage:
    start = BASE + timedelta(minutes=offset_min)
    pid, ptitle = project if project else (None, None)
    return AppUsage(
        id=int(offset_min * 100),
        start=start,
        end=start + timedelta(minutes=dur_min),
        app=app,
        title=title,
        project_id=pid,
        project_title=ptitle,
    )


def test_timing_assignment_is_preferred():
    classifier = Classifier([])
    slices = [_slice(0, 5, "Xcode", project=(7, "Cognovis"))]
    summary = summarize_by_project(slices, classifier)
    assert summary[0].project_title == "Cognovis"
    assert summary[0].project_id == 7


def test_rule_matches_by_title_regex():
    classifier = Classifier([Rule(project="Polaris", title=r"polaris")])
    c = classifier.classify(_slice(0, 5, "cmux", title="~/code/polaris"))
    assert c.project_title == "Polaris"
    assert c.source == "rule"


def test_unmatched_is_unassigned():
    classifier = Classifier([Rule(project="Polaris", title=r"polaris")])
    c = classifier.classify(_slice(0, 5, "Safari", title="News"))
    assert c.project_title == UNASSIGNED


def test_aggregate_merges_within_gap_and_drops_short_blocks():
    classifier = Classifier([Rule(project="Work", app="Xcode")])
    slices = [
        _slice(0, 4, "Xcode"),       # 09:00-09:04
        _slice(5, 4, "Xcode"),       # 09:05-09:09  (1 min gap -> merged)
        _slice(60, 1, "Xcode"),      # 10:00-10:01  (short, isolated -> dropped)
    ]
    entries = aggregate(slices, classifier, min_block_seconds=120, gap_merge_seconds=300)
    assert len(entries) == 1
    e = entries[0]
    assert e.project_title == "Work"
    assert e.start == BASE
    assert (e.end - e.start).total_seconds() == 9 * 60


def test_aggregate_splits_on_large_gap():
    classifier = Classifier([Rule(project="Work", app="Xcode")])
    slices = [
        _slice(0, 10, "Xcode"),      # 09:00-09:10
        _slice(30, 10, "Xcode"),     # 09:30-09:40  (20 min gap -> split)
    ]
    entries = aggregate(slices, classifier, min_block_seconds=120, gap_merge_seconds=300)
    assert len(entries) == 2


def test_aggregate_does_not_overlap_interleaved_projects():
    classifier = Classifier([])
    slices = [
        _slice(0, 10, "Xcode", project=(1, "X")),
        _slice(10, 3, "Safari", project=(2, "Y")),
        _slice(13, 10, "Xcode", project=(1, "X")),
    ]

    entries = aggregate(
        slices,
        classifier,
        min_block_seconds=0,
        gap_merge_seconds=300,
        include_unassigned=True,
    )

    assert [(e.project_title, e.start, e.end) for e in entries] == [
        ("X", BASE, BASE + timedelta(minutes=10)),
        ("Y", BASE + timedelta(minutes=10), BASE + timedelta(minutes=13)),
        ("X", BASE + timedelta(minutes=13), BASE + timedelta(minutes=23)),
    ]
    assert sum(e.duration_seconds for e in entries) == 23 * 60


def test_long_skipped_unassigned_gap_breaks_aggregation():
    classifier = Classifier([Rule(project="Work", app="Xcode")])
    slices = [
        _slice(0, 10, "Xcode"),
        _slice(10, 10, "Safari"),
        _slice(20, 8, "Xcode"),
    ]

    entries = aggregate(slices, classifier, min_block_seconds=0, gap_merge_seconds=300)

    assert len(entries) == 2
    assert entries[0].start == BASE
    assert entries[0].end == BASE + timedelta(minutes=10)
    assert entries[1].start == BASE + timedelta(minutes=20)
    assert entries[1].end == BASE + timedelta(minutes=28)


def test_aggregate_splits_blocks_at_local_midnight():
    classifier = Classifier([])
    start = datetime(2026, 7, 5, 23, 50, 0).astimezone()
    midnight = datetime(2026, 7, 6, 0, 0, 0).astimezone()
    end = datetime(2026, 7, 6, 0, 20, 0).astimezone()
    slices = [
        AppUsage(
            id=1,
            start=start,
            end=end,
            app="Xcode",
            project_id=1,
            project_title="Work",
        )
    ]

    entries = aggregate(
        slices,
        classifier,
        min_block_seconds=0,
        gap_merge_seconds=300,
    )

    assert [(entry.day, entry.start, entry.end) for entry in entries] == [
        ("2026-07-05", start, midnight),
        ("2026-07-06", midnight, end),
    ]


def test_regression_aggregate_splits_at_local_midnight_across_dst_change(monkeypatch):
    old_tz = os.environ.get("TZ")
    monkeypatch.setenv("TZ", "Europe/Berlin")
    if hasattr(time_module, "tzset"):
        time_module.tzset()

    try:
        classifier = Classifier([])
        start = datetime(2026, 3, 29, 1, 30, tzinfo=timezone(timedelta(hours=1)))
        midnight = datetime(2026, 3, 30, 0, 0).astimezone()
        end = datetime(2026, 3, 30, 0, 30, tzinfo=timezone(timedelta(hours=2)))
        slices = [
            AppUsage(
                id=1,
                start=start,
                end=end,
                app="Xcode",
                project_id=1,
                project_title="Work",
            )
        ]

        entries = aggregate(
            slices,
            classifier,
            min_block_seconds=0,
            gap_merge_seconds=300,
        )

        assert [(entry.day, entry.start, entry.end) for entry in entries] == [
            ("2026-03-29", start, midnight),
            ("2026-03-30", midnight, end),
        ]
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        if hasattr(time_module, "tzset"):
            time_module.tzset()


def test_skipped_overlapping_unassigned_slice_does_not_clip_assigned_time():
    classifier = Classifier([])
    assigned_start = BASE + timedelta(minutes=60)
    assigned_end = BASE + timedelta(minutes=90)
    slices = [
        AppUsage(
            id=1,
            start=BASE,
            end=BASE + timedelta(minutes=120),
            app="Safari",
        ),
        AppUsage(
            id=2,
            start=assigned_start,
            end=assigned_end,
            app="Xcode",
            project_id=1,
            project_title="Work",
        ),
    ]

    entries = aggregate(
        slices,
        classifier,
        min_block_seconds=0,
        gap_merge_seconds=300,
    )

    assert len(entries) == 1
    assert entries[0].start == assigned_start
    assert entries[0].end == assigned_end


def test_assignment_explanation_keeps_existing_and_all_matching_alternatives():
    local_id = 2**54 + 77
    usage = AppUsage(
        id=local_id,
        start=BASE,
        end=BASE + timedelta(minutes=10),
        app="Synthetic Editor",
        title="Synthetic alpha review",
        project_id=91,
        project_title="Synthetic Existing",
        project_title_chain=["Synthetic Group", "Synthetic Existing"],
    )
    classifier = Classifier(
        [
            Rule(project="Synthetic Alpha", title="alpha"),
            Rule(project="Synthetic Review", title="review"),
        ],
        user_rule_count=1,
    )

    classification = classifier.classify(usage)
    explanation = classifier.explain(usage, source_reference=f"activity:{local_id}")

    assert classification.project_title == "Synthetic Existing"
    assert explanation.origin == "existing"
    assert explanation.existing_assignment.project_title == "Synthetic Existing"
    assert explanation.selected_assignment == explanation.existing_assignment
    assert [alternative.project_title for alternative in explanation.alternatives] == [
        "Synthetic Alpha",
        "Synthetic Review",
    ]
    assert [alternative.origin for alternative in explanation.alternatives] == [
        "user_rule",
        "packaged_rule",
    ]
    assert all(alternative.rule_id for alternative in explanation.alternatives)
    assert all(alternative.matched_field == "title" for alternative in explanation.alternatives)
    assert all(
        alternative.matched_value == "Synthetic alpha review"
        for alternative in explanation.alternatives
    )
    assert explanation.conflicts == explanation.alternatives
    assert explanation.source_references == [f"activity:{local_id}"]
    assert explanation.uncertainty_reason == "existing_assignment_conflicts_with_alternatives"


def test_assignment_explanation_allows_unresolved_classification():
    usage = AppUsage(
        id=2**54 + 78,
        start=BASE,
        end=BASE + timedelta(minutes=10),
        app="Synthetic Unknown",
        title="No matching evidence",
    )

    explanation = Classifier([]).explain(
        usage,
        source_reference=f"activity:{usage.id}",
    )

    assert explanation.origin == "unresolved"
    assert explanation.existing_assignment is None
    assert explanation.selected_assignment is None
    assert explanation.alternatives == []
    assert explanation.conflicts == []
    assert explanation.uncertainty_reason == "no_matching_assignment_evidence"


def test_assignment_explanation_caps_alternatives_with_completeness_metadata():
    usage = AppUsage(
        id=2**54 + 80,
        start=BASE,
        end=BASE + timedelta(minutes=10),
        app="Synthetic Editor",
        title="Synthetic bounded evidence",
    )
    rules = [
        Rule(project=f"Synthetic Project {index:03d}", title="bounded")
        for index in range(101)
    ]

    explanation = Classifier(rules).explain(
        usage,
        source_reference=f"activity:{usage.id}",
    )

    assert len(explanation.alternatives) == 100
    assert explanation.alternatives_complete is False
    assert explanation.conflicts_complete is False
    assert explanation.uncertainty_reason == "multiple_matching_projects"


def _reconstruction_source(
    source_type,
    source_id,
    start_minute,
    end_minute,
    *,
    project_id=None,
    project_title=None,
    title=None,
):
    return ReconstructionSource(
        source_type=source_type,
        source_id=source_id,
        start=BASE + timedelta(minutes=start_minute),
        end=BASE + timedelta(minutes=end_minute),
        project_id=project_id,
        project_title=project_title,
        project_title_chain=[project_title] if project_title else [],
        app="Synthetic Editor" if source_type == "activity" else None,
        title=title,
        path="/synthetic/evidence.txt" if source_type == "activity" else None,
    )


def test_reconstruction_separates_interval_metrics_coverage_and_conflicts():
    booking = _reconstruction_source(
        "booking",
        2**54 + 100,
        0,
        10,
        project_id=10,
        project_title="Synthetic Internal",
        title="Synthetic customer review",
    )
    covered = _reconstruction_source(
        "activity",
        2**54 + 101,
        0,
        10,
        title="Synthetic customer review",
    )
    candidate = _reconstruction_source(
        "activity",
        2**54 + 102,
        10,
        20,
        title="Synthetic customer implementation",
    )
    identical = candidate.model_copy(update={"source_id": 2**54 + 103})
    conflicting = _reconstruction_source(
        "activity",
        2**54 + 104,
        15,
        25,
        project_id=11,
        project_title="Synthetic Other",
        title="Synthetic other work",
    )
    sources = [booking, covered, candidate, identical, conflicting]
    classifier = Classifier([Rule(project="Synthetic Customer", title="customer")])

    result = __import__("timing_cli.analysis", fromlist=["reconstruct_evidence"])
    reconstruction = result.reconstruct_evidence(sources, sources, classifier)

    assert reconstruction.metrics.scope == "window"
    assert reconstruction.metrics.raw_cumulative_activity_seconds == 40 * 60
    assert reconstruction.metrics.activity_interval_union_seconds == 25 * 60
    assert reconstruction.metrics.elapsed_evidence_span_seconds == 25 * 60
    assert reconstruction.metrics.gap_seconds == 0
    assert reconstruction.metrics.recorded_service_seconds == 10 * 60
    assert reconstruction.metrics.uncovered_candidate_seconds == 15 * 60
    assert not hasattr(reconstruction.metrics, "accepted_billable_seconds")

    records = {
        (record.source.source_type, record.source.source_id): record
        for record in reconstruction.records
    }
    booking_record = records[("booking", booking.source_id)]
    covered_record = records[("activity", covered.source_id)]
    candidate_record = records[("activity", candidate.source_id)]
    conflicting_record = records[("activity", conflicting.source_id)]

    assert booking_record.supporting_activity_references == [
        f"activity:{covered.source_id}"
    ]
    assert booking_record.assignment.existing_assignment.project_title == "Synthetic Internal"
    assert booking_record.assignment.alternatives[0].project_title == "Synthetic Customer"
    assert covered_record.candidate_intervals == []
    assert covered_record.covered_by_booking_references == [f"booking:{booking.source_id}"]
    assert candidate_record.candidate_intervals[0].duration_seconds == 10 * 60
    assert f"activity:{conflicting.source_id}" in candidate_record.conflict_references
    assert f"activity:{candidate.source_id}" in conflicting_record.conflict_references


def test_reconstruction_treats_matching_title_without_id_as_same_project():
    booking = _reconstruction_source(
        "booking",
        1,
        0,
        10,
        project_id=10,
        project_title="Synthetic Customer",
        title="Synthetic customer work",
    )
    activity = _reconstruction_source(
        "activity",
        2,
        0,
        10,
        title="Synthetic customer work",
    )
    classifier = Classifier([Rule(project="Synthetic Customer", title="customer")])

    result = __import__("timing_cli.analysis", fromlist=["reconstruct_evidence"])
    reconstruction = result.reconstruct_evidence(
        [booking, activity],
        [booking, activity],
        classifier,
    )
    records = {record.source.source_type: record for record in reconstruction.records}

    assert records["booking"].assignment.conflicts == []
    assert records["booking"].assignment.uncertainty_reason is None
    assert records["booking"].conflict_references == []
    assert records["activity"].conflict_references == []


def test_reconstruction_keeps_different_project_conflict():
    booking = _reconstruction_source(
        "booking",
        1,
        0,
        10,
        project_id=10,
        project_title="Synthetic Existing",
    )
    activity = _reconstruction_source(
        "activity",
        2,
        0,
        10,
        project_id=11,
        project_title="Synthetic Different",
    )

    result = __import__("timing_cli.analysis", fromlist=["reconstruct_evidence"])
    reconstruction = result.reconstruct_evidence(
        [booking, activity],
        [booking, activity],
        Classifier([]),
    )

    assert reconstruction.records[0].conflict_references == ["activity:2"]
    assert reconstruction.records[1].conflict_references == ["booking:1"]


def test_reconstruction_gap_is_evidence_span_minus_evidence_union():
    first = _reconstruction_source("activity", 1, 0, 10, title="Synthetic first")
    second = _reconstruction_source("activity", 2, 20, 30, title="Synthetic second")

    result = __import__("timing_cli.analysis", fromlist=["reconstruct_evidence"])
    reconstruction = result.reconstruct_evidence([first, second], [first, second], Classifier([]))

    assert reconstruction.metrics.elapsed_evidence_span_seconds == 30 * 60
    assert reconstruction.metrics.activity_interval_union_seconds == 20 * 60
    assert reconstruction.metrics.gap_seconds == 10 * 60
