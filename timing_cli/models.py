"""Pydantic models shared across the CLI, DB layer, analysis and MCP server."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Project(BaseModel):
    """A Timing project, as read from the local database."""

    id: int
    title: str
    parent_id: int | None = None
    is_archived: bool = False
    color: str | None = None
    productivity_score: float = 0.0

    @property
    def api_ref(self) -> str:
        """Self-reference used by the Timing Web API (e.g. ``/projects/1``).

        NOTE: the local database ``id`` and the Web-API project id are NOT the
        same namespace. This helper only builds the API path shape; callers that
        push to the API must map local titles to remote project ids first (see
        ``timing_cli.api.TimingApiClient.resolve_project_ref``).
        """
        return f"/projects/{self.id}"


class AppUsage(BaseModel):
    """A single automatically recorded app-activity slice from the local DB."""

    id: int
    start: datetime
    end: datetime
    application_id: int | None = None
    app: str = Field(description="Human-readable app name or bundle identifier")
    bundle_id: str | None = None
    title: str | None = Field(default=None, description="Window title")
    path: str | None = Field(default=None, description="Document / file path")
    project_id: int | None = Field(default=None, description="Local Timing project id, if assigned")
    project_title: str | None = None
    project_title_chain: list[str] = Field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()


class TimeEntrySuggestion(BaseModel):
    """An aggregated block of app usage, ready to become a Timing time entry."""

    day: str = Field(description="ISO date (YYYY-MM-DD, local) the block belongs to")
    start: datetime
    end: datetime
    project_id: int | None = None
    project_title: str = "Unassigned"
    project_title_chain: list[str] = Field(default_factory=list)
    title: str = ""
    notes: str = ""
    source_count: int = 0
    top_apps: list[str] = Field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    @property
    def duration_minutes(self) -> float:
        return self.duration_seconds / 60.0


class ProjectSummary(BaseModel):
    """Aggregated time per project for a reporting window."""

    project_id: int | None = None
    project_title: str = "Unassigned"
    seconds: float = 0.0
    entries: int = 0

    @property
    def minutes(self) -> float:
        return self.seconds / 60.0

    @property
    def hours(self) -> float:
        return self.seconds / 3600.0
