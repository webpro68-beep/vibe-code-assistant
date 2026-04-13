from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.asset_collector import cache_remote_video
from app.services.render_poll_service import poll_scene_task
from app.services.render_timeline_poll_writer import append_poll_timeline_event_if_needed
from app.services.render_queue import enqueue_render_poll, enqueue_render_postprocess
from app.services.render_repository import (
    get_render_job_by_id,
    get_scene_task_by_id,
    is_scene_terminal,
    should_enqueue_postprocess,
    transition_scene_to_failed,
    transition_scene_to_processing,
    transition_scene_to_succeeded,
)


async def process_render_poll(db: Session, job_id: str, scene_task_id: str) -> None:
    job = get_render_job_by_id(db, job_id, with_scenes=False)
    scene = get_scene_task_by_id(db, scene_task_id)

    if not job or not scene:
        return

    if is_scene_terminal(scene):
        return

    result = await poll_scene_task(
        provider=scene.provider,
        provider_task_id=scene.provider_task_id,
        provider_operation_name=scene.provider_operation_name,
    )

    if result.state == "processing":
        scene.provider_status_observed_at = scene.provider_status_observed_at or scene.started_at or scene.created_at
        append_poll_timeline_event_if_needed(db, scene=scene, event_type="scene_processing", status="processing", provider_status_raw=result.provider_status_raw, payload=result.metadata or {}, occurred_at=None)
        transitioned = transition_scene_to_processing(
            db,
            scene,
            provider_status_raw=result.provider_status_raw,
            metadata=result.metadata,
            raw_response=result.raw_response,
            source="poll",
        )
        if transitioned:
            enqueue_render_poll(job_id, scene.id, countdown=15)
        return

    if result.state in {"failed", "canceled"}:
        append_poll_timeline_event_if_needed(db, scene=scene, event_type=f"scene_{result.state}", status=result.state, provider_status_raw=result.provider_status_raw, failure_code=result.failure_code, failure_category=result.failure_category, error_message=result.error_message, payload=result.raw_response or {}, occurred_at=None)
        transitioned = transition_scene_to_failed(
            db,
            job,
            scene,
            provider_status_raw=result.provider_status_raw,
            error_message=result.error_message or result.state,
            failure_code=result.failure_code,
            failure_category=result.failure_category,
            raw_response=result.raw_response,
            source="poll",
            final_status="canceled" if result.state == "canceled" else "failed",
        )
        if transitioned:
            job = get_render_job_by_id(db, job_id, with_scenes=False)
            if job and should_enqueue_postprocess(job):
                enqueue_render_postprocess(job.id)
        return

    append_poll_timeline_event_if_needed(db, scene=scene, event_type="scene_succeeded", status="succeeded", provider_status_raw=result.provider_status_raw, payload=result.raw_response or {}, occurred_at=None)
    local_video_path = None
    if result.output_video_url:
        local_video_path = await cache_remote_video(
            job_id=job.id,
            scene_index=scene.scene_index,
            url=result.output_video_url,
        )

    transitioned = transition_scene_to_succeeded(
        db,
        job,
        scene,
        provider_status_raw=result.provider_status_raw,
        output_video_url=result.output_video_url,
        output_thumbnail_url=result.output_thumbnail_url,
        local_video_path=local_video_path,
        metadata=result.metadata,
        raw_response=result.raw_response,
        source="poll",
    )

    if transitioned:
        job = get_render_job_by_id(db, job_id, with_scenes=False)
        if job and should_enqueue_postprocess(job):
            enqueue_render_postprocess(job.id)