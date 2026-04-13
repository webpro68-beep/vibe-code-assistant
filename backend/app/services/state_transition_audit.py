from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.state_transition_event import StateTransitionEvent


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def create_state_transition_event(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    job_id: str | None,
    scene_task_id: str | None,
    source: str,
    old_state: str,
    new_state: str,
    reason: str | None = None,
    metadata: dict | None = None,
) -> StateTransitionEvent:
    event = StateTransitionEvent(
        id=str(uuid.uuid4()),
        entity_type=entity_type,
        entity_id=entity_id,
        job_id=job_id,
        scene_task_id=scene_task_id,
        source=source,
        old_state=old_state,
        new_state=new_state,
        reason=reason,
        metadata_json=_json_dumps(metadata or {}),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_state_transition_events_for_job(
    db: Session,
    job_id: str,
) -> list[StateTransitionEvent]:
    return (
        db.query(StateTransitionEvent)
        .filter(StateTransitionEvent.job_id == job_id)
        .order_by(StateTransitionEvent.created_at.asc())
        .all()
    )


def list_state_transition_events_for_scene(
    db: Session,
    scene_task_id: str,
) -> list[StateTransitionEvent]:
    return (
        db.query(StateTransitionEvent)
        .filter(StateTransitionEvent.scene_task_id == scene_task_id)
        .order_by(StateTransitionEvent.created_at.asc())
        .all()
    )


def list_state_transition_events_for_entity(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
) -> list[StateTransitionEvent]:
    return (
        db.query(StateTransitionEvent)
        .filter(
            StateTransitionEvent.entity_type == entity_type,
            StateTransitionEvent.entity_id == entity_id,
        )
        .order_by(StateTransitionEvent.created_at.asc())
        .all()
    )