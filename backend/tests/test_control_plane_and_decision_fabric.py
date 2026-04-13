from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import (
    DecisionExecutionAuditLog,
    ProviderRoutingOverride,
    ReleaseGateState,
    RenderIncidentState,
    RenderJob,
    RenderSceneTask,
    WorkerConcurrencyOverride,
)
from app.services.control_plane import (
    get_or_create_release_gate,
    resolve_effective_provider,
)
from app.services.decision_engine import execute_decision, evaluate_decision_policy


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_decision_engine_persists_worker_override_and_audit_log():
    db = _session()

    result = execute_decision(
        db,
        decision_type="scale_worker",
        actor="platform-bot",
        action_payload={"dispatch_batch_limit": 2, "poll_countdown_seconds": 15},
        reason="Queue pressure mitigation",
        dry_run=False,
        recommendation_key="queue-pressure",
        policy_version="2026-04-11",
    )

    override = db.query(WorkerConcurrencyOverride).filter_by(queue_name="render.dispatch").first()
    audit = db.query(DecisionExecutionAuditLog).filter_by(decision_type="scale_worker").first()

    assert result.status == "executed"
    assert override is not None
    assert override.dispatch_batch_limit == 2
    assert override.poll_countdown_seconds == 15
    assert audit is not None
    assert audit.execution_status == "executed"


def test_decision_engine_persists_provider_override_and_release_gate():
    db = _session()

    switch_result = execute_decision(
        db,
        decision_type="switch_provider",
        actor="platform-bot",
        action_payload={"source_provider": "runway", "target_provider": "veo"},
        reason="Provider surge",
        dry_run=False,
    )
    block_result = execute_decision(
        db,
        decision_type="block_release",
        actor="platform-bot",
        action_payload={"critical_open_incidents": 2},
        reason="Critical incident load",
        dry_run=False,
    )

    override = db.query(ProviderRoutingOverride).filter_by(source_provider="runway").first()
    gate = get_or_create_release_gate(db)

    effective, meta = resolve_effective_provider(db, "runway")

    assert switch_result.status == "executed"
    assert block_result.status == "executed"
    assert override is not None and override.target_provider == "veo"
    assert gate.blocked is True
    assert effective == "veo"
    assert meta is not None


def test_release_guardrail_recommendation_and_incident_action_audit():
    db = _session()
    now = datetime.utcnow()

    db.add(
        RenderJob(
            id="job-1",
            project_id="proj-1",
            provider="runway",
            status="queued",
            planned_scene_count=1,
            completed_scene_count=0,
            failed_scene_count=0,
        )
    )
    db.add(
        RenderSceneTask(
            id="scene-1",
            job_id="job-1",
            scene_index=1,
            title="Scene 1",
            provider="runway",
            status="failed",
            request_payload_json="{}",
        )
    )
    db.add(
        RenderIncidentState(
            id="incident-1",
            incident_key="job-1:health_failed",
            job_id="job-1",
            project_id="proj-1",
            provider="runway",
            incident_family="health_failed",
            current_event_id="evt-1",
            current_event_type="job_health_failed",
            current_severity_rank=30,
            first_seen_at=now,
            last_seen_at=now,
            last_transition_at=now,
            status="open",
            suppressed=False,
            resolved_at=None,
        )
    )
    db.commit()

    evaluation = evaluate_decision_policy(db, now=now)
    result = execute_decision(
        db,
        decision_type="ack_incident",
        actor="operator-1",
        action_payload={"incident_key": "job-1:health_failed"},
        reason="Acknowledge from decision engine",
        dry_run=False,
        recommendation_key="manual-ack",
        policy_version=evaluation.policy_version,
    )

    audit = db.query(DecisionExecutionAuditLog).filter_by(decision_type="ack_incident").first()
    assert any(r.decision_type == "block_release" for r in evaluation.recommendations)
    assert result.status == "executed"
    assert audit is not None
    assert audit.recommendation_key == "manual-ack"
