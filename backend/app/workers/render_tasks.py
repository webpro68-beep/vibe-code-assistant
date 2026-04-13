from __future__ import annotations

import asyncio

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.workers.render_dispatch_worker import process_render_dispatch
from app.workers.render_poll_worker import process_render_poll
from app.workers.render_postprocess_worker import process_render_postprocess


@celery_app.task(name="render.dispatch")
def render_dispatch_task(job_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(process_render_dispatch(db, job_id))
    finally:
        db.close()


@celery_app.task(name="render.poll")
def render_poll_task(job_id: str, scene_task_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(process_render_poll(db, job_id, scene_task_id))
    finally:
        db.close()


@celery_app.task(name="render.postprocess")
def render_postprocess_task(job_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(process_render_postprocess(db, job_id))
    finally:
        db.close()