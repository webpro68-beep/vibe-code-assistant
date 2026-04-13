from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.render_health import RenderJobHealthSummary
from app.services.render_job_health import build_render_job_health_summary
from app.services.render_repository import get_render_job_by_id

router = APIRouter(prefix='/api/v1/render/jobs', tags=['render-job-health'])


@router.get('/{job_id}/health', response_model=RenderJobHealthSummary)
async def get_render_job_health(job_id: str, db: Session = Depends(get_db)):
    job = get_render_job_by_id(db, job_id, with_scenes=True)
    if not job:
        raise HTTPException(status_code=404, detail='Render job not found')
    return RenderJobHealthSummary(**build_render_job_health_summary(db, job))
