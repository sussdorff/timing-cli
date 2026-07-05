"""Client for the Timing Web API (https://web.timingapp.com/docs/).

The Web API is the safe write path: it can *create* time entries even though it
cannot *read* local app usage. We never write to the local SQLite store, which
would risk corrupting Timing's Core-Data invariants and its sync engine.

Auth is a bearer token from https://web.timingapp.com/integrations/tokens,
supplied via ``TIMING_API_KEY`` or the config file.

Payload shapes follow Timing Web API v1: time entries take ``start_date``,
``end_date``, ``project`` (a project self-reference such as ``/projects/1``),
``title``, ``notes`` and ``replace_existing``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx


class TimingApiError(RuntimeError):
    """Raised when the Timing Web API returns an error or no token is set."""


class TimingApiClient:
    def __init__(self, base_url: str, token: str | None, timeout: float = 30.0) -> None:
        if not token:
            raise TimingApiError(
                "No Timing API token. Set TIMING_API_KEY or api_token in the config. "
                "Create one at https://web.timingapp.com/integrations/tokens"
            )
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        self._project_cache: dict[bool, list[dict[str, Any]]] = {}

    def __enter__(self) -> TimingApiClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:  # pragma: no cover - network dependent
            raise TimingApiError(f"Request to Timing API failed: {exc}") from exc
        if resp.status_code >= 400:
            raise TimingApiError(
                f"Timing API {method} {path} -> {resp.status_code}: {resp.text[:500]}"
            )
        if not resp.content:
            return None
        return resp.json()

    # -- Projects ---------------------------------------------------------

    def list_projects(self, hide_archived: bool = True) -> list[dict[str, Any]]:
        if hide_archived in self._project_cache:
            return self._project_cache[hide_archived]

        params = {"hide_archived": "true" if hide_archived else "false"}
        data = self._request("GET", "/projects", params=params)
        projects = data.get("data", []) if isinstance(data, dict) else (data or [])
        self._project_cache[hide_archived] = projects
        return projects

    def find_project_ref(self, title: str) -> str | None:
        """Compatibility wrapper for strict project resolution.

        Returns the unique Web-API self-reference for ``title`` or ``None`` when
        no project matches. Raises ``TimingApiError`` for ambiguous leaf-title
        matches; callers that need disambiguation should use
        ``resolve_project_ref`` with a title chain or config overrides.
        """
        return self.resolve_project_ref(title)

    def resolve_project_ref(
        self,
        title: str,
        title_chain: list[str] | tuple[str, ...] | None = None,
        project_id: int | None = None,
        overrides: dict[str, str] | None = None,
    ) -> str | None:
        """Resolve a local project to a unique Web-API self-reference.

        Resolution order:
        1. Config overrides keyed by local id, ``id:<id>``, full title chain, or
           leaf title.
        2. Exact remote title-chain match.
        3. Exact remote leaf-title match, only when unique.
        """
        chain = [part.strip() for part in title_chain or [] if part.strip()]
        if not chain and title.strip():
            chain = [title.strip()]
        full_chain = " / ".join(chain)

        override_keys = []
        if project_id is not None:
            override_keys.extend((str(project_id), f"id:{project_id}"))
        override_keys.extend(key for key in (full_chain, title.strip()) if key)

        normalized_overrides = {
            key.strip().lower(): value for key, value in (overrides or {}).items()
        }
        for key in override_keys:
            ref = normalized_overrides.get(key.strip().lower())
            if ref:
                return ref

        target = title.strip().lower()
        projects = self.list_projects(hide_archived=False)

        if full_chain:
            chain_matches = [
                project
                for project in projects
                if _project_full_title(project).lower() == full_chain.lower()
            ]
            if len(chain_matches) == 1:
                return _project_ref(chain_matches[0])
            if len(chain_matches) > 1:
                raise TimingApiError(_ambiguous_project_message(full_chain, chain_matches))

        leaf_matches = [
            project
            for project in projects
            if _project_leaf_title(project).lower() == target
        ]
        if len(leaf_matches) == 1:
            return _project_ref(leaf_matches[0])
        if len(leaf_matches) > 1:
            raise TimingApiError(_ambiguous_project_message(title, leaf_matches))
        return None

    def create_project(self, title: str, parent_ref: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"title": title}
        if parent_ref:
            body["parent"] = parent_ref
        data = self._request("POST", "/projects", json=body)
        return data.get("data", data) if isinstance(data, dict) else data

    # -- Time entries -----------------------------------------------------

    def list_time_entries(
        self,
        start_min: datetime | None = None,
        start_max: datetime | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if start_min:
            params["start_date_min"] = start_min.isoformat()
        if start_max:
            params["start_date_max"] = start_max.isoformat()
        data = self._request("GET", "/time-entries", params=params)
        return data.get("data", []) if isinstance(data, dict) else (data or [])

    def create_time_entry(
        self,
        start: datetime,
        end: datetime,
        project_ref: str | None,
        title: str,
        notes: str = "",
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "title": title,
            "replace_existing": replace_existing,
        }
        if project_ref:
            body["project"] = project_ref
        if notes:
            body["notes"] = notes
        data = self._request("POST", "/time-entries", json=body)
        return data.get("data", data) if isinstance(data, dict) else data

    def has_matching_time_entry(
        self,
        entries: list[dict[str, Any]],
        start: datetime,
        end: datetime,
        title: str,
        project_ref: str | None,
    ) -> bool:
        """Return True if an existing entry already represents this suggestion.

        This is an idempotency heuristic for ``push``. It intentionally requires
        matching start/end timestamps, title, and project reference; if Timing's
        API later normalizes titles or rounds timestamps differently, callers
        should prefer ``--replace`` or broaden this matcher deliberately.
        """
        return any(
            _time_entry_matches(entry, start, end, title, project_ref)
            for entry in entries
        )

    def generate_report(
        self,
        start_min: datetime,
        start_max: datetime,
        project_refs: list[str] | None = None,
        columns: list[str] | None = None,
        include_app_usage: bool = False,
    ) -> Any:
        params: list[tuple[str, str]] = [
            ("start_date_min", start_min.isoformat()),
            ("start_date_max", start_max.isoformat()),
        ]
        for ref in project_refs or []:
            params.append(("project_ids[]", ref))
        for col in columns or []:
            params.append(("columns[]", col))
        if include_app_usage:
            params.append(("include_app_usage", "true"))
        return self._request("GET", "/report", params=params)


def _project_chain(project: dict[str, Any]) -> list[str]:
    chain = project.get("title_chain") or []
    if isinstance(chain, list) and chain:
        return [str(part) for part in chain]
    title = project.get("title")
    return [str(title)] if title else []


def _project_full_title(project: dict[str, Any]) -> str:
    return " / ".join(_project_chain(project)).strip()


def _project_leaf_title(project: dict[str, Any]) -> str:
    chain = _project_chain(project)
    if chain:
        return chain[-1].strip()
    return str(project.get("title") or "").strip()


def _project_ref(project: dict[str, Any]) -> str | None:
    ref = project.get("self") or project.get("url")
    if ref is not None:
        return str(ref)
    project_id = project.get("id")
    if project_id is None:
        return None
    project_ref = str(project_id)
    return project_ref if project_ref.startswith("/") else f"/projects/{project_ref}"


def _ambiguous_project_message(title: str, projects: list[dict[str, Any]]) -> str:
    labels = ", ".join(
        f"{_project_full_title(project) or _project_leaf_title(project)} ({_project_ref(project)})"
        for project in projects
    )
    return (
        f"Timing project '{title}' is ambiguous: {labels}. "
        "Add an explicit [project_mappings] entry in the config."
    )


def _parse_api_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text).astimezone()
    except ValueError:
        return None


def _entry_project_ref(entry: dict[str, Any]) -> str | None:
    project = entry.get("project")
    if isinstance(project, str):
        return project
    if isinstance(project, dict):
        return _project_ref(project)
    return None


def _time_entry_matches(
    entry: dict[str, Any],
    start: datetime,
    end: datetime,
    title: str,
    project_ref: str | None,
) -> bool:
    entry_start = _parse_api_datetime(entry.get("start_date") or entry.get("startDate"))
    entry_end = _parse_api_datetime(entry.get("end_date") or entry.get("endDate"))
    if entry_start is None or entry_end is None:
        return False

    same_start = abs((entry_start - start).total_seconds()) < 1
    same_end = abs((entry_end - end).total_seconds()) < 1
    same_title = (entry.get("title") or "") == title
    same_project = _entry_project_ref(entry) == project_ref
    return same_start and same_end and same_title and same_project
