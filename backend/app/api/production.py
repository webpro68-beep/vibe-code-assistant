from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.production import (
    DashboardRunsResponse,
    ProductionRunDetail,
    TimelineEventWrite,
)
from app.state import timeline_service

router = APIRouter(prefix="/api/v1", tags=["production"])


@router.get("/render-jobs/{render_job_id}/timeline", response_model=ProductionRunDetail)
def get_render_job_timeline(render_job_id: str):
    detail = timeline_service.get_run_by_render_job(render_job_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Render job timeline not found")
    return detail


@router.get("/render-jobs/{render_job_id}/status-detail", response_model=ProductionRunDetail)
def get_render_job_status_detail(render_job_id: str):
    detail = timeline_service.get_run_by_render_job(render_job_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Render job status detail not found")
    return detail


@router.get("/dashboard/production-runs", response_model=DashboardRunsResponse)
def get_dashboard_runs():
    return {"items": timeline_service.list_dashboard_runs()}


@router.post("/production/events")
def create_production_event(payload: TimelineEventWrite):
    event = timeline_service.write_event(payload.model_dump())
    return event
