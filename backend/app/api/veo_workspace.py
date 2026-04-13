from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.veo_workspace_service import (
    create_character_reference_pack,
    list_character_reference_packs,
    attach_veo_config_to_project,
    create_veo_batch_run,
    get_veo_batch_run,
)

router = APIRouter(tags=["veo-workspace"])

@router.get("/api/v1/character-reference-packs")
async def get_character_reference_packs(db: Session = Depends(get_db)):
    return {"items": list_character_reference_packs(db)}

@router.post("/api/v1/character-reference-packs")
async def post_character_reference_pack(payload: dict, db: Session = Depends(get_db)):
    row = create_character_reference_pack(db, payload)
    return {"id": str(row.id), "pack_name": row.pack_name}

@router.post("/api/v1/projects/{project_id}/veo-config")
async def post_project_veo_config(project_id: str, payload: dict):
    try:
        project = attach_veo_config_to_project(project_id, payload)
        return {"project_id": project_id, "veo_config": project.get("veo_config"), "scene_count": len(project.get("scenes", []))}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/api/v1/veo/batch-runs")
async def post_veo_batch_run(payload: dict, db: Session = Depends(get_db)):
    return create_veo_batch_run(db, payload)

@router.get("/api/v1/veo/batch-runs/{batch_id}")
async def get_veo_batch(batch_id: str, db: Session = Depends(get_db)):
    row = get_veo_batch_run(db, batch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return row
