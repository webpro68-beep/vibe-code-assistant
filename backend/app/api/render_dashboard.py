from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.render_job import RenderJob
from app.schemas.render_dashboard_incidents import RecentIncidentsResponse
from app.schemas.render_dashboard_summary import RenderDashboardSummaryResponse
from app.schemas.render_incident_history import IncidentHistoryResponse, IncidentNoteResponse, IncidentNoteUpdateRequest
from app.schemas.render_job_list import RenderJobListItem, RenderJobListPage
from app.schemas.render_access_control import RenderAccessProfileListResponse, RenderAccessProfileResponse, RenderAccessProfileUpdateRequest
from app.schemas.render_bulk_audit import BulkActionAuditDetailResponse, BulkActionAuditListResponse, BulkActionAuditRun
from app.schemas.render_productivity import ProductivityBoardResponse, ProductivityTrendsResponse
from app.schemas.render_incident_saved_views import BulkIncidentActionRequest, BulkIncidentActionResponse, BulkIncidentActionResult, IncidentSavedViewCreateRequest, IncidentSavedViewListResponse, IncidentSavedViewResponse, IncidentSavedViewUpdateRequest
from app.schemas.render_incident_work_surface import BulkPreviewRequest, BulkPreviewResponse, IncidentSegmentMetricsResponse
from app.services.render_dashboard_summary import get_recent_incidents, get_render_dashboard_summary
from app.services.render_incident_history import get_incident_history, update_incident_note
from app.services.render_incident_projector import apply_incident_action
from app.services.render_access_control import ensure_access, get_or_create_access_profile, list_access_profiles, update_access_profile
from app.services.render_incident_bulk_audit import create_bulk_action_run, finalize_bulk_action_run, get_bulk_action_run_detail, list_bulk_action_runs
from app.services.render_incident_saved_views import create_saved_view, delete_saved_view, list_saved_views, update_saved_view
from app.services.render_incident_work_surface import get_incident_segment_metrics, preview_bulk_action
from app.services.render_productivity_board import get_productivity_board
from app.schemas.render_console_explainability import BulkGuardrailEvaluationResponse, SavedViewEffectiveAccessResponse
from app.services.render_console_explainability import evaluate_bulk_guardrails, get_productivity_trend_windows, get_saved_view_effective_access_preview

router = APIRouter(prefix="/api/v1/render/dashboard", tags=["render-dashboard"])




@router.get("/access-profiles", response_model=RenderAccessProfileListResponse)
async def get_access_profiles(actor: str = Query(...), team_only: bool = Query(False), db: Session = Depends(get_db)):
    return RenderAccessProfileListResponse(items=[RenderAccessProfileResponse(**i) for i in list_access_profiles(db, actor=actor, team_only=team_only)])


@router.put("/access-profiles/{target_actor}", response_model=RenderAccessProfileResponse)
async def put_access_profile(target_actor: str, payload: RenderAccessProfileUpdateRequest, actor: str = Query(...), db: Session = Depends(get_db)):
    try:
        row = update_access_profile(db, actor=actor, target_actor_id=target_actor, patch=payload.model_dump(exclude_none=True))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not row:
        raise HTTPException(status_code=404, detail="Access profile not found")
    return RenderAccessProfileResponse(**row)


@router.get("/incidents/productivity", response_model=ProductivityBoardResponse)
async def get_incident_productivity(actor: str = Query(...), days: int = Query(7, ge=1, le=30), db: Session = Depends(get_db)):
    ensure_access(db, actor=actor, minimum_role="team_lead")
    return ProductivityBoardResponse(**get_productivity_board(db, actor=actor, days=days))

@router.get("/access-profile", response_model=RenderAccessProfileResponse)
async def get_access_profile(actor: str = Query(...), db: Session = Depends(get_db)):
    return RenderAccessProfileResponse(**get_or_create_access_profile(db, actor=actor))


@router.get("/incidents/productivity/trends", response_model=ProductivityTrendsResponse)
async def get_incident_productivity_trends(actor: str = Query(...), windows: str = Query("1,7,14"), db: Session = Depends(get_db)):
    ensure_access(db, actor=actor, minimum_role="team_lead")
    parsed = [int(part) for part in windows.split(",") if part.strip().isdigit()] or [1, 7, 14]
    return ProductivityTrendsResponse(**get_productivity_trend_windows(db, actor=actor, windows=parsed))


@router.get("/incidents/views/{view_id}/effective-access", response_model=SavedViewEffectiveAccessResponse)
async def get_incident_saved_view_effective_access(view_id: str, actor: str = Query(...), db: Session = Depends(get_db)):
    preview = get_saved_view_effective_access_preview(db, view_id=view_id, actor=actor)
    if not preview:
        raise HTTPException(status_code=404, detail="Saved view not found")
    return SavedViewEffectiveAccessResponse(**preview)


@router.post("/incidents/bulk/{action_type}/guardrails", response_model=BulkGuardrailEvaluationResponse)
async def get_bulk_incident_guardrails(action_type: str, payload: BulkPreviewRequest, db: Session = Depends(get_db)):
    if action_type not in {"acknowledge", "assign", "mute", "resolve"}:
        raise HTTPException(status_code=400, detail="Unsupported bulk guardrail action")
    ensure_access(db, actor=payload.actor, minimum_role="operator")
    return BulkGuardrailEvaluationResponse(**evaluate_bulk_guardrails(db, actor=payload.actor, action_type=action_type, incident_keys=payload.incident_keys))


@router.get("/incidents/bulk/history", response_model=BulkActionAuditListResponse)
async def list_bulk_incident_action_history(actor: str = Query(...), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    profile = get_or_create_access_profile(db, actor=actor)
    team_id = profile.get("team_id") if profile.get("role") in {"team_lead", "admin"} else None
    items = list_bulk_action_runs(db, actor=None if profile.get("role") in {"team_lead", "admin"} else actor, team_id=team_id, limit=limit)
    return BulkActionAuditListResponse(items=[BulkActionAuditRun(**i) for i in items])


@router.get("/incidents/bulk/history/{run_id}", response_model=BulkActionAuditDetailResponse)
async def get_bulk_incident_action_history_detail(run_id: str, actor: str = Query(...), db: Session = Depends(get_db)):
    profile = get_or_create_access_profile(db, actor=actor)
    detail = get_bulk_action_run_detail(db, run_id=run_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Bulk action run not found")
    run = detail["run"]
    if profile.get("role") not in {"team_lead", "admin"} and run.get("actor") != actor:
        raise HTTPException(status_code=403, detail="Forbidden")
    return BulkActionAuditDetailResponse(**detail)


class IncidentActionRequest(BaseModel):
    actor: str
    reason: str | None = None
    assigned_to: str | None = None
    muted_until: datetime | None = None


@router.get("/jobs", response_model=RenderJobListPage)
async def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    provider: str | None = None,
    health_status: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(RenderJob).order_by(RenderJob.created_at.desc())
    if provider:
        q = q.filter(RenderJob.provider == provider)
    if health_status:
        q = q.filter(RenderJob.health_status == health_status)
    items = q.limit(limit).all()
    return RenderJobListPage(
        items=[
            RenderJobListItem(
                id=j.id,
                project_id=j.project_id,
                provider=j.provider,
                status=j.status,
                health_status=j.health_status,
                health_reason=j.health_reason,
                aspect_ratio=j.aspect_ratio,
                style_preset=j.style_preset,
                subtitle_mode=j.subtitle_mode,
                planned_scene_count=j.planned_scene_count,
                processing_scene_count=j.processing_scene_count,
                succeeded_scene_count=j.completed_scene_count,
                failed_scene_count_snapshot=j.failed_scene_count_snapshot,
                stalled_scene_count=j.stalled_scene_count,
                degraded_scene_count=j.degraded_scene_count,
                active_scene_count=j.active_scene_count,
                created_at=j.created_at,
                updated_at=j.updated_at,
                last_event_at=j.last_event_at,
                last_health_transition_at=j.last_health_transition_at,
            )
            for j in items
        ],
        total=len(items),
        limit=limit,
    )


@router.get("/summary", response_model=RenderDashboardSummaryResponse)
async def dashboard_summary(db: Session = Depends(get_db)):
    return RenderDashboardSummaryResponse(**get_render_dashboard_summary(db))


@router.get("/incidents/recent", response_model=RecentIncidentsResponse)
async def recent_incidents(
    limit: int = Query(20, ge=1, le=200),
    provider: str | None = Query(None),
    workflow_status: str | None = Query(None),
    assigned_to: str | None = Query(None),
    segment: str | None = Query(None),
    show_muted: bool = Query(False),
    db: Session = Depends(get_db),
):
    return RecentIncidentsResponse(**get_recent_incidents(db, limit=limit, provider=provider, workflow_status=workflow_status, assigned_to=assigned_to, segment=segment, show_muted=show_muted))




@router.get("/incidents/metrics", response_model=IncidentSegmentMetricsResponse)
async def get_incident_metrics(
    provider: str | None = Query(None),
    show_muted: bool = Query(False),
    assignee: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return IncidentSegmentMetricsResponse(**get_incident_segment_metrics(db, provider=provider, show_muted=show_muted, assignee=assignee))


@router.post("/incidents/bulk/{action_type}/preview", response_model=BulkPreviewResponse)
async def preview_bulk_incident_action(action_type: str, payload: BulkPreviewRequest, db: Session = Depends(get_db)):
    if action_type not in {"acknowledge", "assign", "mute", "resolve"}:
        raise HTTPException(status_code=400, detail="Unsupported bulk preview action")
    profile = ensure_access(db, actor=payload.actor, minimum_role="operator")
    guardrails = evaluate_bulk_guardrails(db, actor=payload.actor, action_type=action_type, incident_keys=payload.incident_keys)
    preview = preview_bulk_action(db, action_type=action_type, incident_keys=payload.incident_keys, assigned_to=payload.assigned_to, muted_until=payload.muted_until)
    preview["guardrails"] = guardrails
    run = create_bulk_action_run(db, action_type=action_type, actor=payload.actor, actor_role=profile.get("role", "operator"), actor_team_id=profile.get("team_id"), mode="preview", reason=payload.reason, filters={}, request={"incident_keys": payload.incident_keys, "assigned_to": payload.assigned_to, "muted_until": payload.muted_until.isoformat() if payload.muted_until else None})
    finalize_bulk_action_run(db, run=run, results=[{**item, "ok": item.get("eligible", False), "status": item.get("predicted_status"), "error": None if item.get("eligible", False) else item.get("reason")} for item in preview.get("items", [])])
    return BulkPreviewResponse(**preview)

@router.get("/incidents/views", response_model=IncidentSavedViewListResponse)
async def list_incident_saved_views(actor: str | None = Query(None), db: Session = Depends(get_db)):
    return IncidentSavedViewListResponse(items=[IncidentSavedViewResponse(**item) for item in list_saved_views(db, actor=actor)])


@router.post("/incidents/views", response_model=IncidentSavedViewResponse)
async def create_incident_saved_view(payload: IncidentSavedViewCreateRequest, db: Session = Depends(get_db)):
    row = create_saved_view(db, owner_actor=payload.owner_actor, name=payload.name, description=payload.description, is_shared=payload.is_shared, share_scope=payload.share_scope, shared_team_id=payload.shared_team_id, allowed_roles=payload.allowed_roles, filters=payload.filters.model_dump(), sort_key=payload.sort_key)
    return IncidentSavedViewResponse(**row)


@router.put("/incidents/views/{view_id}", response_model=IncidentSavedViewResponse)
async def update_incident_saved_view(view_id: str, payload: IncidentSavedViewUpdateRequest, actor: str = Query(...), db: Session = Depends(get_db)):
    row = update_saved_view(db, view_id=view_id, actor=actor, patch=payload.model_dump(exclude_none=True))
    if not row:
        raise HTTPException(status_code=404, detail="Saved view not found")
    return IncidentSavedViewResponse(**row)


@router.delete("/incidents/views/{view_id}")
async def delete_incident_saved_view(view_id: str, actor: str = Query(...), db: Session = Depends(get_db)):
    ok = delete_saved_view(db, view_id=view_id, actor=actor)
    if not ok:
        raise HTTPException(status_code=404, detail="Saved view not found")
    return {"ok": True, "view_id": view_id}


async def _run_bulk_action(action_type: str, payload: BulkIncidentActionRequest, db: Session) -> BulkIncidentActionResponse:
    profile = ensure_access(db, actor=payload.actor, minimum_role="operator")
    guardrails = evaluate_bulk_guardrails(db, actor=payload.actor, action_type=action_type, incident_keys=payload.incident_keys)
    if not guardrails.get("ok"):
        raise HTTPException(status_code=403, detail={"message": "Bulk action blocked by guardrails", "guardrails": guardrails})
    items: list[BulkIncidentActionResult] = []
    succeeded = 0
    run = create_bulk_action_run(db, action_type=action_type, actor=payload.actor, actor_role=profile.get("role", "operator"), actor_team_id=profile.get("team_id"), mode="apply", reason=payload.reason, filters={}, request={"incident_keys": payload.incident_keys, "assigned_to": payload.assigned_to, "muted_until": payload.muted_until.isoformat() if payload.muted_until else None})
    for incident_key in payload.incident_keys:
        try:
            extra = {}
            if action_type == "assign":
                extra = {"assigned_to": payload.assigned_to}
            elif action_type == "mute":
                extra = {"muted_until": payload.muted_until}
            state = apply_incident_action(db, incident_key=incident_key, action_type=action_type, actor=payload.actor, reason=payload.reason, payload=extra)
            if not state:
                items.append(BulkIncidentActionResult(incident_key=incident_key, ok=False, error="Incident not found"))
                continue
            items.append(BulkIncidentActionResult(incident_key=incident_key, ok=True, status=state.status))
            succeeded += 1
        except Exception as exc:
            items.append(BulkIncidentActionResult(incident_key=incident_key, ok=False, error=str(exc)))
    finalize_bulk_action_run(db, run=run, results=[i.model_dump() for i in items])
    return BulkIncidentActionResponse(action_type=action_type, attempted=len(payload.incident_keys), succeeded=succeeded, failed=len(payload.incident_keys) - succeeded, items=items)


@router.post("/incidents/bulk/acknowledge", response_model=BulkIncidentActionResponse)
async def bulk_acknowledge_incidents(payload: BulkIncidentActionRequest, db: Session = Depends(get_db)):
    return await _run_bulk_action("acknowledge", payload, db)


@router.post("/incidents/bulk/assign", response_model=BulkIncidentActionResponse)
async def bulk_assign_incidents(payload: BulkIncidentActionRequest, db: Session = Depends(get_db)):
    return await _run_bulk_action("assign", payload, db)


@router.post("/incidents/bulk/mute", response_model=BulkIncidentActionResponse)
async def bulk_mute_incidents(payload: BulkIncidentActionRequest, db: Session = Depends(get_db)):
    return await _run_bulk_action("mute", payload, db)


@router.post("/incidents/bulk/resolve", response_model=BulkIncidentActionResponse)
async def bulk_resolve_incidents(payload: BulkIncidentActionRequest, db: Session = Depends(get_db)):
    return await _run_bulk_action("resolve", payload, db)


@router.post("/incidents/{incident_key}/acknowledge")
async def acknowledge_incident(incident_key: str, payload: IncidentActionRequest, db: Session = Depends(get_db)):
    state = apply_incident_action(db, incident_key=incident_key, action_type="acknowledge", actor=payload.actor, reason=payload.reason)
    if not state:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"ok": True, "incident_key": state.incident_key, "status": state.status}


@router.post("/incidents/{incident_key}/assign")
async def assign_incident(incident_key: str, payload: IncidentActionRequest, db: Session = Depends(get_db)):
    state = apply_incident_action(db, incident_key=incident_key, action_type="assign", actor=payload.actor, reason=payload.reason, payload={"assigned_to": payload.assigned_to})
    if not state:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"ok": True, "incident_key": state.incident_key, "status": state.status, "assigned_to": state.assigned_to}


@router.post("/incidents/{incident_key}/mute")
async def mute_incident(incident_key: str, payload: IncidentActionRequest, db: Session = Depends(get_db)):
    state = apply_incident_action(db, incident_key=incident_key, action_type="mute", actor=payload.actor, reason=payload.reason, payload={"muted_until": payload.muted_until})
    if not state:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"ok": True, "incident_key": state.incident_key, "status": state.status, "muted_until": state.muted_until}


@router.post("/incidents/{incident_key}/resolve")
async def resolve_incident(incident_key: str, payload: IncidentActionRequest, db: Session = Depends(get_db)):
    state = apply_incident_action(db, incident_key=incident_key, action_type="resolve", actor=payload.actor, reason=payload.reason)
    if not state:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"ok": True, "incident_key": state.incident_key, "status": state.status, "resolved_at": state.resolved_at}


@router.post("/incidents/{incident_key}/reopen")
async def reopen_incident(incident_key: str, payload: IncidentActionRequest, db: Session = Depends(get_db)):
    state = apply_incident_action(db, incident_key=incident_key, action_type="reopen", actor=payload.actor, reason=payload.reason)
    if not state:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"ok": True, "incident_key": state.incident_key, "status": state.status, "reopen_count": state.reopen_count}


@router.get("/incidents/{incident_key}", response_model=IncidentHistoryResponse)
async def get_incident_detail(incident_key: str, db: Session = Depends(get_db)):
    detail = get_incident_history(db, incident_key)
    if not detail:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentHistoryResponse(**detail)


@router.get("/incidents/{incident_key}/history", response_model=IncidentHistoryResponse)
async def get_incident_history_route(incident_key: str, db: Session = Depends(get_db)):
    detail = get_incident_history(db, incident_key)
    if not detail:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentHistoryResponse(**detail)


@router.put("/incidents/{incident_key}/note", response_model=IncidentNoteResponse)
async def update_incident_note_route(incident_key: str, payload: IncidentNoteUpdateRequest, db: Session = Depends(get_db)):
    state = update_incident_note(db, incident_key=incident_key, actor=payload.actor, note=payload.note)
    if not state:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentNoteResponse(incident_key=state.incident_key, note=state.note, updated_at=state.updated_at)
