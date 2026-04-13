from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.project_workspace_service import load_project, list_projects
from app.services.project_render_runtime import trigger_project_render, get_project_render_status, retry_project_render, rerender_scene
from app.services.render_events import build_project_render_event_summary

router = APIRouter(tags=["project-workspace"])

@router.get("/api/v1/projects")
async def get_projects():
    return {"items": list_projects()}

@router.get("/api/v1/projects/{project_id}")
async def get_project(project_id: str):
    project = load_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.post("/api/v1/projects/{project_id}/render")
async def post_project_render(project_id: str, db: Session = Depends(get_db)):
    try:
        return trigger_project_render(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/api/v1/projects/{project_id}/render-status")
async def get_project_render_status_api(project_id: str, db: Session = Depends(get_db)):
    try:
        return get_project_render_status(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.get("/api/v1/projects/{project_id}/render-events")
async def get_project_render_events_api(project_id: str, db: Session = Depends(get_db)):
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    job_id = project.get("render_job_id")
    return {"items": build_project_render_event_summary(db, job_id) if job_id else []}

@router.post("/api/v1/projects/{project_id}/render/retry")
async def retry_project_render_api(project_id: str, db: Session = Depends(get_db)):
    try:
        return retry_project_render(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/api/v1/scenes/{scene_id}/rerender")
async def rerender_scene_api(scene_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return rerender_scene(db, payload["project_id"], int(scene_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
