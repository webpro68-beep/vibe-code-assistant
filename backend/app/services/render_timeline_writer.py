from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.render_scene_task import RenderSceneTask
from app.models.render_timeline_event import RenderTimelineEvent


def _dump(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False)


def append_timeline_event(
    db: Session,
    *,
    job_id: str,
    scene_task_id: str | None,
    scene_index: int | None,
    source: str,
    event_type: str,
    occurred_at: datetime | None = None,
    status: str | None = None,
    provider: str | None = None,
    provider_status_raw: str | None = None,
    provider_request_id: str | None = None,
    provider_task_id: str | None = None,
    provider_operation_name: str | None = None,
    failure_code: str | None = None,
    failure_category: str | None = None,
    error_message: str | None = None,
    signature_valid: bool | None = None,
    processed: bool | None = None,
    event_idempotency_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> RenderTimelineEvent:
    event = RenderTimelineEvent(
        id=f"rte_{uuid.uuid4().hex[:24]}",
        job_id=job_id,
        scene_task_id=scene_task_id,
        scene_index=scene_index,
        source=source,
        event_type=event_type,
        status=status,
        provider=provider,
        provider_status_raw=provider_status_raw,
        provider_request_id=provider_request_id,
        provider_task_id=provider_task_id,
        provider_operation_name=provider_operation_name,
        failure_code=failure_code,
        failure_category=failure_category,
        error_message=error_message,
        signature_valid=signature_valid,
        processed=processed,
        event_idempotency_key=event_idempotency_key,
        payload_json=_dump(payload),
        occurred_at=occurred_at or datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def append_scene_timeline_event(
    db: Session,
    *,
    scene: RenderSceneTask,
    source: str,
    event_type: str,
    occurred_at: datetime | None = None,
    status: str | None = None,
    provider_status_raw: str | None = None,
    failure_code: str | None = None,
    failure_category: str | None = None,
    error_message: str | None = None,
    payload: dict[str, Any] | None = None,
) -> RenderTimelineEvent:
    return append_timeline_event(
        db,
        job_id=scene.job_id,
        scene_task_id=scene.id,
        scene_index=scene.scene_index,
        source=source,
        event_type=event_type,
        occurred_at=occurred_at,
        status=status or scene.status,
        provider=scene.provider,
        provider_status_raw=provider_status_raw or scene.provider_status_raw,
        provider_request_id=scene.provider_request_id,
        provider_task_id=scene.provider_task_id,
        provider_operation_name=scene.provider_operation_name,
        failure_code=failure_code,
        failure_category=failure_category,
        error_message=error_message,
        payload=payload,
    )
