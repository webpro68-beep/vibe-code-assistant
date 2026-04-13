from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.observability import (
    AutopilotDashboardResponse,
    KillSwitchResponse,
    KillSwitchUpdateRequest,
    NotificationDeliveryLogResponse,
    NotificationEndpointResponse,
    NotificationEndpointUpsertRequest,
    ObservabilityStatusResponse,
)
from app.services.kill_switch import get_or_create_global_kill_switch, set_global_kill_switch
from app.services.notification_plane import (
    list_notification_delivery_logs,
    list_notification_endpoints,
    send_notification_event,
    upsert_notification_endpoint,
)
from app.services.observability_metrics import build_autopilot_dashboard_snapshot, collect_status_snapshot, export_prometheus_text

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


@router.get("/status", response_model=ObservabilityStatusResponse)
async def get_observability_status(db: Session = Depends(get_db)):
    return collect_status_snapshot(db)


@router.get("/metrics", response_class=PlainTextResponse)
async def get_observability_metrics(db: Session = Depends(get_db)):
    snapshot = collect_status_snapshot(db)
    return PlainTextResponse(export_prometheus_text(snapshot), media_type="text/plain; version=0.0.4")


@router.get("/kill-switch", response_model=KillSwitchResponse)
async def get_kill_switch(db: Session = Depends(get_db)):
    row = get_or_create_global_kill_switch(db)
    return KillSwitchResponse(switch_name=row.switch_name, enabled=row.enabled, reason=row.reason, updated_by=row.updated_by)


@router.post("/kill-switch", response_model=KillSwitchResponse)
async def post_kill_switch(payload: KillSwitchUpdateRequest, db: Session = Depends(get_db)):
    row = set_global_kill_switch(db, actor=payload.actor, enabled=payload.enabled, reason=payload.reason)
    send_notification_event(
        db,
        event_type="kill_switch_changed",
        payload={"switch_name": row.switch_name, "enabled": row.enabled, "reason": row.reason, "updated_by": row.updated_by},
    )
    return KillSwitchResponse(switch_name=row.switch_name, enabled=row.enabled, reason=row.reason, updated_by=row.updated_by)


@router.get("/notification-endpoints", response_model=list[NotificationEndpointResponse])
async def get_notification_endpoints(db: Session = Depends(get_db)):
    rows = list_notification_endpoints(db)
    return [NotificationEndpointResponse(name=r.name, channel_type=r.channel_type, target=r.target, event_filter=r.event_filter, enabled=r.enabled, updated_by=r.updated_by) for r in rows]


@router.post("/notification-endpoints", response_model=NotificationEndpointResponse)
async def post_notification_endpoint(payload: NotificationEndpointUpsertRequest, db: Session = Depends(get_db)):
    row = upsert_notification_endpoint(
        db,
        actor=payload.actor,
        name=payload.name,
        channel_type=payload.channel_type,
        target=payload.target,
        event_filter=payload.event_filter,
        enabled=payload.enabled,
        secret=payload.secret,
    )
    return NotificationEndpointResponse(name=row.name, channel_type=row.channel_type, target=row.target, event_filter=row.event_filter, enabled=row.enabled, updated_by=row.updated_by)


@router.post("/notifications/test")
async def post_test_notification(payload: NotificationEndpointUpsertRequest, db: Session = Depends(get_db)):
    upsert_notification_endpoint(
        db,
        actor=payload.actor,
        name=payload.name,
        channel_type=payload.channel_type,
        target=payload.target,
        event_filter=payload.event_filter,
        enabled=payload.enabled,
        secret=payload.secret,
    )
    deliveries = send_notification_event(
        db,
        event_type="manual_test",
        payload={"message": "Manual notification test", "channel_type": payload.channel_type, "target": payload.target},
    )
    return {"delivery_count": len(deliveries)}


@router.get("/notification-deliveries", response_model=list[NotificationDeliveryLogResponse])
async def get_notification_deliveries(limit: int = 50, db: Session = Depends(get_db)):
    rows = list_notification_delivery_logs(db, limit=limit)
    return [
        NotificationDeliveryLogResponse(
            id=row.id,
            event_type=row.event_type,
            endpoint_name=row.endpoint_name,
            channel_type=row.channel_type,
            delivery_status=row.delivery_status,
            payload_json=row.payload_json,
            response_text=row.response_text,
            error_message=row.error_message,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/autopilot-dashboard", response_model=AutopilotDashboardResponse)
async def get_autopilot_dashboard(db: Session = Depends(get_db)):
    return AutopilotDashboardResponse(**build_autopilot_dashboard_snapshot(db))
