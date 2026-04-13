from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.render_job_status import RenderJobStatusResponse
from app.services.render_repository import (
    build_render_job_response,
    get_render_job_by_id,
)

router = APIRouter(tags=["render-job-status"])


@router.get(
    "/api/v1/render/jobs/{job_id}",
    response_model=RenderJobStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_render_job(
    job_id: str,
    include_scenes: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """
    Read-model route for frontend polling.

    This route does not orchestrate anything.
    It only reads DB state and returns the current render job status payload.
    """
    try:
        job = get_render_job_by_id(db, job_id=job_id)

        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Render job not found: {job_id}",
            )

        response = build_render_job_response(
            db=db,
            job=job,
            include_scenes=include_scenes,
        )

        terminal_statuses = {"completed", "failed", "canceled"}
        return RenderJobStatusResponse(
            ok=True,
            data=response,
            error=None,
            meta={
                "job_id": job_id,
                "include_scenes": include_scenes,
                "poll_recommended": response.status not in terminal_statuses,
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch render job status",
        ) from exc