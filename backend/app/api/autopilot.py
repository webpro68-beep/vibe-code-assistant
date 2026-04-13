from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.autopilot_control_fabric import run_autopilot_cycle

router = APIRouter(prefix="/api/v1/autopilot", tags=["autopilot"])


@router.post("/run")
async def post_autopilot_run(db: Session = Depends(get_db)):
    return run_autopilot_cycle(db)
