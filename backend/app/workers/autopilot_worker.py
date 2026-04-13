from __future__ import annotations

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.autopilot_control_fabric import run_autopilot_cycle


@celery_app.task(name="autopilot.evaluate_control_fabric")
def autopilot_evaluate_control_fabric() -> dict:
    db = SessionLocal()
    try:
        return run_autopilot_cycle(db)
    finally:
        db.close()
