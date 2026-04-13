from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import (
    AutopilotExecutionState,
    DecisionExecutionAuditLog,
    ProviderRoutingOverride,
    ReleaseGateState,
    RenderIncidentState,
    RenderJob,
    RenderSceneTask,
)
from app.services.autopilot_control_fabric import run_autopilot_cycle, run_provider_override_expiry_policy
from app.services.control_plane import get_or_create_release_gate


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_autopilot_executes_safe_decisions_and_records_state():
    db = _session()
    now = datetime.utcnow()

    for idx in range(4):
        db.add(
            RenderJob(
                id=f"job-{idx}",
                project_id=f"proj-{idx}",
                provider="runway",
                status="queued",
                planned_scene_count=1,
                completed_scene_count=0,
                failed_scene_count=0,
            )
        )
    for idx in range(2):
        db.add(
            RenderSceneTask(
                id=f"scene-fail-{idx}",
                job_id="job-0",
                scene_index=idx,
                title=f"Scene {idx}",
                provider="runway",
                status="failed",
                request_payload_json="{}",
            )
        )
    db.add(
        RenderIncidentState(
            id="incident-1",
            incident_key="job-0:health_failed",
            job_id="job-0",
            project_id="proj-0",
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

    result = run_autopilot_cycle(db, now=now)

    assert result["recommendation_count"] >= 1
    assert any(item["decision_type"] == "scale_worker" for item in result["executed"])
    assert any(item["decision_type"] == "switch_provider" for item in result["executed"])
    assert any(item["decision_type"] == "block_release" for item in result["executed"])

    state_rows = db.query(AutopilotExecutionState).all()
    assert state_rows
    audit_rows = db.query(DecisionExecutionAuditLog).all()
    assert audit_rows


def test_autopilot_release_unblock_policy():
    db = _session()
    old_now = datetime.utcnow() - timedelta(hours=2)
    gate = get_or_create_release_gate(db)
    gate.blocked = True
    gate.reason = "Blocked earlier"
    gate.updated_at = old_now
    db.commit()

    result = run_autopilot_cycle(db, now=datetime.utcnow())
    db.refresh(gate)

    assert gate.blocked is False
    assert result["release_actions"]


def test_provider_override_expiry_policy_rolls_back_expired_override():
    db = _session()
    db.add(
        ProviderRoutingOverride(
            id="override-1",
            source_provider="runway",
            target_provider="veo",
            active=True,
            reason="temporary failover",
            updated_by="test",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
    )
    db.commit()

    actions = run_provider_override_expiry_policy(db, actor="autopilot-bot", now=datetime.utcnow())
    row = db.query(ProviderRoutingOverride).filter_by(source_provider="runway").first()

    assert actions
    assert row is not None
    assert row.active is False
