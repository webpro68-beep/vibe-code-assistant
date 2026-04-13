from __future__ import annotations

from fastapi import APIRouter

from app.services.healthcheck_service import (
    check_database,
    check_object_storage,
    check_redis,
    check_worker_runtime,
    summarize_health,
)
from app.services.render_fsm import describe_fsm, get_transition_metrics_snapshot

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    """
    Aggregate health endpoint cho toàn bộ backend runtime.
    """
    checks = [
        check_database(),
        check_redis(),
        check_object_storage(),
        check_worker_runtime(),
    ]
    return summarize_health(checks)


@router.get("/healthz/postgres")
async def healthz_postgres() -> dict:
    """
    Health check riêng cho Postgres.
    """
    return check_database()


@router.get("/healthz/redis")
async def healthz_redis() -> dict:
    """
    Health check riêng cho Redis/Celery broker.
    """
    return check_redis()


@router.get("/healthz/object-storage")
async def healthz_object_storage() -> dict:
    """
    Health check riêng cho MinIO/S3-compatible object storage.
    """
    return check_object_storage()


@router.get("/healthz/workers")
async def healthz_workers() -> dict:
    """
    Health check cơ bản cho Celery worker runtime.
    """
    return check_worker_runtime()


@router.get("/healthz/fsm")
async def healthz_fsm() -> dict:
    """
    Expose FSM metrics + transition map để debug orchestration.
    """
    return {
        "ok": True,
        "metrics": get_transition_metrics_snapshot(),
        "fsm": describe_fsm(),
    }