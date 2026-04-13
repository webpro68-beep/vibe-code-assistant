from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.render_scene_task import RenderSceneTask
from app.models.render_timeline_event import RenderTimelineEvent

PROCESSING_DEDUPE_WINDOW_SECONDS = 45
PROCESSING_HEARTBEAT_WINDOW_SECONDS = 90
STALLED_CALLBACK_SECONDS = 300
STALLED_PROVIDER_STATUS_SECONDS = 480


def get_latest_timeline_event_for_scene(db: Session, *, scene_task_id: str, source: str | None = None, event_type: str | None = None) -> RenderTimelineEvent | None:
    q = db.query(RenderTimelineEvent).filter(RenderTimelineEvent.scene_task_id == scene_task_id)
    if source:
        q = q.filter(RenderTimelineEvent.source == source)
    if event_type:
        q = q.filter(RenderTimelineEvent.event_type == event_type)
    return q.order_by(RenderTimelineEvent.occurred_at.desc(), RenderTimelineEvent.id.desc()).first()


def should_append_poll_transition(db: Session, *, scene: RenderSceneTask, next_event_type: str, next_status: str | None, next_provider_status_raw: str | None, occurred_at: datetime | None = None) -> tuple[bool, str]:
    now = occurred_at or datetime.utcnow()
    latest = get_latest_timeline_event_for_scene(db, scene_task_id=scene.id, source='provider_poll')
    if latest is None:
        return True, 'no_previous_poll_event'
    if next_status in {'failed', 'succeeded', 'canceled'}:
        return True, 'terminal_state'
    if latest.status != next_status or latest.event_type != next_event_type:
        return True, 'state_changed'
    if (latest.provider_status_raw or '') != (next_provider_status_raw or ''):
        return True, 'provider_status_changed'
    age = (now - latest.occurred_at).total_seconds()
    if age >= PROCESSING_DEDUPE_WINDOW_SECONDS:
        return True, 'cooldown_elapsed'
    return False, 'duplicate_processing_window'


def should_append_processing_heartbeat(db: Session, *, scene: RenderSceneTask, occurred_at: datetime | None = None) -> tuple[bool, str]:
    now = occurred_at or datetime.utcnow()
    latest = get_latest_timeline_event_for_scene(db, scene_task_id=scene.id, source='provider_poll', event_type='scene_processing_heartbeat')
    if latest is None:
        return True, 'no_previous_heartbeat'
    age = (now - latest.occurred_at).total_seconds()
    if age >= PROCESSING_HEARTBEAT_WINDOW_SECONDS:
        return True, 'heartbeat_window_elapsed'
    return False, 'heartbeat_cooldown'


def detect_stalled_scene(scene: RenderSceneTask, *, now: datetime | None = None) -> tuple[bool, str | None, dict]:
    now = now or datetime.utcnow()
    if scene.status != 'processing':
        return False, None, {}
    if scene.last_callback_at is not None:
        age = (now - scene.last_callback_at).total_seconds()
        if age >= STALLED_CALLBACK_SECONDS:
            return True, 'callback_stale', {'threshold_seconds': STALLED_CALLBACK_SECONDS, 'seconds_since_last_callback': int(age)}
    if scene.provider_status_observed_at is not None and scene.provider_status_raw:
        age = (now - scene.provider_status_observed_at).total_seconds()
        if age >= STALLED_PROVIDER_STATUS_SECONDS:
            return True, 'provider_status_stagnant', {'threshold_seconds': STALLED_PROVIDER_STATUS_SECONDS, 'provider_status_raw': scene.provider_status_raw, 'seconds_since_status_change': int(age)}
    return False, None, {}
