"""Read-only access to the local Timing.app SQLite database.

Timing stores its automatically recorded app activity in a Core-Data SQLite
store (``SQLite.db``). We open it strictly read-only so we never interfere with
Timing's own writes or its sync engine.

Key schema facts (Timing2):
  * ``AppActivity(startDate, endDate, applicationID, titleID, pathID, projectID,
    isDeleted)`` — one row per automatically tracked activity slice.
  * ``startDate`` / ``endDate`` are **Unix epoch seconds** (REAL), NOT Core-Data
    reference dates. Verified empirically: adding the 978307200 NSDate offset
    shifts timestamps ~31 years into the future.
  * ``Application(bundleIdentifier, executable, title)``, ``Title(stringValue)``
    and ``Path(stringValue)`` are normalized lookup tables.
  * ``Project(id, title, parentID, color, productivityScore, isArchived)``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from timing_cli.models import AppUsage, Project
from timing_cli.timing_predicates import TimingPredicateRule, decode_timing_predicate


class TimingDatabaseError(RuntimeError):
    """Raised when the local Timing database cannot be opened or read."""


def _epoch_to_local(value: float) -> datetime:
    """Convert a Timing Unix-epoch timestamp to an aware local datetime."""
    return datetime.fromtimestamp(value).astimezone()


@contextmanager
def open_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open the Timing database read-only.

    We deliberately do NOT copy the database. A read-only URI connection reads
    the live WAL without taking a write lock, so Timing keeps running normally.
    """
    if not db_path.exists():
        raise TimingDatabaseError(
            f"Timing database not found at {db_path}. Is Timing.app installed? "
            "Set db_path in ~/.config/timing-cli/config.toml if it lives elsewhere."
        )
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    except sqlite3.OperationalError as exc:  # pragma: no cover - environment specific
        raise TimingDatabaseError(f"Could not open Timing database read-only: {exc}") from exc
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def list_projects(conn: sqlite3.Connection, include_archived: bool = True) -> list[Project]:
    """Return all local projects, ordered by hierarchy position."""
    if include_archived:
        query = """
        SELECT id, title, parentID, isArchived, color, productivityScore
        FROM Project
        ORDER BY parentID IS NOT NULL, listPosition
        """
    else:
        query = """
        SELECT id, title, parentID, isArchived, color, productivityScore
        FROM Project
        WHERE isArchived = 0
        ORDER BY parentID IS NOT NULL, listPosition
        """
    rows = conn.execute(query).fetchall()
    return [
        Project(
            id=r["id"],
            title=r["title"],
            parent_id=r["parentID"],
            is_archived=bool(r["isArchived"]),
            color=r["color"],
            productivity_score=r["productivityScore"] or 0.0,
        )
        for r in rows
    ]


def _project_title_chains(
    conn: sqlite3.Connection,
    project_ids: set[int],
) -> dict[int, list[str]]:
    """Return local project title chains keyed by local project id."""
    projects: dict[int, tuple[str, int | None]] = {}

    def fetch(project_id: int) -> tuple[str, int | None] | None:
        if project_id in projects:
            return projects[project_id]

        row = conn.execute(
            "SELECT title, parentID FROM Project WHERE id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        project = (row["title"], row["parentID"])
        projects[project_id] = project
        return project

    chains: dict[int, list[str]] = {}

    def build(project_id: int) -> list[str]:
        if project_id in chains:
            return chains[project_id]

        seen: set[int] = set()
        chain: list[str] = []
        current: int | None = project_id
        while current is not None and current not in seen:
            seen.add(current)
            project = fetch(current)
            if project is None:
                break
            title, parent_id = project
            chain.append(title)
            current = parent_id

        chain.reverse()
        chains[project_id] = chain
        return chain

    return {project_id: build(project_id) for project_id in project_ids}


def list_app_usage(
    conn: sqlite3.Connection,
    start: datetime,
    end: datetime,
    project_id: int | None = None,
) -> list[AppUsage]:
    """Return automatically tracked app usage overlapping ``[start, end)``.

    A slice is included when it overlaps the window at all (its start is before
    ``end`` and its end is after ``start``).
    """
    if end <= start:
        return []

    params: list[float | int] = [end.timestamp(), start.timestamp()]
    if project_id is None:
        query = """
        SELECT
            a.id            AS id,
            a.startDate     AS start_ts,
            a.endDate       AS end_ts,
            a.applicationID  AS application_id,
            a.projectID     AS project_id,
            p.title         AS project_title,
            app.title       AS app_title,
            app.bundleIdentifier AS bundle_id,
            app.executable  AS executable,
            t.stringValue   AS window_title,
            pa.stringValue  AS doc_path
        FROM AppActivity a
        JOIN Application app ON app.id = a.applicationID
        LEFT JOIN Title   t  ON t.id  = a.titleID
        LEFT JOIN Path    pa ON pa.id = a.pathID
        LEFT JOIN Project p  ON p.id  = a.projectID
        WHERE a.isDeleted = 0
          AND a.startDate < ?
          AND a.endDate   > ?
        ORDER BY a.startDate
        """
    else:
        query = """
        SELECT
            a.id            AS id,
            a.startDate     AS start_ts,
            a.endDate       AS end_ts,
            a.applicationID  AS application_id,
            a.projectID     AS project_id,
            p.title         AS project_title,
            app.title       AS app_title,
            app.bundleIdentifier AS bundle_id,
            app.executable  AS executable,
            t.stringValue   AS window_title,
            pa.stringValue  AS doc_path
        FROM AppActivity a
        JOIN Application app ON app.id = a.applicationID
        LEFT JOIN Title   t  ON t.id  = a.titleID
        LEFT JOIN Path    pa ON pa.id = a.pathID
        LEFT JOIN Project p  ON p.id  = a.projectID
        WHERE a.isDeleted = 0
          AND a.startDate < ?
          AND a.endDate   > ?
          AND a.projectID = ?
        ORDER BY a.startDate
        """
        params.append(project_id)

    rows = conn.execute(query, params).fetchall()

    project_ids = {r["project_id"] for r in rows if r["project_id"] is not None}
    title_chains = _project_title_chains(conn, project_ids)
    usage: list[AppUsage] = []
    for r in rows:
        app_name = r["app_title"] or r["bundle_id"] or r["executable"] or "Unknown"
        clipped_start = max(_epoch_to_local(r["start_ts"]), start)
        clipped_end = min(_epoch_to_local(r["end_ts"]), end)
        if clipped_end <= clipped_start:
            continue
        project_title_chain = title_chains.get(r["project_id"], [])
        project_title = r["project_title"]
        if project_title and not project_title_chain:
            project_title_chain = [project_title]
        usage.append(
            AppUsage(
                id=r["id"],
                start=clipped_start,
                end=clipped_end,
                application_id=r["application_id"],
                app=app_name,
                bundle_id=r["bundle_id"],
                title=r["window_title"],
                path=r["doc_path"],
                project_id=r["project_id"],
                project_title=project_title,
                project_title_chain=project_title_chain,
            )
        )
    return usage


def list_timing_predicate_rules(
    conn: sqlite3.Connection,
    include_archived: bool = False,
) -> list[TimingPredicateRule]:
    """Return decoded Timing project predicate rules from the local database."""
    project_columns = {r["name"] for r in conn.execute("PRAGMA table_info(Project)")}
    if "predicate" not in project_columns:
        return []

    if include_archived:
        query = """
        SELECT id, title, predicate
        FROM Project
        WHERE predicate IS NOT NULL
        ORDER BY ruleListPosition, listPosition
        """
    else:
        query = """
        SELECT id, title, predicate
        FROM Project
        WHERE predicate IS NOT NULL AND isArchived = 0
        ORDER BY ruleListPosition, listPosition
        """

    rows = conn.execute(query).fetchall()
    title_chains = _project_title_chains(conn, {r["id"] for r in rows})
    rules: list[TimingPredicateRule] = []
    for row in rows:
        conditions = decode_timing_predicate(row["predicate"])
        if not conditions:
            continue
        title_chain = tuple(title_chains.get(row["id"], [row["title"]]))
        rules.append(
            TimingPredicateRule(
                project_id=row["id"],
                project_title=row["title"],
                project_title_chain=title_chain,
                conditions=conditions,
            )
        )
    return rules


def date_range(conn: sqlite3.Connection) -> tuple[datetime, datetime] | None:
    """Return the (earliest start, latest end) of recorded activity, or None."""
    row = conn.execute(
        "SELECT MIN(startDate) AS lo, MAX(endDate) AS hi FROM AppActivity WHERE isDeleted = 0"
    ).fetchone()
    if row is None or row["lo"] is None:
        return None
    return _epoch_to_local(row["lo"]), _epoch_to_local(row["hi"])
