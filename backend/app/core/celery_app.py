from __future__ import annotations

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "render_factory",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.render_tasks",
        "app.workers.stuck_job_recovery_worker",
        "app.workers.template_analytics_worker",
        "app.workers.template_batch_worker",
        "app.workers.template_generation_worker",
        "app.workers.template_extraction_worker",
        "app.workers.template_rescore_worker",
        "app.workers.template_feedback_worker",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=settings.celery_task_acks_late,
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    worker_send_task_events=True,
    task_send_sent_event=True,
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "recover-stuck-render-tasks": {
        "task": "render.recover_stuck",
        "schedule": 120.0,
    }
}

from celery.schedules import crontab

try:
    celery_app.conf.beat_schedule = {
        **getattr(celery_app.conf, "beat_schedule", {}),
        "autopilot-evaluate-control-fabric-every-5-minutes": {
            "task": "autopilot.evaluate_control_fabric",
            "schedule": 300.0,
        },
    }
except Exception:
    pass
