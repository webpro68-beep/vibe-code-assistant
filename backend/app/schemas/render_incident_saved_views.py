
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class IncidentListFilters(BaseModel):
    provider: str | None = None
    workflow_status: str | None = None
    assigned_to: str | None = None
    segment: str | None = None
    show_muted: bool = False
    limit: int = 20


class IncidentSavedViewCreateRequest(BaseModel):
    owner_actor: str
    name: str
    description: str | None = None
    is_shared: bool = False
    share_scope: str = "private"
    shared_team_id: str | None = None
    allowed_roles: list[str] = Field(default_factory=list)
    filters: IncidentListFilters = Field(default_factory=IncidentListFilters)
    sort_key: str | None = None


class IncidentSavedViewUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_shared: bool | None = None
    share_scope: str | None = None
    shared_team_id: str | None = None
    allowed_roles: list[str] | None = None
    filters: IncidentListFilters | None = None
    sort_key: str | None = None


class IncidentSavedViewResponse(BaseModel):
    id: str
    owner_actor: str
    name: str
    description: str | None = None
    is_shared: bool = False
    share_scope: str = "private"
    shared_team_id: str | None = None
    allowed_roles: list[str] = Field(default_factory=list)
    filters: IncidentListFilters
    sort_key: str | None = None
    created_at: datetime
    updated_at: datetime


class IncidentSavedViewListResponse(BaseModel):
    items: list[IncidentSavedViewResponse] = Field(default_factory=list)


class BulkIncidentActionRequest(BaseModel):
    actor: str
    incident_keys: list[str] = Field(default_factory=list)
    reason: str | None = None
    assigned_to: str | None = None
    muted_until: datetime | None = None


class BulkIncidentActionResult(BaseModel):
    incident_key: str
    ok: bool
    status: str | None = None
    error: str | None = None


class BulkIncidentActionResponse(BaseModel):
    ok: bool = True
    action_type: str
    attempted: int
    succeeded: int
    failed: int
    items: list[BulkIncidentActionResult] = Field(default_factory=list)
