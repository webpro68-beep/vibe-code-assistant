from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.render_dispatch_service import dispatch_scene_task, get_dispatch_runtime_override
from app.services.render_queue import enqueue_render_dispatch, enqueue_render_poll
from app.services.kill_switch import get_or_create_global_kill_switch
from app.services.render_repository import (
    get_render_job_by_id,
    list_queued_scene_tasks,
    mark_job_status,
    mark_scene_submitted,
    transition_scene_to_failed,
)


async def process_render_dispatch(db: Session, job_id: str) -> None:
    """
    Dispatch tất cả queued scenes sang provider theo flow callback-first,
    sau đó enqueue poll fallback.

    Flow:
    1) job queued -> dispatching
    2) từng scene queued -> submitted hoặc failed
    3) nếu scene submit thành công -> enqueue poll fallback với countdown dài hơn
    4) nếu tất cả scene fail ngay ở dispatch -> job failed
    5) nếu còn ít nhất 1 scene submit thành công -> job polling
    """
    job = get_render_job_by_id(db, job_id, with_scenes=False)
    if not job:
        return

    updated = mark_job_status(
        db,
        job,
        "dispatching",
        source="dispatch",
        reason="dispatch_started",
    )
    if not updated:
        return

    runtime_override = get_dispatch_runtime_override()
    scene_tasks = list_queued_scene_tasks(db, job_id)

    if not scene_tasks:
        mark_job_status(
            db,
            job,
            "failed",
            "No queued scene tasks found for dispatch.",
            source="dispatch",
            reason="no_queued_scenes",
        )
        return

    dispatch_batch_limit = max(1, int(runtime_override.get("dispatch_batch_limit") or len(scene_tasks) or 1))
    scenes_to_dispatch = scene_tasks[:dispatch_batch_limit]

    for scene in scenes_to_dispatch:
        result = await dispatch_scene_task(scene.provider, scene.request_payload_json)

        if not result.accepted:
            transition_scene_to_failed(
                db,
                job,
                scene,
                provider_status_raw=result.provider_status_raw,
                error_message=result.error_message or "Provider dispatch rejected scene",
                failure_code="DISPATCH_REJECTED",
                failure_category="provider_dispatch",
                raw_response=result.raw_response,
                source="dispatch",
                final_status="failed",
            )
            continue

        transitioned = mark_scene_submitted(
            db,
            scene,
            provider_task_id=result.provider_task_id,
            provider_operation_name=result.provider_operation_name,
            raw_response=result.raw_response,
            provider_request_id=result.provider_request_id,
            provider_status_raw=result.provider_status_raw,
            provider_model=result.provider_model,
            provider_callback_url=result.callback_url_used,
            effective_provider=result.provider,
            source="dispatch",
        )

        if not transitioned:
            continue

        # callback-first:
        # ưu tiên callback thật từ provider,
        # poll chỉ là fallback nếu callback không về
        if scene.poll_fallback_enabled:
            enqueue_render_poll(job_id, scene.id, countdown=int(runtime_override.get("poll_countdown_seconds") or 60))

    if len(scene_tasks) > dispatch_batch_limit and runtime_override.get("enabled", True):
        enqueue_render_dispatch(job_id, countdown=5)

    refreshed_job = get_render_job_by_id(db, job_id, with_scenes=False)
    if not refreshed_job:
        return

    # Nếu mọi scene đều fail ngay từ dispatch
    if refreshed_job.failed_scene_count >= refreshed_job.planned_scene_count:
        mark_job_status(
            db,
            refreshed_job,
            "failed",
            "All scene dispatches failed before polling phase.",
            source="dispatch",
            reason="all_dispatches_failed",
        )
        return

    # Nếu còn ít nhất 1 scene submitted thành công thì chuyển sang polling
    mark_job_status(
        db,
        refreshed_job,
        "polling",
        source="dispatch",
        reason="dispatch_completed_polling_started",
    )