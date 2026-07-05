"""Tests for the aggregation and classification logic (no database needed)."""

from __future__ import annotations

from datetime import datetime, timedelta

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
