from __future__ import annotations

def enqueue_render_dispatch(job_id: str, countdown: int = 0) -> dict:
    from app.workers.render_tasks import render_dispatch_task

    if countdown > 0:
        result = render_dispatch_task.apply_async(args=[job_id], countdown=countdown)
    else:
        result = render_dispatch_task.delay(job_id)
    return {
        "task_name": "render.dispatch",
        "celery_task_id": result.id,
        "job_id": job_id,
        "countdown": countdown,
    }


def enqueue_render_poll(
    job_id: str,
    scene_task_id: str,
    countdown: int = 60,
) -> dict:
    from app.workers.render_tasks import render_poll_task

    result = render_poll_task.apply_async(
        args=[job_id, scene_task_id],
        countdown=countdown,
    )
    return {
        "task_name": "render.poll",
        "celery_task_id": result.id,
        "job_id": job_id,
        "scene_task_id": scene_task_id,
        "countdown": countdown,
    }


def enqueue_render_postprocess(job_id: str, countdown: int = 0) -> dict:
    from app.workers.render_tasks import render_postprocess_task

    if countdown > 0:
        result = render_postprocess_task.apply_async(args=[job_id], countdown=countdown)
    else:
        result = render_postprocess_task.delay(job_id)

    return {
        "task_name": "render.postprocess",
        "celery_task_id": result.id,
        "job_id": job_id,
        "countdown": countdown,
    }
