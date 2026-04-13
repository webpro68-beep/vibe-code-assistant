from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.template_runtime_scoring import ingest_usage_run, ingest_performance_snapshot, score_template, evaluate_memory, ranked_templates, auto_pick_template, persist_selection_decision
from app.services.template_feedback_loop import process_project_completion_feedback

router = APIRouter(tags=["template-runtime"])

@router.post("/api/v1/templates/{template_id}/runs")
async def create_template_run(template_id: str, payload: dict, db: Session = Depends(get_db)):
    row = ingest_usage_run(db, template_id, payload["project_id"], payload.get("generation_mode", "manual"))
    return {"id": str(row.id), "status": row.status}

@router.post("/api/v1/templates/{template_id}/performance-snapshot")
async def create_template_performance_snapshot(template_id: str, payload: dict, db: Session = Depends(get_db)):
    row = ingest_performance_snapshot(db, template_id, payload["project_id"], payload)
    return {"id": str(row.id)}

@router.post("/api/v1/templates/{template_id}/score")
async def score_template_api(template_id: str, db: Session = Depends(get_db)):
    row = score_template(db, template_id)
    return {"template_id": template_id, "render_score": float(row.render_score), "upload_score": float(row.upload_score), "retention_score": float(row.retention_score), "final_priority_score": float(row.final_priority_score)}

@router.post("/api/v1/templates/{template_id}/memory/evaluate")
async def evaluate_template_memory_api(template_id: str, db: Session = Depends(get_db)):
    row = evaluate_memory(db, template_id)
    return {"template_id": template_id, "state": row.state, "reason": row.reason, "last_score": float(row.last_score or 0)}

@router.get("/api/v1/templates/memory")
async def list_template_memory(db: Session = Depends(get_db)):
    from app.models.template_runtime import TemplateMemory
    rows = db.query(TemplateMemory).all()
    return {"items": [{"template_id": str(r.template_pack_id), "state": r.state, "reason": r.reason, "last_score": float(r.last_score or 0)} for r in rows]}

@router.get("/api/v1/templates/ranked")
async def get_ranked_templates(limit: int = 20, db: Session = Depends(get_db)):
    return {"items": ranked_templates(db, limit=limit)}

@router.post("/api/v1/templates/auto-pick")
async def template_auto_pick(payload: dict, db: Session = Depends(get_db)):
    result = auto_pick_template(db, payload)
    if result.get("recommended"):
        persist_selection_decision(db, result["recommended"]["template_id"], None, payload, result)
    return result

@router.post("/api/v1/templates/auto-pick/preview")
async def template_auto_pick_preview(payload: dict, db: Session = Depends(get_db)):
    return auto_pick_template(db, payload)

@router.post("/api/v1/templates/feedback/process-project")
async def process_template_feedback(payload: dict, db: Session = Depends(get_db)):
    return process_project_completion_feedback(db, payload["project_id"])
