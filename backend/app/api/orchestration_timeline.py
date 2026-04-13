from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.state_transition_event import (
    StateTransitionEventResponse,
    StateTransitionTimelineResponse,
)
from app.services.state_transition_audit import (
    list_state_transition_events_for_job,
    list_state_transition_events_for_scene,
)

router = APIRouter(prefix="/api/v1/orchestration", tags=["orchestration-timeline"])


@router.get("/jobs/{job_id}/timeline", response_model=StateTransitionTimelineResponse)
async def get_job_timeline(job_id: str, db: Session = Depends(get_db)):
    events = list_state_transition_events_for_job(db, job_id)

    return StateTransitionTimelineResponse(
        job_id=job_id,
        scene_task_id=None,
        events=[
            StateTransitionEventResponse(
                id=e.id,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                job_id=e.job_id,
                scene_task_id=e.scene_task_id,
                source=e.source,
                old_state=e.old_state,
                new_state=e.new_state,
                reason=e.reason,
                metadata_json=e.metadata_json,
                created_at=e.created_at,
            )
            for e in events
        ],
    )


@router.get("/scenes/{scene_task_id}/timeline", response_model=StateTransitionTimelineResponse)
async def get_scene_timeline(scene_task_id: str, db: Session = Depends(get_db)):
    events = list_state_transition_events_for_scene(db, scene_task_id)

    return StateTransitionTimelineResponse(
        job_id=None,
        scene_task_id=scene_task_id,
        events=[
            StateTransitionEventResponse(
                id=e.id,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                job_id=e.job_id,
                scene_task_id=e.scene_task_id,
                source=e.source,
                old_state=e.old_state,
                new_state=e.new_state,
                reason=e.reason,
                metadata_json=e.metadata_json,
                created_at=e.created_at,
            )
            for e in events
        ],
    )