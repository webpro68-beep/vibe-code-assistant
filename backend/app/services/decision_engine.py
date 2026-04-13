from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.render_incident_state import RenderIncidentState
from app.models.render_job import RenderJob
from app.models.render_scene_task import RenderSceneTask
from app.core.config import settings
from app.schemas.decision_engine import (
    DecisionContextSnapshot,
    DecisionEvaluationResponse,
    DecisionExecutionResult,
    DecisionRecommendation,
)
from app.services.render_incident_projector import apply_incident_action
from app.services.control_plane import (
    create_decision_audit_log,
    set_provider_override,
    set_release_gate,
    set_worker_override,
)


_DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "default_decision_policy.json"


def load_decision_policy() -> dict:
    path = Path(settings.decision_engine_policy_path) if settings.decision_engine_policy_path else _DEFAULT_POLICY_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def _build_snapshot(db: Session, *, now: datetime | None = None) -> DecisionContextSnapshot:
    now = now or datetime.utcnow()
    cutoff = now - timedelta(hours=24)

    queued_jobs = db.query(RenderJob).filter(RenderJob.status == "queued").count()
    processing_jobs = db.query(RenderJob).filter(RenderJob.status.in_(["submitted", "processing", "merging"])).count()

    failed_scenes = (
        db.query(RenderSceneTask)
        .filter(RenderSceneTask.status == "failed")
        .all()
    )
    failed_counter: Counter[str] = Counter()
    for scene in failed_scenes:
        if getattr(scene, "updated_at", None) is None or scene.updated_at >= cutoff:
            failed_counter[scene.provider or "unknown"] += 1

    open_incidents = (
        db.query(RenderIncidentState)
        .filter(RenderIncidentState.status.in_(["open", "acknowledged", "assigned", "muted"]))
        .all()
    )
    open_incidents_by_provider: Counter[str] = Counter()
    open_incidents_by_assignee: Counter[str] = Counter()
    critical_open_incidents = 0

    for incident in open_incidents:
        provider = incident.provider or "unknown"
        open_incidents_by_provider[provider] += 1
        if incident.assigned_to:
            open_incidents_by_assignee[incident.assigned_to] += 1
        if getattr(incident, "current_severity_rank", 0) >= 20:
            critical_open_incidents += 1

    return DecisionContextSnapshot(
        queued_jobs=queued_jobs,
        processing_jobs=processing_jobs,
        failed_scenes_last_24h_by_provider=dict(failed_counter),
        open_incidents_by_provider=dict(open_incidents_by_provider),
        critical_open_incidents=critical_open_incidents,
        open_incidents_by_assignee=dict(open_incidents_by_assignee),
    )


def evaluate_decision_policy(db: Session, *, now: datetime | None = None) -> DecisionEvaluationResponse:
    now = now or datetime.utcnow()
    policy = load_decision_policy()
    snapshot = _build_snapshot(db, now=now)
    rules = policy["rules"]
    recommendations: list[DecisionRecommendation] = []

    queue_rule = rules["queue_pressure"]
    if queue_rule.get("enabled") and (
        snapshot.queued_jobs >= queue_rule["queued_jobs_threshold"]
        or snapshot.processing_jobs >= queue_rule["processing_jobs_threshold"]
    ):
        recommendations.append(
            DecisionRecommendation(
                decision_key="queue-pressure",
                decision_type="scale_worker",
                severity=queue_rule["severity"],
                title="Queue pressure exceeded safe threshold",
                rationale=(
                    f"Queued jobs={snapshot.queued_jobs}, processing jobs={snapshot.processing_jobs}; "
                    "recommend increasing worker concurrency or temporarily throttling submissions."
                ),
                owner=queue_rule["owner"],
                action_payload={
                    "queued_jobs": snapshot.queued_jobs,
                    "processing_jobs": snapshot.processing_jobs,
                    "recommended_worker_delta": 1,
                },
                planned_only=True,
            )
        )

    surge_rule = rules["provider_failure_surge"]
    if surge_rule.get("enabled"):
        for provider, failed_count in snapshot.failed_scenes_last_24h_by_provider.items():
            open_count = snapshot.open_incidents_by_provider.get(provider, 0)
            if failed_count >= surge_rule["failed_scene_threshold"] or open_count >= surge_rule["open_incident_threshold"]:
                recommendations.append(
                    DecisionRecommendation(
                        decision_key=f"provider-surge-{provider}",
                        decision_type="switch_provider",
                        severity=surge_rule["severity"],
                        title=f"Provider failure surge detected for {provider}",
                        rationale=(
                            f"{provider} has failed_scenes_last_24h={failed_count} and open_incidents={open_count}; "
                            "recommend routing new scenes away from this provider until recovery."
                        ),
                        owner=surge_rule["owner"],
                        action_payload={
                            "source_provider": provider,
                            "target_provider": _fallback_provider(provider),
                            "failed_scenes_last_24h": failed_count,
                            "open_incidents": open_count,
                        },
                        planned_only=True,
                    )
                )

    release_rule = rules["release_guardrail"]
    if release_rule.get("enabled") and snapshot.critical_open_incidents >= release_rule["critical_open_incident_threshold"]:
        recommendations.append(
            DecisionRecommendation(
                decision_key="release-guardrail",
                decision_type="block_release",
                severity=release_rule["severity"],
                title="Release should be blocked due to critical incident load",
                rationale=(
                    f"critical_open_incidents={snapshot.critical_open_incidents}; "
                    "releasing now would increase operational risk."
                ),
                owner=release_rule["owner"],
                action_payload={"critical_open_incidents": snapshot.critical_open_incidents},
                planned_only=True,
            )
        )

    overload_rule = rules["operator_overload"]
    if overload_rule.get("enabled"):
        overloaded = {
            assignee: count
            for assignee, count in snapshot.open_incidents_by_assignee.items()
            if count >= overload_rule["max_open_incidents_per_assignee"]
        }
        for assignee, count in overloaded.items():
            recommendations.append(
                DecisionRecommendation(
                    decision_key=f"operator-overload-{assignee}",
                    decision_type="rebalance_queue",
                    severity=overload_rule["severity"],
                    title=f"Operator overload detected for {assignee}",
                    rationale=(
                        f"{assignee} has {count} open incidents; recommend redistributing ownership to reduce response latency."
                    ),
                    owner=overload_rule["owner"],
                    action_payload={"assignee": assignee, "open_incident_count": count},
                    planned_only=True,
                )
            )

    return DecisionEvaluationResponse(
        engine_name=policy["engine_name"],
        policy_version=policy["version"],
        evaluated_at=now,
        snapshot=snapshot,
        recommendations=recommendations,
    )


def execute_decision(
    db: Session,
    *,
    decision_type: str,
    actor: str,
    action_payload: dict | None = None,
    reason: str | None = None,
    dry_run: bool = False,
    recommendation_key: str | None = None,
    policy_version: str | None = None,
) -> DecisionExecutionResult:
    action_payload = action_payload or {}

    if dry_run:
        result = DecisionExecutionResult(
            decision_type=decision_type,
            status="dry_run",
            summary=f"Dry-run accepted for {decision_type}",
            details={"actor": actor, "action_payload": action_payload, "reason": reason},
        )
        create_decision_audit_log(
            db,
            decision_type=decision_type,
            actor=actor,
            execution_status=result.status,
            reason=reason,
            action_payload=action_payload,
            result=result.model_dump(),
            policy_version=policy_version,
            recommendation_key=recommendation_key,
        )
        return result

    if decision_type == "scale_worker":
        row = set_worker_override(
            db,
            actor=actor,
            dispatch_batch_limit=action_payload.get("dispatch_batch_limit") or action_payload.get("recommended_worker_delta") or 1,
            poll_countdown_seconds=action_payload.get("poll_countdown_seconds"),
            reason=reason,
        )
        result = DecisionExecutionResult(
            decision_type=decision_type,
            status="executed",
            summary="Worker concurrency override updated",
            details={
                "queue_name": row.queue_name,
                "dispatch_batch_limit": row.dispatch_batch_limit,
                "poll_countdown_seconds": row.poll_countdown_seconds,
                "enabled": row.enabled,
            },
        )
        create_decision_audit_log(
            db,
            decision_type=decision_type,
            actor=actor,
            execution_status=result.status,
            reason=reason,
            action_payload=action_payload,
            result=result.model_dump(),
            policy_version=policy_version,
            recommendation_key=recommendation_key,
        )
        return result

    if decision_type == "switch_provider":
        source_provider = action_payload.get("source_provider")
        target_provider = action_payload.get("target_provider")
        if not source_provider or not target_provider:
            result = DecisionExecutionResult(
                decision_type=decision_type,
                status="rejected",
                summary="source_provider and target_provider are required",
                details={},
            )
            create_decision_audit_log(
                db,
                decision_type=decision_type,
                actor=actor,
                execution_status=result.status,
                reason=reason,
                action_payload=action_payload,
                result=result.model_dump(),
                policy_version=policy_version,
                recommendation_key=recommendation_key,
            )
            return result
        expires_at = action_payload.get("expires_at")
        if isinstance(expires_at, str) and expires_at:
            from datetime import datetime as _dt
            expires_at = _dt.fromisoformat(expires_at.replace("Z", "+00:00")).replace(tzinfo=None)
        row = set_provider_override(
            db,
            actor=actor,
            source_provider=source_provider,
            target_provider=target_provider,
            active=True,
            reason=reason,
            expires_at=expires_at,
        )
        result = DecisionExecutionResult(
            decision_type=decision_type,
            status="executed",
            summary=f"Provider routing override set: {source_provider} -> {target_provider}",
            details={
                "source_provider": row.source_provider,
                "target_provider": row.target_provider,
                "active": row.active,
            },
        )
        create_decision_audit_log(
            db,
            decision_type=decision_type,
            actor=actor,
            execution_status=result.status,
            reason=reason,
            action_payload=action_payload,
            result=result.model_dump(),
            policy_version=policy_version,
            recommendation_key=recommendation_key,
        )
        return result

    if decision_type == "block_release":
        row = set_release_gate(
            db,
            actor=actor,
            blocked=True,
            reason=reason or "Blocked by decision engine",
            source="decision_engine",
            decision_type=decision_type,
        )
        result = DecisionExecutionResult(
            decision_type=decision_type,
            status="executed",
            summary="Release gate persisted in blocked state",
            details={"gate_name": row.gate_name, "blocked": row.blocked, "reason": row.reason},
        )
        create_decision_audit_log(
            db,
            decision_type=decision_type,
            actor=actor,
            execution_status=result.status,
            reason=reason,
            action_payload=action_payload,
            result=result.model_dump(),
            policy_version=policy_version,
            recommendation_key=recommendation_key,
        )
        return result

    if decision_type == "rebalance_queue":
        result = DecisionExecutionResult(
            decision_type=decision_type,
            status="planned_only",
            summary="Queue rebalance recommendation recorded; no safe bulk reassignment actuator is wired yet",
            details={"actor": actor, "action_payload": action_payload, "reason": reason},
        )
        create_decision_audit_log(
            db,
            decision_type=decision_type,
            actor=actor,
            execution_status=result.status,
            reason=reason,
            action_payload=action_payload,
            result=result.model_dump(),
            policy_version=policy_version,
            recommendation_key=recommendation_key,
        )
        return result

    if decision_type in {"ack_incident", "assign_incident", "resolve_incident"}:
        incident_key = action_payload.get("incident_key")
        if not incident_key:
            result = DecisionExecutionResult(
                decision_type=decision_type,
                status="rejected",
                summary="incident_key is required for incident actions",
                details={},
            )
            create_decision_audit_log(
                db,
                decision_type=decision_type,
                actor=actor,
                execution_status=result.status,
                reason=reason,
                action_payload=action_payload,
                result=result.model_dump(),
                policy_version=policy_version,
                recommendation_key=recommendation_key,
            )
            return result

        action_type = {
            "ack_incident": "acknowledge",
            "assign_incident": "assign",
            "resolve_incident": "resolve",
        }[decision_type]

        payload = {}
        if decision_type == "assign_incident":
            payload["assigned_to"] = action_payload.get("assigned_to")

        state = apply_incident_action(
            db,
            incident_key=incident_key,
            action_type=action_type,
            actor=actor,
            reason=reason,
            payload=payload,
        )
        if state is None:
            result = DecisionExecutionResult(
                decision_type=decision_type,
                status="rejected",
                summary=f"Incident not found: {incident_key}",
                details={},
            )
            create_decision_audit_log(
                db,
                decision_type=decision_type,
                actor=actor,
                execution_status=result.status,
                reason=reason,
                action_payload=action_payload,
                result=result.model_dump(),
                policy_version=policy_version,
                recommendation_key=recommendation_key,
            )
            return result

        result = DecisionExecutionResult(
            decision_type=decision_type,
            status="executed",
            summary=f"{decision_type} executed for {incident_key}",
            details={"incident_key": incident_key, "status": state.status},
        )
        create_decision_audit_log(
            db,
            decision_type=decision_type,
            actor=actor,
            execution_status=result.status,
            reason=reason,
            action_payload=action_payload,
            result=result.model_dump(),
            policy_version=policy_version,
            recommendation_key=recommendation_key,
        )
        return result

    result = DecisionExecutionResult(
        decision_type=decision_type,
        status="rejected",
        summary=f"Unsupported decision_type: {decision_type}",
        details={},
    )
    create_decision_audit_log(
        db,
        decision_type=decision_type,
        actor=actor,
        execution_status=result.status,
        reason=reason,
        action_payload=action_payload,
        result=result.model_dump(),
        policy_version=policy_version,
        recommendation_key=recommendation_key,
    )
    return result


def _fallback_provider(source_provider: str) -> str:
    options = ["runway", "veo", "kling"]
    for option in options:
        if option != source_provider:
            return option
    return source_provider
