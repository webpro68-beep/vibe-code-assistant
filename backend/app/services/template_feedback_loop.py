from __future__ import annotations
from app.services.project_workspace_service import update_project
from app.services.template_runtime_scoring import process_project_feedback

def maybe_enqueue_template_extraction(project: dict) -> dict:
    if not project.get("is_template_source", True):
        return {"status": "skipped", "reason": "not_template_source"}
    if project.get("template_extracted"):
        return {"status": "skipped", "reason": "already_extracted"}
    project["template_extract_queued"] = True
    update_project(project["id"], **project)
    return {"status": "queued"}

def process_project_completion_feedback(db, project_id: str) -> dict:
    return process_project_feedback(db, project_id)
