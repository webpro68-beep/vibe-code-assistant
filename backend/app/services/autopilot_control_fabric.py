from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.autopilot_execution_state import AutopilotExecutionState
from app.models.provider_routing_override import ProviderRoutingOverride
from app.models.release_gate_state import ReleaseGateState
from app.schemas.decision_engine import DecisionEvaluationResponse, DecisionRecommendation
from app.services.control_plane import create_decision_audit_log, get_or_create_release_gate
from app.services.kill_switch import get_or_create_global_kill_switch
from app.services.notification_plane import send_notification_event
from app.services.decision_engine import evaluate_decision_policy, execute_decision, load_decision_policy


def _utcnow() -> datetime:
    return datetime.utcnow()


def get_or_create_autopilot_state(
    db: Session,
    *,
    decision_type: str,
    recommendation_key: str | None,
) -> AutopilotExecutionState:
    row = (
        db.query(AutopilotExecutionState)
        .filter(
            AutopilotExecutionState.decision_type == decision_type,
            AutopilotExecutionState.recommendation_key == recommendation_key,
        )
        .first()
    )
    if row:
        return row
    row = AutopilotExecutionState(
        id=str(uuid.uuid4()),
        decision_type=decision_type,
        recommendation_key=recommendation_key,
        last_status="new",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _policy_autopilot() -> dict[str, Any]:
    return load_decision_policy().get("autopilot", {})


def _cooldown_delta(decision_type: str) -> timedelta:
    minutes = int(_policy_autopilot().get("cooldown_minutes_by_decision_type", {}).get(decision_type, 15))
    return timedelta(minutes=max(1, minutes))


def _suppression_delta() -> timedelta:
    minutes = int(_policy_autopilot().get("suppression_window_minutes", 30))
    return timedelta(minutes=max(1, minutes))


def _provider_override_expiry_delta() -> timedelta:
    minutes = int(_policy_autopilot().get("provider_override_default_expiry_minutes", 120))
    return timedelta(minutes=max(5, minutes))


def _release_unblock_delta() -> timedelta:
    minutes = int(_policy_autopilot().get("release_unblock_minutes_after_last_critical_incident", 60))
    return timedelta(minutes=max(5, minutes))


def _safe_auto_execute_decision_types() -> set[str]:
    return set(_policy_autopilot().get("safe_auto_execute_decision_types", []))


def should_auto_execute(
    db: Session,
    *,
    recommendation: DecisionRecommendation,
    now: datetime | None = None,
) -> tuple[bool, str]:
    now = now or _utcnow()
    state = get_or_create_autopilot_state(
        db,
        decision_type=recommendation.decision_type,
        recommendation_key=recommendation.decision_key,
    )
    state.last_evaluated_at = now
    db.commit()

    if recommendation.decision_type not in _safe_auto_execute_decision_types():
        return False, "decision_type_not_whitelisted"

    if state.cooldown_until and state.cooldown_until > now:
        return False, "cooldown_active"

    if state.suppression_until and state.suppression_until > now:
        return False, "suppression_active"

    return True, "safe_to_execute"


def record_autopilot_state(
    db: Session,
    *,
    recommendation: DecisionRecommendation,
    status: str,
    reason: str | None,
    now: datetime | None = None,
) -> AutopilotExecutionState:
    now = now or _utcnow()
    state = get_or_create_autopilot_state(
        db,
        decision_type=recommendation.decision_type,
        recommendation_key=recommendation.decision_key,
    )
    state.last_status = status
    state.last_reason = reason
    state.last_evaluated_at = now
    if status in {"executed", "planned_only", "dry_run"}:
        state.last_executed_at = now
        state.cooldown_until = now + _cooldown_delta(recommendation.decision_type)
    if status in {"suppressed", "rejected"}:
        state.suppression_until = now + _suppression_delta()
    db.commit()
    db.refresh(state)
    return state


def run_autopilot_cycle(db: Session, *, actor: str = "autopilot-bot", now: datetime | None = None) -> dict[str, Any]:
    now = now or _utcnow()
    kill_switch = get_or_create_global_kill_switch(db)
    if kill_switch.enabled:
        audit = _write_autopilot_audit(
            db,
            decision_type="autopilot_kill_switch_skip",
            actor=actor,
            reason=kill_switch.reason or "global kill switch enabled",
            payload={"switch_name": kill_switch.switch_name},
            result={"status": "suppressed"},
            recommendation_key="autopilot:kill_switch",
        )
        send_notification_event(db, event_type="autopilot_kill_switch_skip", payload={"reason": kill_switch.reason, "switch_name": kill_switch.switch_name})
        return {
            "evaluated_at": now.isoformat(),
            "engine_name": "render_factory_decision_engine",
            "policy_version": load_decision_policy().get("version"),
            "recommendation_count": 0,
            "executed": [],
            "suppressed": [{"decision_key": "autopilot:kill_switch", "reason": "kill_switch_active"}],
            "escalations": [audit],
            "release_actions": [],
            "provider_actions": [],
        }

    evaluation: DecisionEvaluationResponse = evaluate_decision_policy(db, now=now)

    executed = []
    suppressed = []
    escalations = []

    for recommendation in evaluation.recommendations:
        allowed, reason = should_auto_execute(db, recommendation=recommendation, now=now)
        if not allowed:
            record_autopilot_state(
                db,
                recommendation=recommendation,
                status="suppressed",
                reason=reason,
                now=now,
            )
            suppressed.append({"decision_key": recommendation.decision_key, "reason": reason})
            continue

        payload = dict(recommendation.action_payload or {})
        if recommendation.decision_type == "switch_provider":
            payload.setdefault("expires_at", (now + _provider_override_expiry_delta()).isoformat())

        result = execute_decision(
            db,
            decision_type=recommendation.decision_type,
            actor=actor,
            action_payload=payload,
            reason=f"autopilot:{recommendation.title}",
            dry_run=False,
            recommendation_key=recommendation.decision_key,
            policy_version=evaluation.policy_version,
        )
        record_autopilot_state(
            db,
            recommendation=recommendation,
            status=result.status,
            reason=result.summary,
            now=now,
        )
        executed.append({
            "decision_key": recommendation.decision_key,
            "decision_type": recommendation.decision_type,
            "status": result.status,
            "summary": result.summary,
        })

    escalations.extend(run_escalation_policy(db, evaluation=evaluation, actor=actor, now=now))
    release_actions = run_release_unblocking_policy(db, evaluation=evaluation, actor=actor, now=now)
    provider_actions = run_provider_override_expiry_policy(db, actor=actor, now=now)

    if executed:
        send_notification_event(db, event_type="autopilot_executed", payload={"executed": executed, "evaluated_at": now.isoformat()})
    if escalations:
        send_notification_event(db, event_type="autopilot_escalation", payload={"escalations": escalations, "evaluated_at": now.isoformat()})
    if release_actions:
        send_notification_event(db, event_type="release_gate_changed", payload={"actions": release_actions, "evaluated_at": now.isoformat()})
    if provider_actions:
        send_notification_event(db, event_type="provider_override_changed", payload={"actions": provider_actions, "evaluated_at": now.isoformat()})

    return {
        "evaluated_at": now.isoformat(),
        "engine_name": evaluation.engine_name,
        "policy_version": evaluation.policy_version,
        "recommendation_count": len(evaluation.recommendations),
        "executed": executed,
        "suppressed": suppressed,
        "escalations": escalations,
        "release_actions": release_actions,
        "provider_actions": provider_actions,
    }


def run_escalation_policy(
    db: Session,
    *,
    evaluation: DecisionEvaluationResponse,
    actor: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or _utcnow()
    policy = _policy_autopilot().get("escalation", {})
    actions: list[dict[str, Any]] = []

    queue_threshold = int(policy.get("queue_pressure_queued_jobs_threshold", 6))
    if evaluation.snapshot.queued_jobs >= queue_threshold:
        actions.append(
            _write_autopilot_audit(
                db,
                decision_type="escalate_queue_pressure",
                actor=actor,
                reason=f"queued_jobs={evaluation.snapshot.queued_jobs} exceeded escalation threshold {queue_threshold}",
                payload={"queued_jobs": evaluation.snapshot.queued_jobs, "threshold": queue_threshold},
                result={"status": "escalated", "target": "platform_oncall"},
                policy_version=evaluation.policy_version,
                recommendation_key="escalation:queue_pressure",
            )
        )

    critical_threshold = int(policy.get("critical_open_incident_threshold", 2))
    if evaluation.snapshot.critical_open_incidents >= critical_threshold:
        actions.append(
            _write_autopilot_audit(
                db,
                decision_type="escalate_release_risk",
                actor=actor,
                reason=(
                    f"critical_open_incidents={evaluation.snapshot.critical_open_incidents} "
                    f"exceeded escalation threshold {critical_threshold}"
                ),
                payload={"critical_open_incidents": evaluation.snapshot.critical_open_incidents, "threshold": critical_threshold},
                result={"status": "escalated", "target": "incident_commander"},
                policy_version=evaluation.policy_version,
                recommendation_key="escalation:release_risk",
            )
        )
    return actions


def run_release_unblocking_policy(
    db: Session,
    *,
    evaluation: DecisionEvaluationResponse,
    actor: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or _utcnow()
    actions: list[dict[str, Any]] = []
    gate = get_or_create_release_gate(db)
    if not gate.blocked:
        return actions

    if evaluation.snapshot.critical_open_incidents > 0:
        return actions

    wait_delta = _release_unblock_delta()
    cutoff = now - wait_delta
    if gate.updated_at and gate.updated_at <= cutoff:
        gate.blocked = False
        gate.reason = "Auto-unblocked by autopilot after critical incident cooldown window"
        gate.source = "autopilot"
        gate.updated_by = actor
        gate.last_decision_type = "auto_unblock_release"
        db.commit()
        db.refresh(gate)
        actions.append(
            _write_autopilot_audit(
                db,
                decision_type="auto_unblock_release",
                actor=actor,
                reason="No critical incidents remain after cooldown window",
                payload={"cutoff": cutoff.isoformat(), "gate_name": gate.gate_name},
                result={"status": "executed", "blocked": gate.blocked},
                policy_version=evaluation.policy_version,
                recommendation_key="autopilot:release_unblock",
            )
        )
    return actions


def run_provider_override_expiry_policy(
    db: Session,
    *,
    actor: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or _utcnow()
    actions: list[dict[str, Any]] = []
    rows = (
        db.query(ProviderRoutingOverride)
        .filter(ProviderRoutingOverride.active.is_(True))
        .all()
    )
    for row in rows:
        if row.expires_at and row.expires_at <= now:
            row.active = False
            row.reason = (row.reason or "") + " | auto-expired by autopilot rollback"
            row.updated_by = actor
            db.commit()
            db.refresh(row)
            actions.append(
                _write_autopilot_audit(
                    db,
                    decision_type="rollback_provider_override",
                    actor=actor,
                    reason=f"Expired override {row.source_provider}->{row.target_provider}",
                    payload={"source_provider": row.source_provider, "target_provider": row.target_provider},
                    result={"status": "executed", "active": row.active},
                    recommendation_key=f"rollback:{row.source_provider}",
                )
            )
    return actions


def _write_autopilot_audit(
    db: Session,
    *,
    decision_type: str,
    actor: str,
    reason: str,
    payload: dict[str, Any],
    result: dict[str, Any],
    policy_version: str | None = None,
    recommendation_key: str | None = None,
) -> dict[str, Any]:
    row = create_decision_audit_log(
        db,
        decision_type=decision_type,
        actor=actor,
        execution_status=result.get("status", "executed"),
        reason=reason,
        action_payload=payload,
        result=result,
        policy_version=policy_version,
        recommendation_key=recommendation_key,
    )
    return {
        "audit_id": row.id,
        "decision_type": decision_type,
        "execution_status": row.execution_status,
        "recommendation_key": recommendation_key,
    }
