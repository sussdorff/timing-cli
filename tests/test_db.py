from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from timing_cli.db import list_app_usage, list_projects, open_db

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
