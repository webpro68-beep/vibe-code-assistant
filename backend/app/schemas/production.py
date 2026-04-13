from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TimelineEventWrite(BaseModel):
    production_run_id: str | None = None
    project_id: str | None = None
    render_job_id: str | None = None
    trace_id: str | None = None
    title: str
    message: str | None = None
    phase: Literal["ingest", "render", "narration", "music", "mix", "mux", "publish", "operator"]
    stage: str
    event_type: str
    status: Literal["queued", "running", "succeeded", "failed", "blocked", "retried", "needs_review"]
    worker_name: str | None = None
    provider: str | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    is_blocking: bool = False
    is_operator_action: bool = False
    details: dict | None = None
    occurred_at: datetime | None = None


class ProductionTimelineEventRead(BaseModel):
    id: str
    production_run_id: str
    project_id: str | None = None
    render_job_id: str | None = None
    trace_id: str | None = None
    title: str
    message: str | None = None
    phase: str
    stage: str
    event_type: str
    status: str
    worker_name: str | None = None
    provider: str | None = None
    progress_percent: int | None = None
    is_blocking: bool = False
    is_operator_action: bool = False
    occurred_at: datetime
    details: dict | None = None


class ProductionRunRead(BaseModel):
    id: str
    project_id: str | None = None
    render_job_id: str | None = None
    trace_id: str | None = None
    title: str | None = None
    current_stage: str
    status: str
    percent_complete: int
    blocking_reason: str | None = None
    active_worker: str | None = None
    output_readiness: str
    output_url: str | None = None
    last_event_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ProductionRunDetail(BaseModel):
    run: ProductionRunRead
    timeline: list[ProductionTimelineEventRead]


class DashboardRunItem(BaseModel):
    id: str
    title: str | None = None
    render_job_id: str | None = None
    current_stage: str
    status: str
    percent_complete: int
    blocking_reason: str | None = None
    output_readiness: str
    active_worker: str | None = None
    last_event_at: datetime | None = None


class DashboardRunsResponse(BaseModel):
    items: list[DashboardRunItem]
