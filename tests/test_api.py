from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from timing_cli.api import TimingApiClient, TimingApiError

BASE = datetime(2026, 7, 5, 9, 0).astimezone()


def _client_with_projects(projects: list[dict]) -> TimingApiClient:
    client = TimingApiClient("https://example.test", "token")
    client._project_cache[False] = projects
    return client


def test_resolve_project_ref_prefers_full_title_chain():
    client = _client_with_projects(
        [
            {"self": "/projects/1", "title": "Work", "title_chain": ["Client A", "Work"]},
            {"self": "/projects/2", "title": "Work", "title_chain": ["Client B", "Work"]},
        ]
    )

    assert client.resolve_project_ref("Work", ["Client B", "Work"]) == "/projects/2"


def test_resolve_project_ref_reports_ambiguous_leaf_title():
    client = _client_with_projects(
        [
            {"self": "/projects/1", "title": "Work", "title_chain": ["Client A", "Work"]},
            {"self": "/projects/2", "title": "Work", "title_chain": ["Client B", "Work"]},
        ]
    )

    with pytest.raises(TimingApiError, match="ambiguous"):
        client.resolve_project_ref("Work")


def test_resolve_project_ref_uses_config_overrides():
    client = _client_with_projects([])

    assert (
        client.resolve_project_ref(
            "Work",
            ["Client A", "Work"],
            project_id=17,
            overrides={"id:17": "/projects/remote"},
        )
        == "/projects/remote"
    )


def test_has_matching_time_entry_detects_existing_suggestion():
    client = _client_with_projects([])
    end = BASE + timedelta(minutes=30)
    existing = [
        {
            "start_date": BASE.isoformat(),
            "end_date": end.isoformat(),
            "title": "Work: Xcode",
            "project": {"self": "/projects/1"},
        }
    ]

    assert client.has_matching_time_entry(
        existing,
        BASE,
        end,
        "Work: Xcode",
        "/projects/1",
    )
    assert not client.has_matching_time_entry(
        existing,
        BASE,
        end,
        "Different title",
        "/projects/1",
    )


def test_has_matching_time_entry_normalizes_project_ids():
    client = _client_with_projects([])
    end = BASE + timedelta(minutes=30)
    existing = [
        {
            "start_date": BASE.isoformat(),
            "end_date": end.isoformat(),
            "title": "Work: Xcode",
            "project": {"id": 1},
        }
    ]

    assert client.has_matching_time_entry(
        existing,
        BASE,
        end,
        "Work: Xcode",
        "/projects/1",
    )
