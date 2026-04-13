from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.provider_ingress_signing import (
    resolve_ingress_secret,
    verify_ingress_signature,
)
from app.services.provider_router import (
    normalize_render_callback,
    verify_render_callback,
)
from app.services.render_queue import enqueue_render_postprocess
from app.services.render_repository import (
    create_webhook_event,
    find_scene_by_provider_refs,
    get_render_job_by_id,
    get_webhook_event_by_idempotency_key,
    is_scene_terminal,
    mark_webhook_event_processed,
    should_enqueue_postprocess,
    transition_scene_to_failed,
    transition_scene_to_processing,
    transition_scene_to_succeeded,
)

router = APIRouter(prefix="/api/v1/provider-callbacks", tags=["provider-callbacks"])


def _load_json_payload(raw_body: bytes) -> dict:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Callback payload must be a JSON object",
        )
    return payload


def _process_normalized_callback(*, provider_key: str, headers: dict[str, str], raw_body: bytes, payload: dict):
    normalized = normalize_render_callback(
        provider=provider_key,
        headers=headers,
        payload=payload,
    )

    db: Session = SessionLocal()
    try:
        existing = get_webhook_event_by_idempotency_key(
            db,
            normalized.event_idempotency_key,
        )
        if existing:
            return {
                "ok": True,
                "duplicate": True,
                "event_id": existing.id,
                "event_idempotency_key": normalized.event_idempotency_key,
            }

        scene = find_scene_by_provider_refs(
            db,
            provider=provider_key,
            provider_task_id=normalized.provider_task_id,
            provider_operation_name=normalized.provider_operation_name,
        )

        event = create_webhook_event(
            db,
            provider=provider_key,
            event_type=normalized.event_type,
            event_idempotency_key=normalized.event_idempotency_key,
            scene_task_id=scene.id if scene else None,
            provider_task_id=normalized.provider_task_id,
            provider_operation_name=normalized.provider_operation_name,
            signature_valid=True,
            headers_json=headers,
            payload_json=payload,
            normalized_payload_json=normalized.model_dump(),
        )

        if scene is None:
            mark_webhook_event_processed(db, event)
            return {
                "ok": True,
                "duplicate": False,
                "event_id": event.id,
                "scene_matched": False,
                "event_idempotency_key": normalized.event_idempotency_key,
            }

        if is_scene_terminal(scene):
            mark_webhook_event_processed(db, event)
            return {
                "ok": True,
                "duplicate": False,
                "event_id": event.id,
                "scene_matched": True,
                "scene_task_id": scene.id,
                "event_idempotency_key": normalized.event_idempotency_key,
                "normalized_state": normalized.state,
                "ignored": True,
                "reason": f"scene already terminal: {scene.status}",
            }

        transitioned = False

        if normalized.state == "processing":
            transitioned = transition_scene_to_processing(
                db,
                scene,
                provider_status_raw=normalized.provider_status_raw,
                metadata=normalized.metadata,
                raw_response=normalized.raw_payload,
                source="callback",
            )

        elif normalized.state == "succeeded":
            job = scene.job
            transitioned = transition_scene_to_succeeded(
                db,
                job,
                scene,
                provider_status_raw=normalized.provider_status_raw,
                output_video_url=normalized.output_video_url,
                output_thumbnail_url=normalized.output_thumbnail_url,
                local_video_path=None,
                metadata=normalized.metadata,
                raw_response=normalized.raw_payload,
                source="callback",
            )

            if transitioned:
                refreshed_job = get_render_job_by_id(db, scene.job_id, with_scenes=False)
                if refreshed_job and should_enqueue_postprocess(refreshed_job):
                    enqueue_render_postprocess(refreshed_job.id)

        elif normalized.state in {"failed", "canceled"}:
            job = scene.job
            transitioned = transition_scene_to_failed(
                db,
                job,
                scene,
                provider_status_raw=normalized.provider_status_raw,
                error_message=normalized.error_message or normalized.state,
                failure_code=normalized.failure_code,
                failure_category=normalized.failure_category,
                raw_response=normalized.raw_payload,
                source="callback",
                final_status="canceled" if normalized.state == "canceled" else "failed",
            )

            if transitioned:
                refreshed_job = get_render_job_by_id(db, scene.job_id, with_scenes=False)
                if refreshed_job and should_enqueue_postprocess(refreshed_job):
                    enqueue_render_postprocess(refreshed_job.id)

        mark_webhook_event_processed(db, event)

        return {
            "ok": True,
            "duplicate": False,
            "event_id": event.id,
            "scene_matched": True,
            "scene_task_id": scene.id,
            "event_idempotency_key": normalized.event_idempotency_key,
            "normalized_state": normalized.state,
            "transitioned": transitioned,
        }
    finally:
        db.close()


@router.post("/{provider}")
async def receive_provider_callback(provider: str, request: Request):
    raw_body = await request.body()
    payload = _load_json_payload(raw_body)
    headers = {k.lower(): v for k, v in request.headers.items()}
    provider_key = provider.strip().lower()

    signature_valid = verify_render_callback(
        provider=provider_key,
        headers=headers,
        raw_body=raw_body,
    )
    if not signature_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid callback signature",
        )

    return _process_normalized_callback(
        provider_key=provider_key,
        headers=headers,
        raw_body=raw_body,
        payload=payload,
    )


@router.post("/relay/{provider}")
async def receive_provider_callback_from_signed_relay(provider: str, request: Request):
    raw_body = await request.body()
    payload = _load_json_payload(raw_body)
    headers = {k.lower(): v for k, v in request.headers.items()}
    provider_key = provider.strip().lower()

    relay_secret = resolve_ingress_secret(provider_key)
    signature_valid = verify_ingress_signature(
        secret=relay_secret,
        timestamp=headers.get("x-render-relay-timestamp"),
        signature=headers.get("x-render-relay-signature"),
        raw_body=raw_body,
    )
    if not signature_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid relay signature",
        )

    return _process_normalized_callback(
        provider_key=provider_key,
        headers=headers,
        raw_body=raw_body,
        payload=payload,
    )
