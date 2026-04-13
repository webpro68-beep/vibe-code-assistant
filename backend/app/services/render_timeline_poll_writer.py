from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.render_scene_task import RenderSceneTask
from app.models.render_timeline_event import RenderTimelineEvent
from app.services.render_timeline_dedupe import detect_stalled_scene, should_append_poll_transition, should_append_processing_heartbeat
from app.services.render_timeline_writer import append_scene_timeline_event


def append_poll_timeline_event_if_needed(
    db: Session,
    *,
    scene: RenderSceneTask,
    event_type: str,
    status: str | None,
    provider_status_raw: str | None,
    failure_code: str | None = None,
    failure_category: str | None = None,
    error_message: str | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> RenderTimelineEvent | None:
    allowed, _reason = should_append_poll_transition(
        db, scene=scene, next_event_type=event_type, next_status=status, next_provider_status_raw=provider_status_raw, occurred_at=occurred_at
    )
    if not allowed:
        if status == 'processing':
            hb_allowed, _ = should_append_processing_heartbeat(db, scene=scene, occurred_at=occurred_at)
            if hb_allowed:
                return append_scene_timeline_event(
                    db, scene=scene, source='provider_poll', event_type='scene_processing_heartbeat', occurred_at=occurred_at, status=status, provider_status_raw=provider_status_raw, payload=payload
                )
        return None

    event = append_scene_timeline_event(
        db, scene=scene, source='provider_poll', event_type=event_type, occurred_at=occurred_at, status=status, provider_status_raw=provider_status_raw, failure_code=failure_code, failure_category=failure_category, error_message=error_message, payload=payload
    )
    stalled, reason, meta = detect_stalled_scene(scene, now=occurred_at)
    if stalled and scene.last_stalled_at is None:
        scene.last_stalled_at = occurred_at or datetime.utcnow()
        db.commit()
        append_scene_timeline_event(
            db, scene=scene, source='provider_poll', event_type='scene_processing_stalled', occurred_at=occurred_at, status=status, provider_status_raw=provider_status_raw, payload={'stalled_reason': reason, **meta}
        )
    return event
