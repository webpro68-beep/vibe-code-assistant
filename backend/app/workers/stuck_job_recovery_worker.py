from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.render_queue import enqueue_render_poll, enqueue_render_postprocess
from app.services.render_repository import (
    compute_stuck_backoff_seconds,
    escalate_stuck_scene_task,
    find_scene_tasks_exceeding_retry_budget,
    find_stuck_scene_tasks,
    get_render_job_by_id,
    increment_scene_retry_count,
    should_enqueue_postprocess,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="render.recover_stuck")
def recover_stuck_render_tasks() -> None:
    """
    Self-healing recovery loop:
    - quét scene stuck
    - retry poll fallback theo exponential backoff
    - escalate sang failed nếu vượt retry budget
    """

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(seconds=120)
        max_retry_count = 5

        # 1) Escalate các scene vượt retry budget
        exceeded = find_scene_tasks_exceeding_retry_budget(
            db,
            threshold=threshold,
            max_retry_count=max_retry_count,
        )

        for scene in exceeded:
            logger.error(
                "Escalating stuck scene task id=%s job_id=%s retry_count=%s",
                scene.id,
                scene.job_id,
                scene.retry_count,
            )

            previous_status = scene.status

            escalate_stuck_scene_task(
                db,
                scene,
                max_retry_count=max_retry_count,
            )

            # Nếu scene vừa được mark failed từ recovery và job đã đủ điều kiện postprocess,
            # enqueue postprocess đúng 1 lần theo guard downstream.
            if previous_status != "failed":
                refreshed_job = get_render_job_by_id(db, scene.job_id, with_scenes=False)
                if refreshed_job and should_enqueue_postprocess(refreshed_job):
                    enqueue_render_postprocess(refreshed_job.id)

        # 2) Retry những scene còn budget
        stuck_tasks = find_stuck_scene_tasks(
            db,
            threshold=threshold,
            max_retry_count=max_retry_count,
        )

        if not stuck_tasks:
            logger.info("No stuck scene tasks found")
            return

        logger.warning(
            "Found %s stuck scene tasks eligible for recovery",
            len(stuck_tasks),
        )

        for scene in stuck_tasks:
            delay = compute_stuck_backoff_seconds(scene.retry_count)

            logger.warning(
                "Recovering stuck scene task id=%s job_id=%s retry_count=%s countdown=%ss",
                scene.id,
                scene.job_id,
                scene.retry_count,
                delay,
            )

            increment_scene_retry_count(db, scene)
            enqueue_render_poll(scene.job_id, scene.id, countdown=delay)

    finally:
        db.close()