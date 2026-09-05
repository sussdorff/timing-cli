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

import base64
import hashlib
import json
import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from timing_cli.models import (
    MAX_PROJECT_TITLE_CHAIN,
    MAX_RECONSTRUCTION_PAGE_SIZE,
    AppUsage,
    Project,
    ReconstructionSource,
)
from timing_cli.timing_predicates import TimingPredicateRule, decode_timing_predicate


class TimingDatabaseError(RuntimeError):
    """Raised when the local Timing database cannot be opened or read."""


@dataclass(frozen=True)
class ReconstructionSourcePage:
    """One SQL-bounded page of reconstruction source rows."""

    records: list[ReconstructionSource]
    total_count: int
    returned_count: int
    complete: bool
    next_cursor: str | None


@dataclass(frozen=True)
class ReconstructionSnapshot:
    """Digest and size of one deterministic reconstruction source window."""

    digest: str
    total_count: int


def _epoch_to_local(value: float) -> datetime:
    """Convert a Timing Unix-epoch timestamp to an aware local datetime."""
    return datetime.fromtimestamp(value).astimezone()


def _encode_reconstruction_cursor(
    start_ts: float,
    source_rank: int,
    source_id: int,
    snapshot_digest: str,
) -> str:
    payload = json.dumps(
        {
            "key": [start_ts.hex(), source_rank, str(source_id)],
            "snapshot": snapshot_digest,
            "version": 1,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_reconstruction_cursor(cursor: str) -> tuple[float, int, int, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        decoded = json.loads(payload)
        if decoded.get("version") != 1:
            raise ValueError
        start_hex, source_rank, source_id_text = decoded["key"]
        snapshot_digest = decoded["snapshot"]
        start_ts = float.fromhex(start_hex)
        source_id = int(source_id_text)
        if (
            not math.isfinite(start_ts)
            or source_rank not in {0, 1}
            or not isinstance(snapshot_digest, str)
            or len(snapshot_digest) != 64
        ):
            raise ValueError
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid reconstruction cursor") from exc
    return start_ts, source_rank, source_id, snapshot_digest


@contextmanager
def reconstruction_read_transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Pin all reads for one response to a single SQLite snapshot."""
    owns_transaction = not conn.in_transaction
    if owns_transaction:
        conn.execute("BEGIN")
    try:
        yield
    finally:
        if owns_transaction:
            conn.rollback()


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
        LEFT JOIN Application app ON app.id = a.applicationID
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
        LEFT JOIN Application app ON app.id = a.applicationID
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


def _fetch_reconstruction_rows(
    conn: sqlite3.Connection,
    start: datetime,
    end: datetime,
    *,
    limit: int,
    cursor_key: tuple[float, int, int] | None,
) -> list[sqlite3.Row]:
    window_params = (end.timestamp(), start.timestamp())
    params: list[float | int | None] = [
        *window_params,
        *window_params,
        start.timestamp(),
    ]
    if cursor_key:
        cursor_start, cursor_rank, cursor_id = cursor_key
        params.extend([cursor_start, cursor_start, cursor_rank, cursor_id])
    else:
        params.extend([None, None, None, None])
    params.append(limit)

    return conn.execute(
        """
        WITH sources AS (
            SELECT
                'booking' AS source_type,
                0 AS source_rank,
                task.id AS source_id,
                task.startDate AS start_ts,
                task.endDate AS end_ts,
                task.projectID AS project_id,
                project.title AS project_title,
                NULL AS application_id,
                NULL AS app,
                NULL AS bundle_id,
                task.title AS title,
                NULL AS path,
                task.notes AS notes
            FROM TaskActivity task
            LEFT JOIN Project project ON project.id = task.projectID
            WHERE task.isDeleted = 0
              AND task.isRunning = 0
              AND task.startDate < ?
              AND task.endDate > ?

            UNION ALL

            SELECT
                'activity' AS source_type,
                1 AS source_rank,
                activity.id AS source_id,
                activity.startDate AS start_ts,
                activity.endDate AS end_ts,
                activity.projectID AS project_id,
                project.title AS project_title,
                activity.applicationID AS application_id,
                COALESCE(application.title, application.bundleIdentifier,
                         application.executable, 'Unknown') AS app,
                application.bundleIdentifier AS bundle_id,
                title.stringValue AS title,
                path.stringValue AS path,
                NULL AS notes
            FROM AppActivity activity
            LEFT JOIN Application application ON application.id = activity.applicationID
            LEFT JOIN Title title ON title.id = activity.titleID
            LEFT JOIN Path path ON path.id = activity.pathID
            LEFT JOIN Project project ON project.id = activity.projectID
            WHERE activity.isDeleted = 0
              AND activity.startDate < ?
              AND activity.endDate > ?
        ), ordered_sources AS (
            SELECT *, MAX(start_ts, ?) AS clipped_start_ts
            FROM sources
        )
        SELECT * FROM ordered_sources
        WHERE ? IS NULL OR (clipped_start_ts, source_rank, source_id) > (?, ?, ?)
        ORDER BY clipped_start_ts, source_rank, source_id
        LIMIT ?
        """,
        params,
    ).fetchall()


def _reconstruction_records_from_rows(
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
    start: datetime,
    end: datetime,
) -> list[ReconstructionSource]:
    project_ids = {row["project_id"] for row in rows if row["project_id"] is not None}
    title_chains = _project_title_chains(conn, project_ids)
    records: list[ReconstructionSource] = []
    for row in rows:
        project_title_chain = title_chains.get(row["project_id"], [])
        records.append(
            ReconstructionSource(
                source_type=row["source_type"],
                source_id=row["source_id"],
                start=max(_epoch_to_local(row["start_ts"]), start),
                end=min(_epoch_to_local(row["end_ts"]), end),
                project_id=row["project_id"],
                project_title=row["project_title"],
                project_title_chain=project_title_chain[-MAX_PROJECT_TITLE_CHAIN:],
                project_title_chain_complete=(
                    len(project_title_chain) <= MAX_PROJECT_TITLE_CHAIN
                ),
                application_id=row["application_id"],
                app=row["app"],
                bundle_id=row["bundle_id"],
                title=row["title"],
                path=row["path"],
                notes=row["notes"],
            )
        )
    return records


def reconstruction_snapshot(
    conn: sqlite3.Connection,
    start: datetime,
    end: datetime,
) -> ReconstructionSnapshot:
    """Stream a canonical digest of every mutable source field in a window."""
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            {"end": end.isoformat(), "start": start.isoformat(), "version": 1},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    cursor_key = None
    total_count = 0
    while True:
        rows = _fetch_reconstruction_rows(
            conn,
            start,
            end,
            limit=MAX_RECONSTRUCTION_PAGE_SIZE,
            cursor_key=cursor_key,
        )
        records = _reconstruction_records_from_rows(conn, rows, start, end)
        for row, record in zip(rows, records, strict=True):
            canonical = json.dumps(
                {
                    "record": record.model_dump(mode="json"),
                    "source_end": float(row["end_ts"]).hex(),
                    "source_start": float(row["start_ts"]).hex(),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            digest.update(len(canonical).to_bytes(8, "big"))
            digest.update(canonical)
        total_count += len(rows)
        if len(rows) < MAX_RECONSTRUCTION_PAGE_SIZE:
            break
        last = rows[-1]
        cursor_key = (
            last["clipped_start_ts"],
            last["source_rank"],
            last["source_id"],
        )
    return ReconstructionSnapshot(digest=digest.hexdigest(), total_count=total_count)


def list_reconstruction_sources(
    conn: sqlite3.Connection,
    start: datetime,
    end: datetime,
    *,
    limit: int,
    cursor: str | None = None,
    snapshot: ReconstructionSnapshot | None = None,
) -> ReconstructionSourcePage:
    """Return one keyset page bound to a deterministic source snapshot."""
    if not 1 <= limit <= MAX_RECONSTRUCTION_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_RECONSTRUCTION_PAGE_SIZE}")
    decoded_cursor = _decode_reconstruction_cursor(cursor) if cursor else None
    if end <= start:
        return ReconstructionSourcePage([], 0, 0, True, None)

    with reconstruction_read_transaction(conn):
        current_snapshot = snapshot or reconstruction_snapshot(conn, start, end)
        if decoded_cursor and decoded_cursor[3] != current_snapshot.digest:
            raise ValueError("Stale reconstruction cursor: source window changed")
        cursor_key = decoded_cursor[:3] if decoded_cursor else None
        rows = _fetch_reconstruction_rows(
            conn,
            start,
            end,
            limit=limit + 1,
            cursor_key=cursor_key,
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        records = _reconstruction_records_from_rows(conn, page_rows, start, end)

    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = _encode_reconstruction_cursor(
            last["clipped_start_ts"],
            last["source_rank"],
            last["source_id"],
            current_snapshot.digest,
        )
    return ReconstructionSourcePage(
        records=records,
        total_count=current_snapshot.total_count,
        returned_count=len(records),
        complete=not has_more,
        next_cursor=next_cursor,
    )


def iter_reconstruction_sources(
    conn: sqlite3.Connection,
    start: datetime,
    end: datetime,
    *,
    batch_size: int = MAX_RECONSTRUCTION_PAGE_SIZE,
    snapshot: ReconstructionSnapshot | None = None,
) -> Iterator[ReconstructionSource]:
    """Stream a full window through capped SQL keyset pages."""
    with reconstruction_read_transaction(conn):
        current_snapshot = snapshot or reconstruction_snapshot(conn, start, end)
        cursor = None
        while True:
            page = list_reconstruction_sources(
                conn,
                start,
                end,
                limit=batch_size,
                cursor=cursor,
                snapshot=current_snapshot,
            )
            yield from page.records
            if page.complete:
                return
            cursor = page.next_cursor


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
