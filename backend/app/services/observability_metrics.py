from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.autopilot_execution_state import AutopilotExecutionState
from app.models.decision_execution_audit_log import DecisionExecutionAuditLog
from app.models.global_kill_switch import GlobalKillSwitch
from app.models.notification_delivery_log import NotificationDeliveryLog
from app.models.provider_routing_override import ProviderRoutingOverride
from app.models.release_gate_state import ReleaseGateState
from app.models.render_incident_state import RenderIncidentState
from app.models.render_job import RenderJob
from app.models.worker_concurrency_override import WorkerConcurrencyOverride
from app.schemas.observability import MetricSample, ObservabilityStatusResponse
from app.services.control_plane import get_or_create_release_gate, get_or_create_worker_override
from app.services.kill_switch import get_or_create_global_kill_switch


def collect_status_snapshot(db: Session) -> ObservabilityStatusResponse:
    now = datetime.utcnow()
    metrics: list[MetricSample] = []

    job_rows = db.query(RenderJob.status, func.count(RenderJob.id)).group_by(RenderJob.status).all()
    for status, count in job_rows:
        metrics.append(MetricSample(name="render_jobs_total", value=float(count), labels={"status": status or "unknown"}))

    incident_rows = db.query(RenderIncidentState.status, func.count(RenderIncidentState.id)).group_by(RenderIncidentState.status).all()
    for status, count in incident_rows:
        metrics.append(MetricSample(name="render_incidents_total", value=float(count), labels={"status": status or "unknown"}))

    active_provider_overrides = db.query(ProviderRoutingOverride).filter(ProviderRoutingOverride.active.is_(True)).count()
    metrics.append(MetricSample(name="provider_overrides_active", value=float(active_provider_overrides)))

    release_gate = get_or_create_release_gate(db)
    kill_switch = get_or_create_global_kill_switch(db)
    worker_override = get_or_create_worker_override(db)

    metrics.append(MetricSample(name="release_gate_blocked", value=1.0 if release_gate.blocked else 0.0))
    metrics.append(MetricSample(name="global_kill_switch_enabled", value=1.0 if kill_switch.enabled else 0.0))
    metrics.append(MetricSample(name="dispatch_batch_limit", value=float(worker_override.dispatch_batch_limit)))
    metrics.append(MetricSample(name="dispatch_poll_countdown_seconds", value=float(worker_override.poll_countdown_seconds)))

    cutoff = now - timedelta(hours=24)
    notif_failures = db.query(NotificationDeliveryLog).filter(
        NotificationDeliveryLog.created_at >= cutoff,
        NotificationDeliveryLog.delivery_status.in_(["failed", "rejected"]),
    ).count()
    metrics.append(MetricSample(name="notification_failures_last_24h", value=float(notif_failures)))

    autopilot_latest = db.query(func.max(AutopilotExecutionState.last_executed_at)).scalar()
    state_rows = db.query(AutopilotExecutionState.last_status, func.count(AutopilotExecutionState.id)).group_by(AutopilotExecutionState.last_status).all()
    for status, count in state_rows:
        metrics.append(MetricSample(name="autopilot_states_total", value=float(count), labels={"status": status or "unknown"}))

    return ObservabilityStatusResponse(
        generated_at=now,
        metrics=metrics,
        release_gate_blocked=release_gate.blocked,
        global_kill_switch_enabled=kill_switch.enabled,
        active_provider_overrides=active_provider_overrides,
        notification_failures_last_24h=notif_failures,
        autopilot_last_execution_at=autopilot_latest.isoformat() if autopilot_latest else None,
    )


def export_prometheus_text(snapshot: ObservabilityStatusResponse) -> str:
    lines: list[str] = []
    for metric in snapshot.metrics:
        if metric.labels:
            labels = ",".join(f'{key}="{value}"' for key, value in sorted(metric.labels.items()))
            lines.append(f'{metric.name}{{{labels}}} {metric.value}')
        else:
            lines.append(f"{metric.name} {metric.value}")
    return "\n".join(lines) + "\n"


def build_autopilot_dashboard_snapshot(db: Session) -> dict:
    status = collect_status_snapshot(db)
    worker_override = get_or_create_worker_override(db)
    latest_audits = (
        db.query(DecisionExecutionAuditLog)
        .order_by(DecisionExecutionAuditLog.created_at.desc())
        .limit(20)
        .all()
    )
    latest_deliveries = (
        db.query(NotificationDeliveryLog)
        .order_by(NotificationDeliveryLog.created_at.desc())
        .limit(20)
        .all()
    )
    state_rows = db.query(AutopilotExecutionState.last_status, func.count(AutopilotExecutionState.id)).group_by(AutopilotExecutionState.last_status).all()
    return {
        "generated_at": status.generated_at,
        "kill_switch_enabled": status.global_kill_switch_enabled,
        "release_gate_blocked": status.release_gate_blocked,
        "active_provider_overrides": status.active_provider_overrides,
        "worker_dispatch_batch_limit": worker_override.dispatch_batch_limit,
        "worker_poll_countdown_seconds": worker_override.poll_countdown_seconds,
        "autopilot_states": {status: count for status, count in state_rows},
        "latest_decision_audits": [
            {
                "decision_type": row.decision_type,
                "execution_status": row.execution_status,
                "actor": row.actor,
                "reason": row.reason,
                "created_at": row.created_at.isoformat(),
                "recommendation_key": row.recommendation_key,
            }
            for row in latest_audits
        ],
        "latest_notification_deliveries": [
            {
                "event_type": row.event_type,
                "endpoint_name": row.endpoint_name,
                "channel_type": row.channel_type,
                "delivery_status": row.delivery_status,
                "created_at": row.created_at.isoformat(),
                "error_message": row.error_message,
            }
            for row in latest_deliveries
        ],
    }
