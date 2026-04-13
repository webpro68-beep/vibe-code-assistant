from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.render_incident_state import RenderIncidentState
from app.models.render_job import RenderJob
from app.models.render_scene_task import RenderSceneTask
from app.services.decision_engine import evaluate_decision_policy, execute_decision


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_decision_engine_recommends_queue_pressure_and_provider_surge():
    db = _session()
    now = datetime.utcnow()

    for idx in range(4):
        db.add(
            RenderJob(
                id=f"job-q-{idx}",
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
                job_id="job-q-0",
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
            incident_key="job-q-0:health_failed",
            job_id="job-q-0",
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

    result = evaluate_decision_policy(db, now=now)

    decision_types = {item.decision_type for item in result.recommendations}
    assert "scale_worker" in decision_types
    assert "switch_provider" in decision_types
    assert "block_release" in decision_types


def test_decision_engine_can_execute_incident_ack_action():
    db = _session()
    now = datetime.utcnow()

    db.add(
        RenderIncidentState(
            id="incident-ack",
            incident_key="job-1:health_failed",
            job_id="job-1",
            project_id="proj-1",
            provider="runway",
            incident_family="health_failed",
            current_event_id="evt-ack",
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

    result = execute_decision(
        db,
        decision_type="ack_incident",
        actor="operator-1",
        action_payload={"incident_key": "job-1:health_failed"},
        reason="Acknowledged by test",
        dry_run=False,
    )

    assert result.status == "executed"
    assert result.details["status"] == "acknowledged"


def test_decision_engine_marks_control_plane_actions_as_planned_only():
    db = _session()
    result = execute_decision(
        db,
        decision_type="scale_worker",
        actor="platform-bot",
        action_payload={"recommended_worker_delta": 1},
        reason="Queue pressure",
        dry_run=False,
    )
    assert result.status == "planned_only"
