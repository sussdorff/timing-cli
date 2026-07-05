"""Tests for the aggregation and classification logic (no database needed)."""

from __future__ import annotations

import os
import time as time_module
from datetime import datetime, timedelta, timezone

from timing_cli.analysis import aggregate, summarize_by_project
from timing_cli.config import Rule
from timing_cli.models import AppUsage
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
