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
        params = {"hide_archived": "true" if hide_archived else "false"}
        data = self._request("GET", "/projects", params=params)
        return data.get("data", []) if isinstance(data, dict) else (data or [])

    def find_project_ref(self, title: str) -> str | None:
        """Return the API self-reference (e.g. ``/projects/3``) for a title.

        Matches the leaf title case-insensitively. Returns None if not found,
        so callers can decide whether to create the project or skip.
        """
        target = title.strip().lower()
        for project in self.list_projects(hide_archived=False):
            leaf = (project.get("title") or "").strip().lower()
            chain = project.get("title_chain") or []
            chain_leaf = (chain[-1] if chain else "").strip().lower()
            if target in (leaf, chain_leaf):
                return project.get("self")
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
