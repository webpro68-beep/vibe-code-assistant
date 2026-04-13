from __future__ import annotations

from typing import Any

from kombu import Connection
from redis import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import engine


def check_database() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "ok": True,
            "service": "postgres",
        }
    except Exception as exc:
        return {
            "ok": False,
            "service": "postgres",
            "error": str(exc),
        }

def check_postgres() -> dict[str, Any]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "service": "postgres"}
    except SQLAlchemyError as exc:
        return {"ok": False, "service": "postgres", "error": str(exc)}


def check_redis() -> dict[str, Any]:
    try:
        redis_client = Redis.from_url(settings.celery_broker_url)
        pong = redis_client.ping()
        return {"ok": bool(pong), "service": "redis"}
    except Exception as exc:
        return {"ok": False, "service": "redis", "error": str(exc)}

def check_object_storage() -> dict[str, Any]:
    if not settings.s3_endpoint_url:
        return {
            "ok": False,
            "service": "object_storage",
            "error": "Missing S3 endpoint configuration",
        }

    try:
        import httpx

        with httpx.Client(timeout=3.0, follow_redirects=True) as client:
            response = client.get(f"{settings.s3_endpoint_url.rstrip('/')}/minio/health/live")

        return {
            "ok": response.status_code == 200,
            "service": "object_storage",
            "status_code": response.status_code,
        }
    except Exception as exc:
        return {
            "ok": False,
            "service": "object_storage",
            "error": str(exc),
        }


def check_worker_runtime() -> dict[str, Any]:
    """
    Health check cơ bản cho Celery runtime.
    Hiện tại chỉ xác nhận broker/backend config có mặt.
    Có thể nâng cấp sau thành inspect ping worker thật.
    """
    missing = []

    if not settings.celery_broker_url:
        missing.append("CELERY_BROKER_URL")
    if not settings.celery_result_backend:
        missing.append("CELERY_RESULT_BACKEND")

    if missing:
        return {
            "ok": False,
            "service": "workers",
            "error": f"Missing worker config: {', '.join(missing)}",
        }

    return {
        "ok": True,
        "service": "workers",
        "broker_url": settings.celery_broker_url,
        "result_backend": settings.celery_result_backend,
    }


def summarize_health(checks: list[dict[str, Any]]) -> dict[str, Any]:
    ok = all(bool(check.get("ok")) for check in checks)

    return {
        "ok": ok,
        "service": "render_factory_api",
        "env": settings.app_env,
        "checks": checks,
    }


def check_celery_broker() -> dict[str, Any]:
    try:
        with Connection(settings.celery_broker_url) as conn:
            conn.ensure_connection(max_retries=1)
        return {"ok": True, "service": "celery_broker"}
    except Exception as exc:
        return {"ok": False, "service": "celery_broker", "error": str(exc)}


def check_celery_workers(timeout: float = 2.0) -> dict[str, Any]:
    try:
        inspect = celery_app.control.inspect(timeout=timeout)
        ping = inspect.ping() or {}
        stats = inspect.stats() or {}

        worker_names = sorted(list(ping.keys()))
        return {
            "ok": len(worker_names) > 0,
            "service": "celery_workers",
            "workers": worker_names,
            "worker_count": len(worker_names),
            "stats_keys": sorted(list(stats.keys())),
        }
    except Exception as exc:
        return {"ok": False, "service": "celery_workers", "error": str(exc)}


def build_full_health_payload() -> dict[str, Any]:
    postgres = check_postgres()
    redis = check_redis()
    broker = check_celery_broker()
    workers = check_celery_workers()

    checks = {
        "postgres": postgres,
        "redis": redis,
        "celery_broker": broker,
        "celery_workers": workers,
    }

    overall_ok = all(item.get("ok") for item in checks.values())

    return {
        "ok": overall_ok,
        "checks": checks,
    }