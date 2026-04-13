from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class SegmentMetricItem(BaseModel):
    segment: str
    total: int
    unacknowledged: int = 0
    assigned: int = 0
    muted: int = 0
    resolved: int = 0
    stale_over_30m: int = 0
    high_severity: int = 0


class IncidentSegmentMetricsResponse(BaseModel):
    generated_at: datetime
    provider: str | None = None
    show_muted: bool = False
    items: list[SegmentMetricItem] = Field(default_factory=list)


class BulkPreviewItem(BaseModel):
    incident_key: str
    current_status: str | None = None
    assigned_to: str | None = None
    muted: bool = False
    acknowledged: bool = False
    eligible: bool = True
    reason: str | None = None
    predicted_status: str | None = None
    predicted_assigned_to: str | None = None
    predicted_muted_until: datetime | None = None


class BulkPreviewRequest(BaseModel):
    actor: str
    incident_keys: list[str] = Field(default_factory=list)
    reason: str | None = None
    assigned_to: str | None = None
    muted_until: datetime | None = None


class BulkPreviewResponse(BaseModel):
    ok: bool = True
    action_type: str
    attempted: int
    eligible: int
    skipped: int
    items: list[BulkPreviewItem] = Field(default_factory=list)
    guardrails: dict = Field(default_factory=dict)
