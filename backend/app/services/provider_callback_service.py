from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.provider_webhook_event import ProviderWebhookEvent
from app.services.provider_registry import get_provider_adapter
from app.services.render_repository import (
    find_scene_by_provider_refs,
    mark_scene_failed_from_provider,
    mark_scene_processing_from_provider,
    mark_scene_succeeded_from_provider,
)
from app.services.render_timeline_writer import append_timeline_event


def ingest_provider_callback(
    db: Session,
    *,
    provider: str,
    headers: dict[str, str],
    raw_body: bytes,
    payload: dict,
    signature_valid: bool,
) -> dict:
    adapter = get_provider_adapter(provider)
    normalized = adapter.normalize_callback(headers, payload)

    existing = (
        db.query(ProviderWebhookEvent)
        .filter(ProviderWebhookEvent.event_idempotency_key == normalized.event_idempotency_key)
        .first()
    )
    if existing:
        return {"duplicate": True, "event_id": existing.id}

    event = ProviderWebhookEvent(
        id=str(uuid.uuid4()),
        provider=provider,
        event_type=normalized.event_type,
        event_idempotency_key=normalized.event_idempotency_key,
        provider_task_id=normalized.provider_task_id,
        provider_operation_name=normalized.provider_operation_name,
        signature_valid=signature_valid,
        headers_json=json.dumps(headers, ensure_ascii=False),
        payload_json=raw_body.decode("utf-8", errors="replace"),
        normalized_payload_json=json.dumps(normalized.model_dump(), ensure_ascii=False),
    )
    db.add(event)
    db.commit()

    scene = find_scene_by_provider_refs(
        db,
        provider_task_id=normalized.provider_task_id,
        provider_operation_name=normalized.provider_operation_name,
    )

    if scene:
        append_timeline_event(
            db,
            job_id=scene.job_id,
            scene_task_id=scene.id,
            scene_index=scene.scene_index,
            source="provider_webhook",
            event_type="callback_received",
            status=normalized.state,
            provider=provider,
            provider_status_raw=normalized.provider_status_raw,
            provider_task_id=normalized.provider_task_id,
            provider_operation_name=normalized.provider_operation_name,
            signature_valid=signature_valid,
            processed=False,
            event_idempotency_key=normalized.event_idempotency_key,
            payload=normalized.model_dump(),
        )

    if scene and normalized.state == "processing":
        mark_scene_processing_from_provider(
            db,
            scene=scene,
            provider_status_raw=normalized.provider_status_raw,
            metadata=normalized.metadata,
        )
    elif scene and normalized.state == "succeeded":
        mark_scene_succeeded_from_provider(
            db,
            scene=scene,
            provider_status_raw=normalized.provider_status_raw,
            output_video_url=normalized.output_video_url,
            output_thumbnail_url=normalized.output_thumbnail_url,
            metadata=normalized.metadata,
        )
    elif scene and normalized.state in {"failed", "canceled"}:
        mark_scene_failed_from_provider(
            db,
            scene=scene,
            provider_status_raw=normalized.provider_status_raw,
            error_message=normalized.error_message,
            failure_code=normalized.failure_code,
            failure_category=normalized.failure_category,
        )

    event.processed = True
    event.processed_at = datetime.utcnow()
    db.commit()

    return {"duplicate": False, "event_id": event.id}