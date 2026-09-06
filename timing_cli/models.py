"""Pydantic models shared across the CLI, DB layer, analysis and MCP server."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer, computed_field

LocalId = Annotated[
    int,
    PlainSerializer(lambda value: str(value), return_type=str, when_used="json"),
]

MAX_ASSIGNMENT_ALTERNATIVES = 100
MAX_PROJECT_TITLE_CHAIN = 32
MAX_RECONSTRUCTION_PAGE_SIZE = 200
MAX_RECORD_REFERENCES = 200


class Project(BaseModel):
    """A Timing project, as read from the local database."""

    id: LocalId
    title: str
    parent_id: LocalId | None = None
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

    id: LocalId
    start: datetime
    end: datetime
    application_id: LocalId | None = None
    app: str = Field(description="Human-readable app name or bundle identifier")
    bundle_id: str | None = None
    title: str | None = Field(default=None, description="Window title")
    path: str | None = Field(default=None, description="Document / file path")
    project_id: LocalId | None = Field(
        default=None, description="Local Timing project id, if assigned"
    )
    project_title: str | None = None
    project_title_chain: list[str] = Field(default_factory=list)
    project_title_chain_complete: bool = Field(default=True, exclude=True)

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()


class ReconstructionSource(BaseModel):
    """One clipped booking or automatic-activity source row."""

    source_type: Literal["booking", "activity"]
    source_id: LocalId
    start: datetime
    end: datetime
    project_id: LocalId | None = None
    project_title: str | None = None
    project_title_chain: list[str] = Field(
        default_factory=list, max_length=MAX_PROJECT_TITLE_CHAIN
    )
    project_title_chain_complete: bool = True
    application_id: LocalId | None = None
    app: str | None = None
    bundle_id: str | None = None
    title: str | None = None
    path: str | None = None
    notes: str | None = None

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()


class AssignmentTarget(BaseModel):
    """A current or proposed local Timing project assignment."""

    project_id: LocalId | None = None
    project_title: str
    project_title_chain: list[str] = Field(
        default_factory=list, max_length=MAX_PROJECT_TITLE_CHAIN
    )
    project_title_chain_complete: bool = True


class AssignmentAlternative(AssignmentTarget):
    """One matching rule or predicate with observable match evidence."""

    origin: Literal["user_rule", "packaged_rule", "timing_predicate"]
    rule_id: str
    matched_field: str
    matched_value: str
    criterion: str


class AssignmentExplanation(BaseModel):
    """Bounded explanation for an existing, proposed, or unresolved assignment."""

    existing_assignment: AssignmentTarget | None = None
    selected_assignment: AssignmentTarget | None = None
    origin: Literal[
        "existing", "user_rule", "packaged_rule", "timing_predicate", "unresolved"
    ]
    rule_id: str | None = None
    matched_field: str | None = None
    matched_value: str | None = None
    source_references: list[str] = Field(max_length=4)
    alternatives: list[AssignmentAlternative] = Field(max_length=MAX_ASSIGNMENT_ALTERNATIVES)
    alternatives_complete: bool = True
    conflicts: list[AssignmentAlternative] = Field(max_length=MAX_ASSIGNMENT_ALTERNATIVES)
    conflicts_complete: bool = True
    uncertainty_reason: str | None = None


class EvidenceInterval(BaseModel):
    """One exact half-open interval derived from a single source record."""

    start: datetime
    end: datetime

    @computed_field
    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()


class ReconstructionRecord(BaseModel):
    """One page-scoped source record with window-derived relationships."""

    metric_scope: Literal["record"] = "record"
    source: ReconstructionSource
    assignment: AssignmentExplanation
    supporting_activity_references: list[str] = Field(
        default_factory=list, max_length=MAX_RECORD_REFERENCES
    )
    supporting_activity_references_complete: bool = True
    covered_by_booking_references: list[str] = Field(
        default_factory=list, max_length=MAX_RECORD_REFERENCES
    )
    covered_by_booking_references_complete: bool = True
    conflict_references: list[str] = Field(
        default_factory=list, max_length=MAX_RECORD_REFERENCES
    )
    conflict_references_complete: bool = True
    candidate_intervals: list[EvidenceInterval] = Field(
        default_factory=list, max_length=MAX_RECORD_REFERENCES
    )
    candidate_intervals_complete: bool = True


class ReconstructionMetrics(BaseModel):
    """Whole-window metrics with deliberately separate duration semantics."""

    scope: Literal["window"] = "window"
    raw_cumulative_activity_seconds: float
    activity_interval_union_seconds: float
    elapsed_evidence_span_seconds: float
    gap_seconds: float
    recorded_service_seconds: float
    uncovered_candidate_seconds: float


class ReconstructionEvidence(BaseModel):
    """Analyzed evidence for one bounded page and the complete window metrics."""

    records: list[ReconstructionRecord] = Field(max_length=MAX_RECONSTRUCTION_PAGE_SIZE)
    metrics: ReconstructionMetrics


class ReconstructionWindow(BaseModel):
    """Requested local half-open window and extraction provenance."""

    timezone: str
    interval_semantics: Literal["half-open"] = "half-open"
    start: datetime
    end: datetime
    extracted_at: datetime


class ReconstructionPagination(BaseModel):
    """Stable continuation metadata for the bounded record collection."""

    limit: int = Field(ge=1, le=MAX_RECONSTRUCTION_PAGE_SIZE)
    stable_order: list[str] = Field(
        default_factory=lambda: ["start", "source_type", "source_id"],
        min_length=3,
        max_length=3,
    )
    total_count: int = Field(ge=0)
    returned_count: int = Field(ge=0, le=MAX_RECONSTRUCTION_PAGE_SIZE)
    complete: bool
    next_cursor: str | None = None


class ReconstructionResponse(BaseModel):
    """Versioned wire contract shared by the CLI and MCP tool."""

    schema_version: Literal["timing.reconstruction.v1"] = "timing.reconstruction.v1"
    window: ReconstructionWindow
    pagination: ReconstructionPagination
    metrics: ReconstructionMetrics
    records: list[ReconstructionRecord] = Field(max_length=MAX_RECONSTRUCTION_PAGE_SIZE)


class TimeEntrySuggestion(BaseModel):
    """An aggregated block of app usage, ready to become a Timing time entry."""

    day: str = Field(description="ISO date (YYYY-MM-DD, local) the block belongs to")
    start: datetime
    end: datetime
    project_id: LocalId | None = None
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

    project_id: LocalId | None = None
    project_title: str = "Unassigned"
    seconds: float = 0.0
    entries: int = 0

    @property
    def minutes(self) -> float:
        return self.seconds / 60.0

    @property
    def hours(self) -> float:
        return self.seconds / 3600.0
