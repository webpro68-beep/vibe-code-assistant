from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class StateTransitionEventResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    job_id: str | None = None
    scene_task_id: str | None = None
    source: str
    old_state: str
    new_state: str
    reason: str | None = None
    metadata_json: str | None = None
    created_at: datetime


class StateTransitionTimelineResponse(BaseModel):
    job_id: str | None = None
    scene_task_id: str | None = None
    events: list[StateTransitionEventResponse]