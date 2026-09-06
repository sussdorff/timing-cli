from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import timing_cli.analysis as analysis
import timing_cli.db as db
from timing_cli.db import list_app_usage, list_projects, open_db
from timing_cli.rules import Classifier

BASE = datetime(2026, 7, 5, 0, 0).astimezone()


def _create_timing_fixture(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE Application(
            id INTEGER PRIMARY KEY,
            bundleIdentifier TEXT,
            executable TEXT,
            title TEXT
        );
        CREATE TABLE Title(id INTEGER PRIMARY KEY, stringValue TEXT);
        CREATE TABLE Path(id INTEGER PRIMARY KEY, stringValue TEXT);
        CREATE TABLE Project(
            id INTEGER PRIMARY KEY,
            title TEXT,
            parentID INTEGER,
            color TEXT,
            productivityScore REAL,
            isArchived INTEGER,
            listPosition INTEGER
        );
        CREATE TABLE AppActivity(
            id INTEGER PRIMARY KEY,
            startDate REAL,
            endDate REAL,
            applicationID INTEGER,
            titleID INTEGER,
            pathID INTEGER,
            projectID INTEGER,
            isDeleted INTEGER
        );
        CREATE TABLE TaskActivity(
            id INTEGER PRIMARY KEY,
            startDate REAL NOT NULL,
            endDate REAL NOT NULL,
            projectID INTEGER,
            title TEXT,
            notes TEXT,
            isDeleted INTEGER NOT NULL DEFAULT 0,
            isRunning INTEGER NOT NULL DEFAULT 0,
            property_bag TEXT
        );
        """
    )
    conn.execute("INSERT INTO Application VALUES (1, 'com.test.app', 'Test', 'TestApp')")
    conn.execute("INSERT INTO Title VALUES (1, 'Fixture Window')")
    conn.execute("INSERT INTO Path VALUES (1, '/tmp/fixture.txt')")
    conn.execute("INSERT INTO Project VALUES (1, 'Client', NULL, NULL, 0, 0, 0)")
    conn.execute("INSERT INTO Project VALUES (2, 'Work', 1, NULL, 0, 0, 1)")
    conn.execute("INSERT INTO Project VALUES (3, 'Archive', NULL, NULL, 0, 1, 2)")
    conn.execute(
        "INSERT INTO AppActivity VALUES (1, ?, ?, 1, 1, 1, 2, 0)",
        (
            (BASE - timedelta(minutes=30)).timestamp(),
            (BASE + timedelta(minutes=30)).timestamp(),
        ),
    )
    conn.commit()
    conn.close()


def test_list_app_usage_clips_slices_to_requested_window(tmp_path):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)

    with open_db(db_path) as conn:
        rows = list_app_usage(conn, BASE, BASE + timedelta(minutes=10))

    assert len(rows) == 1
    row = rows[0]
    assert row.start == BASE
    assert row.end == BASE + timedelta(minutes=10)
    assert row.duration_seconds == 10 * 60
    assert row.project_title == "Work"
    assert row.project_title_chain == ["Client", "Work"]


def test_list_projects_filters_archived_projects(tmp_path):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)

    with open_db(db_path) as conn:
        active = list_projects(conn, include_archived=False)
        all_projects = list_projects(conn, include_archived=True)

    assert [project.title for project in active] == ["Client", "Work"]
    assert [project.title for project in all_projects] == ["Client", "Archive", "Work"]


def test_reconstruction_source_pages_are_bounded_clipped_and_lossless(tmp_path):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)
    booking_id = 2**54 + 123
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO TaskActivity VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        [
            (
                booking_id,
                (BASE - timedelta(seconds=0.25)).timestamp(),
                (BASE + timedelta(minutes=10, seconds=0.75)).timestamp(),
                2,
                "Synthetic planning session",
                "Synthetic booking note",
                0,
                0,
            ),
            (
                booking_id + 1,
                BASE.timestamp(),
                (BASE + timedelta(minutes=5)).timestamp(),
                2,
                "Deleted synthetic booking",
                None,
                1,
                0,
            ),
            (
                booking_id + 2,
                BASE.timestamp(),
                (BASE + timedelta(minutes=5)).timestamp(),
                2,
                "Running synthetic booking",
                None,
                0,
                1,
            ),
            (
                booking_id + 3,
                (BASE - timedelta(hours=2)).timestamp(),
                (BASE - timedelta(hours=1)).timestamp(),
                2,
                "Outside synthetic booking",
                None,
                0,
                0,
            ),
        ],
    )
    conn.commit()
    conn.close()

    window_end = BASE + timedelta(minutes=20)
    with open_db(db_path) as read_conn:
        first = db.list_reconstruction_sources(read_conn, BASE, window_end, limit=1)
        second = db.list_reconstruction_sources(
            read_conn,
            BASE,
            window_end,
            limit=1,
            cursor=first.next_cursor,
        )

    records = [*first.records, *second.records]
    assert first.total_count == second.total_count == 2
    assert first.returned_count == second.returned_count == 1
    assert first.complete is False
    assert first.next_cursor is not None
    assert second.complete is True
    assert second.next_cursor is None
    assert [(record.source_type, record.source_id) for record in records] == [
        ("booking", booking_id),
        ("activity", 1),
    ]

    booking = records[0]
    assert booking.start == BASE
    assert booking.end == BASE + timedelta(minutes=10, seconds=0.75)
    assert booking.duration_seconds == 600.75
    assert booking.title == "Synthetic planning session"
    assert booking.notes == "Synthetic booking note"
    assert booking.project_title_chain == ["Client", "Work"]
    assert booking.model_dump(mode="json")["source_id"] == str(booking_id)


@pytest.mark.parametrize("limit", [0, 201])
def test_reconstruction_source_page_rejects_out_of_range_limits(tmp_path, limit):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)

    with open_db(db_path) as conn:
        with pytest.raises(ValueError, match="limit must be between 1 and 200"):
            db.list_reconstruction_sources(conn, BASE, BASE + timedelta(days=1), limit=limit)


def test_reconstruction_source_page_rejects_invalid_cursor(tmp_path):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)

    with open_db(db_path) as conn:
        with pytest.raises(ValueError, match="Invalid reconstruction cursor"):
            db.list_reconstruction_sources(
                conn,
                BASE,
                BASE + timedelta(days=1),
                limit=20,
                cursor="not-a-valid-cursor",
            )


def test_reconstruction_preserves_activity_without_application_metadata(tmp_path):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO AppActivity VALUES (2, ?, ?, 999, NULL, NULL, NULL, 0)",
        (BASE.timestamp(), (BASE + timedelta(minutes=5)).timestamp()),
    )
    conn.commit()
    conn.close()

    with open_db(db_path) as conn:
        page = db.list_reconstruction_sources(
            conn,
            BASE,
            BASE + timedelta(minutes=10),
            limit=10,
        )

    missing_metadata = next(record for record in page.records if record.source_id == 2)
    assert page.total_count == page.returned_count == 2
    assert page.complete is True
    assert missing_metadata.app == "Unknown"
    assert missing_metadata.application_id == 999


def test_reconstruction_total_count_is_computed_in_sql(tmp_path):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)
    statements = []

    with open_db(db_path) as conn:
        conn.set_trace_callback(statements.append)
        page = db.list_reconstruction_sources(
            conn,
            BASE,
            BASE + timedelta(minutes=10),
            limit=10,
        )

    assert page.total_count == 1
    assert any("COUNT(*)" in statement.upper() for statement in statements)


def test_reconstruction_cursor_rejects_insertion_before_position(tmp_path):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO TaskActivity VALUES (10, ?, ?, 2, 'Later', NULL, 0, 0, NULL)",
        (
            (BASE + timedelta(minutes=5)).timestamp(),
            (BASE + timedelta(minutes=10)).timestamp(),
        ),
    )
    conn.commit()
    conn.close()

    with open_db(db_path) as conn:
        first = db.list_reconstruction_sources(
            conn,
            BASE,
            BASE + timedelta(minutes=20),
            limit=1,
        )

    writer = sqlite3.connect(db_path)
    writer.execute(
        "INSERT INTO TaskActivity VALUES (11, ?, ?, 2, 'Inserted', NULL, 0, 0, NULL)",
        (BASE.timestamp(), (BASE + timedelta(minutes=2)).timestamp()),
    )
    writer.commit()
    writer.close()

    with open_db(db_path) as conn:
        with pytest.raises(ValueError, match="Stale reconstruction cursor"):
            db.list_reconstruction_sources(
                conn,
                BASE,
                BASE + timedelta(minutes=20),
                limit=1,
                cursor=first.next_cursor,
            )


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE AppActivity SET endDate = endDate - 60 WHERE id = 1",
        "UPDATE AppActivity SET isDeleted = 1 WHERE id = 1",
    ],
    ids=["update", "delete"],
)
def test_reconstruction_cursor_rejects_updated_or_deleted_source(tmp_path, mutation):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO TaskActivity VALUES (10, ?, ?, 2, 'Later', NULL, 0, 0, NULL)",
        (
            (BASE + timedelta(minutes=5)).timestamp(),
            (BASE + timedelta(minutes=10)).timestamp(),
        ),
    )
    conn.commit()
    conn.close()

    with open_db(db_path) as conn:
        first = db.list_reconstruction_sources(
            conn,
            BASE,
            BASE + timedelta(minutes=20),
            limit=1,
        )

    writer = sqlite3.connect(db_path)
    writer.execute(mutation)
    writer.commit()
    writer.close()

    with open_db(db_path) as conn:
        with pytest.raises(ValueError, match="Stale reconstruction cursor"):
            db.list_reconstruction_sources(
                conn,
                BASE,
                BASE + timedelta(minutes=20),
                limit=1,
                cursor=first.next_cursor,
            )


def test_reconstruction_response_uses_one_snapshot_during_concurrent_write(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)
    setup = sqlite3.connect(db_path)
    setup.execute("PRAGMA journal_mode=WAL")
    setup.close()
    original_snapshot = db.reconstruction_snapshot
    wrote = False

    def snapshot_then_write(conn, start, end):
        nonlocal wrote
        snapshot = original_snapshot(conn, start, end)
        if not wrote:
            writer = sqlite3.connect(db_path)
            writer.execute(
                "INSERT INTO AppActivity VALUES (2, ?, ?, 1, 1, 1, 2, 0)",
                (
                    BASE.timestamp(),
                    (BASE + timedelta(minutes=5)).timestamp(),
                ),
            )
            writer.commit()
            writer.close()
            wrote = True
        return snapshot

    monkeypatch.setattr(db, "reconstruction_snapshot", snapshot_then_write)
    window_end = BASE + timedelta(minutes=10)
    with open_db(db_path) as conn:
        response = analysis.reconstruct_window(
            conn,
            BASE,
            window_end,
            Classifier([]),
            limit=10,
        )

    assert response.pagination.total_count == 1
    assert response.pagination.returned_count == 1
    assert response.metrics.raw_cumulative_activity_seconds == 10 * 60

    monkeypatch.setattr(db, "reconstruction_snapshot", original_snapshot)
    with open_db(db_path) as conn:
        fresh = analysis.reconstruct_window(
            conn,
            BASE,
            window_end,
            Classifier([]),
            limit=10,
        )
    assert fresh.pagination.total_count == 2
    assert fresh.metrics.raw_cumulative_activity_seconds == 15 * 60


def test_reconstruction_project_chain_is_bounded_and_keeps_current_project(tmp_path):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)
    booking_id = 2**54 + 129
    conn = sqlite3.connect(db_path)
    parent_id = None
    for index in range(33):
        project_id = 100 + index
        conn.execute(
            "INSERT INTO Project VALUES (?, ?, ?, NULL, 0, 0, ?)",
            (project_id, f"Synthetic Level {index:02d}", parent_id, 10 + index),
        )
        parent_id = project_id
    conn.execute(
        "INSERT INTO TaskActivity VALUES (?, ?, ?, ?, ?, NULL, 0, 0, NULL)",
        (
            booking_id,
            BASE.timestamp(),
            (BASE + timedelta(minutes=10)).timestamp(),
            parent_id,
            "Synthetic deep project booking",
        ),
    )
    conn.commit()
    conn.close()

    with open_db(db_path) as read_conn:
        page = db.list_reconstruction_sources(
            read_conn,
            BASE,
            BASE + timedelta(minutes=20),
            limit=10,
        )

    booking = next(record for record in page.records if record.source_id == booking_id)
    assert len(booking.project_title_chain) == 32
    assert booking.project_title_chain[-1] == "Synthetic Level 32"
    assert booking.project_title_chain_complete is False


def test_reconstruction_service_is_versioned_complete_and_page_boundary_safe(tmp_path):
    db_path = tmp_path / "Timing.db"
    _create_timing_fixture(db_path)
    booking_id = 2**54 + 130
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO TaskActivity VALUES (?, ?, ?, ?, ?, ?, 0, 0, NULL)",
        (
            booking_id,
            BASE.timestamp(),
            (BASE + timedelta(minutes=10)).timestamp(),
            2,
            "Synthetic service",
            "Synthetic service note",
        ),
    )
    conn.commit()
    conn.close()

    extracted_at = datetime(2026, 7, 6, 8, 0).astimezone()
    window_end = BASE + timedelta(minutes=20)
    with open_db(db_path) as read_conn:
        first = analysis.reconstruct_window(
            read_conn,
            BASE,
            window_end,
            Classifier([]),
            limit=1,
            extracted_at=extracted_at,
            timezone_name="Synthetic/Local",
        )
        second = analysis.reconstruct_window(
            read_conn,
            BASE,
            window_end,
            Classifier([]),
            limit=1,
            cursor=first.pagination.next_cursor,
            extracted_at=extracted_at,
            timezone_name="Synthetic/Local",
        )

    assert first.schema_version == "timing.reconstruction.v1"
    assert first.window.timezone == "Synthetic/Local"
    assert first.window.interval_semantics == "half-open"
    assert first.window.start == BASE
    assert first.window.end == window_end
    assert first.window.extracted_at == extracted_at
    assert first.pagination.stable_order == ["start", "source_type", "source_id"]
    assert first.pagination.total_count == second.pagination.total_count == 2
    assert first.pagination.returned_count == second.pagination.returned_count == 1
    assert first.pagination.complete is False
    assert second.pagination.complete is True
    assert first.metrics == second.metrics
    assert first.metrics.scope == "window"

    first_record = first.records[0]
    second_record = second.records[0]
    assert first_record.source.source_type == "booking"
    assert first_record.supporting_activity_references == ["activity:1"]
    assert second_record.source.source_type == "activity"
    assert second_record.covered_by_booking_references == [f"booking:{booking_id}"]
    assert second_record.candidate_intervals[0].start == BASE + timedelta(minutes=10)
    assert first_record.source.source_id != second_record.source.source_id
    payloads = [
        first_record.model_dump(mode="json"),
        second_record.model_dump(mode="json"),
    ]
    assert payloads[0]["source"]["source_id"] == str(booking_id)
    assert payloads[1]["source"]["source_id"] == "1"
