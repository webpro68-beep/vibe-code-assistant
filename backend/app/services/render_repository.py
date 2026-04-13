from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Sequence

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.provider_webhook_event import ProviderWebhookEvent
from app.models.render_job import RenderJob
from app.models.render_scene_task import RenderSceneTask
from app.models.render_timeline_event import RenderTimelineEvent
from app.services.render_fsm import assert_valid_transition
from app.services.state_transition_audit import create_state_transition_event
from app.services.render_job_health import refresh_render_job_health_snapshot
from app.services.render_incident_projector import project_timeline_event_to_incident_state
from app.services.render_timeline_writer import append_timeline_event


TERMINAL_SCENE_STATUSES = {"succeeded", "failed", "canceled"}
TERMINAL_JOB_STATUSES = {"completed", "failed"}
ACTIVE_POSTPROCESS_JOB_STATUSES = {"merging", "burning_subtitles"}


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


# =========================
# Core queries
# =========================
def create_render_job_with_scenes(
    db: Session,
    *,
    project_id: str,
    provider: str,
    aspect_ratio: str,
    style_preset: str | None,
    subtitle_mode: str,
    planned_scenes: list[dict],
) -> RenderJob:
    job = RenderJob(
        id=str(uuid.uuid4()),
        project_id=project_id,
        provider=provider,
        status="queued",
        aspect_ratio=aspect_ratio,
        style_preset=style_preset,
        subtitle_mode=subtitle_mode,
        merge_mode="timeline_concat",
        planned_scene_count=len(planned_scenes),
        completed_scene_count=0,
        failed_scene_count=0,
    )
    db.add(job)

    for scene in planned_scenes:
        db.add(
            RenderSceneTask(
                id=str(uuid.uuid4()),
                job_id=job.id,
                scene_index=int(scene["scene_index"]),
                title=scene["title"],
                provider=provider,
                status="queued",
                request_payload_json=_json_dumps(scene),
            )
        )

    db.commit()
    created = get_render_job_by_id(db, job.id, with_scenes=True)
    if created:
        refresh_render_job_health_snapshot(db, created)
    return created


def get_render_job_by_id(
    db: Session,
    job_id: str,
    *,
    with_scenes: bool = True,
) -> RenderJob | None:
    query = db.query(RenderJob).filter(RenderJob.id == job_id)
    if with_scenes:
        query = query.options(selectinload(RenderJob.scenes))
    return query.first()


def get_scene_task_by_id(db: Session, scene_task_id: str) -> RenderSceneTask | None:
    return db.query(RenderSceneTask).filter(RenderSceneTask.id == scene_task_id).first()


def find_scene_by_provider_refs(
    db: Session,
    *,
    provider: str,
    provider_task_id: str | None,
    provider_operation_name: str | None,
) -> RenderSceneTask | None:
    query = db.query(RenderSceneTask).filter(RenderSceneTask.provider == provider)

    if provider_task_id:
        found = query.filter(RenderSceneTask.provider_task_id == provider_task_id).first()
        if found:
            return found

    if provider_operation_name:
        found = query.filter(RenderSceneTask.provider_operation_name == provider_operation_name).first()
        if found:
            return found

    return None


def list_queued_scene_tasks(db: Session, job_id: str) -> list[RenderSceneTask]:
    return (
        db.query(RenderSceneTask)
        .filter(
            RenderSceneTask.job_id == job_id,
            RenderSceneTask.status == "queued",
        )
        .order_by(RenderSceneTask.scene_index.asc())
        .all()
    )


def list_successful_scene_tasks(db: Session, job_id: str) -> list[RenderSceneTask]:
    return (
        db.query(RenderSceneTask)
        .filter(
            RenderSceneTask.job_id == job_id,
            RenderSceneTask.status == "succeeded",
        )
        .order_by(RenderSceneTask.scene_index.asc())
        .all()
    )


# =========================
# State helpers
# =========================
def is_scene_terminal(scene: RenderSceneTask) -> bool:
    return scene.status in TERMINAL_SCENE_STATUSES


def is_job_terminal(job: RenderJob) -> bool:
    return job.status in TERMINAL_JOB_STATUSES


def is_job_in_postprocess(job: RenderJob) -> bool:
    return job.status in ACTIVE_POSTPROCESS_JOB_STATUSES


def all_scene_tasks_finished(job: RenderJob) -> bool:
    return (job.completed_scene_count + job.failed_scene_count) >= job.planned_scene_count


def should_enqueue_postprocess(job: RenderJob) -> bool:
    return all_scene_tasks_finished(job) and not is_job_terminal(job) and not is_job_in_postprocess(job)


# =========================
# Job transitions
# =========================
def mark_job_status(
    db: Session,
    job: RenderJob,
    status: str,
    error_message: str | None = None,
    *,
    source: str = "system",
    reason: str | None = None,
    metadata: dict | None = None,
) -> bool:
    current_status = job.status

    try:
        assert_valid_transition(
            entity_type="render_job",
            entity_id=job.id,
            current_state=current_status,
            next_state=status,
            context={
                "project_id": job.project_id,
                "provider": job.provider,
                "source": source,
            },
        )
    except Exception:
        return False

    job.status = status
    if error_message is not None:
        job.error_message = error_message

    db.commit()

    create_state_transition_event(
        db,
        entity_type="render_job",
        entity_id=job.id,
        job_id=job.id,
        scene_task_id=None,
        source=source,
        old_state=current_status,
        new_state=status,
        reason=reason or error_message,
        metadata=metadata,
    )
    append_timeline_event(
        db,
        job_id=job.id,
        scene_task_id=None,
        scene_index=None,
        source=source,
        event_type=f"job_{status}",
        status=status,
        provider=job.provider,
        error_message=error_message,
        payload={"old_status": current_status, "reason": reason, **(metadata or {})},
    )
    refresh_render_job_health_snapshot(db, get_render_job_by_id(db, job.id, with_scenes=True) or job)

    return True


def finalize_render_job(
    db: Session,
    job: RenderJob,
    *,
    final_video_url: str,
    final_video_path: str,
    final_timeline: dict,
    source: str = "postprocess",
) -> bool:
    db.refresh(job)
    old_status = job.status

    try:
        assert_valid_transition(
            entity_type="render_job",
            entity_id=job.id,
            current_state=old_status,
            next_state="completed",
            context={
                "project_id": job.project_id,
                "provider": job.provider,
                "source": source,
            },
        )
    except Exception:
        return False

    job.status = "completed"
    job.final_video_url = final_video_url
    job.final_video_path = final_video_path
    job.final_timeline_json = _json_dumps(final_timeline)

    db.commit()

    create_state_transition_event(
        db,
        entity_type="render_job",
        entity_id=job.id,
        job_id=job.id,
        scene_task_id=None,
        source=source,
        old_state=old_status,
        new_state="completed",
        reason="Final merged output completed successfully",
        metadata={
            "final_video_url": final_video_url,
            "final_video_path": final_video_path,
        },
    )

    return True


# =========================
# Scene transitions
# =========================
def mark_scene_submitted(
    db: Session,
    scene: RenderSceneTask,
    *,
    provider_task_id: str | None,
    provider_operation_name: str | None,
    raw_response: dict | None,
    provider_request_id: str | None = None,
    provider_status_raw: str | None = None,
    provider_model: str | None = None,
    provider_callback_url: str | None = None,
    effective_provider: str | None = None,
    source: str = "dispatch",
) -> bool:
    old_status = scene.status

    try:
        assert_valid_transition(
            entity_type="render_scene_task",
            entity_id=scene.id,
            current_state=old_status,
            next_state="submitted",
            context={
                "job_id": scene.job_id,
                "provider": scene.provider,
                "source": source,
            },
        )
    except Exception:
        return False

    scene.status = "submitted"
    if effective_provider:
        scene.provider = effective_provider
    scene.provider_task_id = provider_task_id
    scene.provider_operation_name = provider_operation_name
    scene.provider_request_id = provider_request_id
    scene.provider_status_raw = provider_status_raw
    scene.provider_model = provider_model
    scene.provider_callback_url = provider_callback_url
    scene.submitted_at = scene.submitted_at or datetime.utcnow()
    scene.response_payload_json = _json_dumps(raw_response or {})
    db.commit()

    create_state_transition_event(
        db,
        entity_type="render_scene_task",
        entity_id=scene.id,
        job_id=scene.job_id,
        scene_task_id=scene.id,
        source=source,
        old_state=old_status,
        new_state="submitted",
        reason="Scene submitted to provider",
        metadata={
            "provider": scene.provider,
            "provider_task_id": provider_task_id,
            "provider_operation_name": provider_operation_name,
            "provider_request_id": provider_request_id,
            "provider_model": provider_model,
        },
    )
    append_timeline_event(db, job_id=scene.job_id, scene_task_id=scene.id, scene_index=scene.scene_index, source=source, event_type='scene_submitted', status=scene.status, provider=scene.provider, provider_status_raw=scene.provider_status_raw, provider_request_id=scene.provider_request_id, provider_task_id=scene.provider_task_id, provider_operation_name=scene.provider_operation_name, payload={"title": scene.title})
    refresh_render_job_health_snapshot(db, get_render_job_by_id(db, scene.job_id, with_scenes=True) or scene.job)

    return True


def transition_scene_to_processing(
    db: Session,
    scene: RenderSceneTask,
    *,
    provider_status_raw: str | None,
    metadata: dict | None,
    raw_response: dict | None = None,
    source: str = "poll",
) -> bool:
    old_status = scene.status

    try:
        assert_valid_transition(
            entity_type="render_scene_task",
            entity_id=scene.id,
            current_state=old_status,
            next_state="processing",
            context={
                "job_id": scene.job_id,
                "provider": scene.provider,
                "source": source,
            },
        )
    except Exception:
        return False

    scene.status = "processing"
    scene.provider_status_raw = provider_status_raw or scene.provider_status_raw
    scene.started_at = scene.started_at or datetime.utcnow()

    now = datetime.utcnow()
    if source == "callback":
        scene.last_callback_at = now
    else:
        scene.last_polled_at = now

    if metadata is not None:
        scene.output_metadata_json = _json_dumps(metadata)
    if raw_response is not None:
        scene.response_payload_json = _json_dumps(raw_response)

    db.commit()

    create_state_transition_event(
        db,
        entity_type="render_scene_task",
        entity_id=scene.id,
        job_id=scene.job_id,
        scene_task_id=scene.id,
        source=source,
        old_state=old_status,
        new_state="processing",
        reason="Scene entered processing state",
        metadata={
            "provider": scene.provider,
            "provider_status_raw": provider_status_raw,
        },
    )
    append_timeline_event(db, job_id=scene.job_id, scene_task_id=scene.id, scene_index=scene.scene_index, source=f'provider_{source}', event_type='scene_processing', status=scene.status, provider=scene.provider, provider_status_raw=scene.provider_status_raw, provider_request_id=scene.provider_request_id, provider_task_id=scene.provider_task_id, provider_operation_name=scene.provider_operation_name, payload=metadata or {})
    refresh_render_job_health_snapshot(db, get_render_job_by_id(db, scene.job_id, with_scenes=True) or scene.job)

    return True


def transition_scene_to_succeeded(
    db: Session,
    job: RenderJob,
    scene: RenderSceneTask,
    *,
    provider_status_raw: str | None,
    output_video_url: str | None,
    output_thumbnail_url: str | None,
    local_video_path: str | None = None,
    metadata: dict | None = None,
    raw_response: dict | None = None,
    source: str = "poll",
) -> bool:
    old_status = scene.status

    try:
        assert_valid_transition(
            entity_type="render_scene_task",
            entity_id=scene.id,
            current_state=old_status,
            next_state="succeeded",
            context={
                "job_id": scene.job_id,
                "provider": scene.provider,
                "source": source,
            },
        )
    except Exception:
        return False

    job.completed_scene_count += 1

    scene.status = "succeeded"
    scene.provider_status_raw = provider_status_raw or scene.provider_status_raw
    scene.output_video_url = output_video_url
    scene.output_thumbnail_url = output_thumbnail_url
    scene.local_video_path = local_video_path
    scene.finished_at = datetime.utcnow()

    now = datetime.utcnow()
    if source == "callback":
        scene.last_callback_at = now
    else:
        scene.last_polled_at = now

    if metadata is not None:
        scene.output_metadata_json = _json_dumps(metadata)
    if raw_response is not None:
        scene.response_payload_json = _json_dumps(raw_response)

    db.commit()

    create_state_transition_event(
        db,
        entity_type="render_scene_task",
        entity_id=scene.id,
        job_id=scene.job_id,
        scene_task_id=scene.id,
        source=source,
        old_state=old_status,
        new_state="succeeded",
        reason="Scene completed successfully",
        metadata={
            "provider": scene.provider,
            "provider_status_raw": provider_status_raw,
            "output_video_url": output_video_url,
            "output_thumbnail_url": output_thumbnail_url,
        },
    )
    append_timeline_event(db, job_id=scene.job_id, scene_task_id=scene.id, scene_index=scene.scene_index, source=f'provider_{source}', event_type='scene_succeeded', status=scene.status, provider=scene.provider, provider_status_raw=scene.provider_status_raw, provider_request_id=scene.provider_request_id, provider_task_id=scene.provider_task_id, provider_operation_name=scene.provider_operation_name, payload={"output_video_url": output_video_url, "output_thumbnail_url": output_thumbnail_url})
    refresh_render_job_health_snapshot(db, get_render_job_by_id(db, scene.job_id, with_scenes=True) or scene.job)

    return True


def transition_scene_to_failed(
    db: Session,
    job: RenderJob,
    scene: RenderSceneTask,
    *,
    provider_status_raw: str | None,
    error_message: str | None,
    failure_code: str | None,
    failure_category: str | None,
    raw_response: dict | None = None,
    source: str = "poll",
    final_status: str = "failed",
) -> bool:
    old_status = scene.status

    try:
        assert_valid_transition(
            entity_type="render_scene_task",
            entity_id=scene.id,
            current_state=old_status,
            next_state=final_status,
            context={
                "job_id": scene.job_id,
                "provider": scene.provider,
                "source": source,
                "failure_code": failure_code,
                "failure_category": failure_category,
            },
        )
    except Exception:
        return False

    job.failed_scene_count += 1

    scene.status = final_status
    scene.provider_status_raw = provider_status_raw or scene.provider_status_raw
    scene.error_message = error_message
    scene.failure_code = failure_code
    scene.failure_category = failure_category
    scene.finished_at = datetime.utcnow()

    now = datetime.utcnow()
    if source == "callback":
        scene.last_callback_at = now
    else:
        scene.last_polled_at = now

    if raw_response is not None:
        scene.response_payload_json = _json_dumps(raw_response)

    db.commit()

    create_state_transition_event(
        db,
        entity_type="render_scene_task",
        entity_id=scene.id,
        job_id=scene.job_id,
        scene_task_id=scene.id,
        source=source,
        old_state=old_status,
        new_state=final_status,
        reason=error_message or "Scene failed or was canceled",
        metadata={
            "provider": scene.provider,
            "provider_status_raw": provider_status_raw,
            "failure_code": failure_code,
            "failure_category": failure_category,
        },
    )
    append_timeline_event(db, job_id=scene.job_id, scene_task_id=scene.id, scene_index=scene.scene_index, source=f'provider_{source}', event_type=f'scene_{final_status}', status=scene.status, provider=scene.provider, provider_status_raw=scene.provider_status_raw, provider_request_id=scene.provider_request_id, provider_task_id=scene.provider_task_id, provider_operation_name=scene.provider_operation_name, failure_code=failure_code, failure_category=failure_category, error_message=error_message, payload={"error_message": error_message})
    refresh_render_job_health_snapshot(db, get_render_job_by_id(db, scene.job_id, with_scenes=True) or scene.job)

    return True


# =========================
# Backward-compatible wrappers
# =========================
def mark_scene_processing(
    db: Session,
    scene: RenderSceneTask,
    raw_response: dict | None = None,
    *,
    provider_status_raw: str | None = None,
    output_metadata: dict | None = None,
) -> bool:
    return transition_scene_to_processing(
        db,
        scene,
        provider_status_raw=provider_status_raw,
        metadata=output_metadata,
        raw_response=raw_response,
        source="poll",
    )


def mark_scene_failed(
    db: Session,
    job: RenderJob,
    scene: RenderSceneTask,
    message: str | None,
    *,
    provider_status_raw: str | None = None,
    failure_code: str | None = None,
    failure_category: str | None = None,
    raw_response: dict | None = None,
) -> bool:
    return transition_scene_to_failed(
        db,
        job,
        scene,
        provider_status_raw=provider_status_raw,
        error_message=message,
        failure_code=failure_code,
        failure_category=failure_category,
        raw_response=raw_response,
        source="poll",
        final_status="failed",
    )


def mark_scene_succeeded(
    db: Session,
    job: RenderJob,
    scene: RenderSceneTask,
    *,
    output_video_url: str | None,
    output_thumbnail_url: str | None,
    local_video_path: str | None,
    raw_response: dict | None,
    provider_status_raw: str | None = None,
    output_metadata: dict | None = None,
) -> bool:
    return transition_scene_to_succeeded(
        db,
        job,
        scene,
        provider_status_raw=provider_status_raw,
        output_video_url=output_video_url,
        output_thumbnail_url=output_thumbnail_url,
        local_video_path=local_video_path,
        metadata=output_metadata,
        raw_response=raw_response,
        source="poll",
    )


def mark_scene_processing_from_provider(
    db: Session,
    scene: RenderSceneTask,
    *,
    provider_status_raw: str | None,
    metadata: dict | None,
    raw_response: dict | None = None,
) -> bool:
    return transition_scene_to_processing(
        db,
        scene,
        provider_status_raw=provider_status_raw,
        metadata=metadata,
        raw_response=raw_response,
        source="callback",
    )


def mark_scene_succeeded_from_provider(
    db: Session,
    scene: RenderSceneTask,
    *,
    provider_status_raw: str | None,
    output_video_url: str | None,
    output_thumbnail_url: str | None,
    metadata: dict | None,
    raw_response: dict | None = None,
) -> bool:
    return transition_scene_to_succeeded(
        db,
        scene.job,
        scene,
        provider_status_raw=provider_status_raw,
        output_video_url=output_video_url,
        output_thumbnail_url=output_thumbnail_url,
        local_video_path=None,
        metadata=metadata,
        raw_response=raw_response,
        source="callback",
    )


def mark_scene_failed_from_provider(
    db: Session,
    scene: RenderSceneTask,
    *,
    provider_status_raw: str | None,
    error_message: str | None,
    failure_code: str | None,
    failure_category: str | None,
    raw_response: dict | None = None,
) -> bool:
    return transition_scene_to_failed(
        db,
        scene.job,
        scene,
        provider_status_raw=provider_status_raw,
        error_message=error_message,
        failure_code=failure_code,
        failure_category=failure_category,
        raw_response=raw_response,
        source="callback",
        final_status="failed",
    )


# =========================
# Storage attachment
# =========================
def attach_scene_storage(
    db: Session,
    scene: RenderSceneTask,
    *,
    bucket: str,
    key: str,
    signed_url: str | None,
) -> None:
    scene.storage_bucket = bucket
    scene.storage_key = key
    scene.storage_signed_url = signed_url
    db.commit()


def attach_final_job_storage(
    db: Session,
    job: RenderJob,
    *,
    bucket: str,
    key: str,
    signed_url: str | None,
) -> bool:
    db.refresh(job)
    if is_job_terminal(job) and job.status != "completed":
        return False

    job.final_storage_bucket = bucket
    job.final_storage_key = key
    job.final_signed_url = signed_url
    db.commit()
    return True


# =========================
# Webhook audit
# =========================
def get_webhook_event_by_idempotency_key(
    db: Session,
    event_idempotency_key: str,
) -> ProviderWebhookEvent | None:
    return (
        db.query(ProviderWebhookEvent)
        .filter(ProviderWebhookEvent.event_idempotency_key == event_idempotency_key)
        .first()
    )


def create_webhook_event(
    db: Session,
    *,
    provider: str,
    event_type: str | None,
    event_idempotency_key: str,
    scene_task_id: str | None,
    provider_task_id: str | None,
    provider_operation_name: str | None,
    signature_valid: bool,
    headers_json: dict | None,
    payload_json: dict,
    normalized_payload_json: dict | None,
) -> ProviderWebhookEvent:
    event = ProviderWebhookEvent(
        id=str(uuid.uuid4()),
        provider=provider,
        event_type=event_type,
        event_idempotency_key=event_idempotency_key,
        scene_task_id=scene_task_id,
        provider_task_id=provider_task_id,
        provider_operation_name=provider_operation_name,
        signature_valid=signature_valid,
        processed=False,
        headers_json=_json_dumps(headers_json or {}),
        payload_json=_json_dumps(payload_json),
        normalized_payload_json=_json_dumps(normalized_payload_json or {}),
        received_at=datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def mark_webhook_event_processed(db: Session, event: ProviderWebhookEvent) -> None:
    event.processed = True
    event.processed_at = datetime.utcnow()
    db.commit()


def list_webhook_events_for_scene(
    db: Session,
    scene_task_id: str,
) -> list[ProviderWebhookEvent]:
    return (
        db.query(ProviderWebhookEvent)
        .filter(ProviderWebhookEvent.scene_task_id == scene_task_id)
        .order_by(ProviderWebhookEvent.received_at.desc())
        .all()
    )


def get_latest_webhook_event_for_scene(
    db: Session,
    scene_task_id: str,
) -> ProviderWebhookEvent | None:
    return (
        db.query(ProviderWebhookEvent)
        .filter(ProviderWebhookEvent.scene_task_id == scene_task_id)
        .order_by(ProviderWebhookEvent.received_at.desc())
        .first()
    )


def get_webhook_audit_summary_for_scene(
    db: Session,
    scene_task_id: str,
) -> dict:
    total_events = (
        db.query(func.count(ProviderWebhookEvent.id))
        .filter(ProviderWebhookEvent.scene_task_id == scene_task_id)
        .scalar()
        or 0
    )

    processed_events = (
        db.query(func.count(ProviderWebhookEvent.id))
        .filter(
            ProviderWebhookEvent.scene_task_id == scene_task_id,
            ProviderWebhookEvent.processed.is_(True),
        )
        .scalar()
        or 0
    )

    latest_event = get_latest_webhook_event_for_scene(db, scene_task_id)

    return {
        "total_events": int(total_events),
        "processed_events": int(processed_events),
        "latest_event_type": latest_event.event_type if latest_event else None,
        "latest_event_received_at": latest_event.received_at if latest_event else None,
        "latest_event_processed_at": latest_event.processed_at if latest_event else None,
        "latest_event_signature_valid": latest_event.signature_valid if latest_event else None,
        "latest_event_idempotency_key": latest_event.event_idempotency_key if latest_event else None,
    }


# =========================
# Recovery / self-healing
# =========================
def find_stuck_scene_tasks(
    db: Session,
    threshold: datetime,
    *,
    max_retry_count: int = 5,
    eligible_statuses: Sequence[str] = ("submitted", "processing"),
) -> list[RenderSceneTask]:
    return (
        db.query(RenderSceneTask)
        .options(selectinload(RenderSceneTask.job))
        .filter(
            RenderSceneTask.poll_fallback_enabled.is_(True),
            RenderSceneTask.status.in_(list(eligible_statuses)),
            RenderSceneTask.retry_count < max_retry_count,
            or_(
                RenderSceneTask.last_callback_at.is_(None),
                RenderSceneTask.last_callback_at < threshold,
            ),
            or_(
                RenderSceneTask.last_polled_at.is_(None),
                RenderSceneTask.last_polled_at < threshold,
            ),
        )
        .order_by(
            RenderSceneTask.retry_count.asc(),
            RenderSceneTask.updated_at.asc(),
        )
        .all()
    )


def find_scene_tasks_exceeding_retry_budget(
    db: Session,
    threshold: datetime,
    *,
    max_retry_count: int = 5,
    eligible_statuses: Sequence[str] = ("submitted", "processing"),
) -> list[RenderSceneTask]:
    return (
        db.query(RenderSceneTask)
        .options(selectinload(RenderSceneTask.job))
        .filter(
            RenderSceneTask.poll_fallback_enabled.is_(True),
            RenderSceneTask.status.in_(list(eligible_statuses)),
            RenderSceneTask.retry_count >= max_retry_count,
            or_(
                RenderSceneTask.last_callback_at.is_(None),
                RenderSceneTask.last_callback_at < threshold,
            ),
            or_(
                RenderSceneTask.last_polled_at.is_(None),
                RenderSceneTask.last_polled_at < threshold,
            ),
        )
        .order_by(RenderSceneTask.updated_at.asc())
        .all()
    )


def increment_scene_retry_count(db: Session, scene: RenderSceneTask) -> None:
    scene.retry_count = (scene.retry_count or 0) + 1
    scene.last_polled_at = datetime.utcnow()
    db.commit()


def compute_stuck_backoff_seconds(
    retry_count: int,
    *,
    base_delay_seconds: int = 30,
    max_delay_seconds: int = 600,
) -> int:
    delay = base_delay_seconds * (2 ** max(retry_count, 0))
    return min(delay, max_delay_seconds)


def escalate_stuck_scene_task(
    db: Session,
    scene: RenderSceneTask,
    *,
    max_retry_count: int,
) -> None:
    job = scene.job
    transitioned = transition_scene_to_failed(
        db,
        job,
        scene,
        provider_status_raw=scene.provider_status_raw,
        error_message=f"Scene task exceeded stuck retry budget ({max_retry_count}) without callback or successful poll recovery.",
        failure_code="STUCK_TIMEOUT",
        failure_category="orchestration",
        raw_response=None,
        source="recovery",
        final_status="failed",
    )

    if transitioned and job and should_enqueue_postprocess(job):
        # intentionally queue-level decision is outside repository
        pass

# =========================
# Read models
# =========================
def _parse_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def build_render_job_response(db: Session, job: RenderJob, *, include_scenes: bool = True) -> RenderJob:
    db.refresh(job)
    if include_scenes:
        job = get_render_job_by_id(db, job.id, with_scenes=True) or job
    refresh_render_job_health_snapshot(db, job)
    return type('RenderJobDTO', (), {
        'id': job.id,
        'project_id': job.project_id,
        'provider': job.provider,
        'aspect_ratio': job.aspect_ratio,
        'style_preset': job.style_preset,
        'subtitle_mode': job.subtitle_mode,
        'status': job.status,
        'error_message': job.error_message,
        'planned_scene_count': job.planned_scene_count,
        'output_url': job.final_video_url or job.output_url or job.final_signed_url,
        'output_path': job.final_video_path or job.output_path,
        'storage_key': job.final_storage_key or job.storage_key,
        'thumbnail_url': job.thumbnail_url,
        'subtitle_segments': _parse_json(job.subtitle_segments),
        'final_timeline': _parse_json(job.final_timeline_json or job.final_timeline),
        'started_at': job.started_at,
        'completed_at': job.completed_at,
        'created_at': job.created_at,
        'updated_at': job.updated_at,
        'scenes': [type('SceneDTO', (), {
            'id': s.id, 'job_id': s.job_id, 'scene_index': s.scene_index, 'title': s.title, 'status': s.status,
            'provider_task_id': s.provider_task_id, 'provider_operation_name': s.provider_operation_name,
            'output_url': s.storage_signed_url or s.output_video_url, 'output_path': s.local_video_path,
            'error_message': s.error_message, 'completed_at': s.finished_at
        }) for s in (job.scenes if include_scenes else [])]
    })()


def list_timeline_events_for_job(db: Session, job_id: str, *, limit: int = 200) -> list[RenderTimelineEvent]:
    return db.query(RenderTimelineEvent).filter(RenderTimelineEvent.job_id == job_id).order_by(RenderTimelineEvent.occurred_at.desc(), RenderTimelineEvent.id.desc()).limit(limit).all()


def list_timeline_events_for_scene(db: Session, scene_task_id: str, *, limit: int = 200) -> list[RenderTimelineEvent]:
    return db.query(RenderTimelineEvent).filter(RenderTimelineEvent.scene_task_id == scene_task_id).order_by(RenderTimelineEvent.occurred_at.desc(), RenderTimelineEvent.id.desc()).limit(limit).all()
