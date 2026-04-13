from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from app.models.template_factory import TemplatePack, TemplateUsageRun, TemplatePerformanceSnapshot
from app.models.template_runtime import TemplateScore, TemplateMemory, TemplateSelectionDecision
from app.services.project_workspace_service import load_project

def _safe_num(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def ingest_usage_run(db: Session, template_pack_id: str, project_id: str, generation_mode: str = "manual") -> TemplateUsageRun:
    row = db.query(TemplateUsageRun).filter(TemplateUsageRun.project_id == project_id).first()
    if row:
        return row
    version = db.execute(text("select id from template_versions where template_pack_id=:tid and is_active=true order by version_no desc limit 1"), {"tid": str(template_pack_id)}).first()
    row = TemplateUsageRun(id=uuid.uuid4(), template_pack_id=template_pack_id, template_version_id=version[0] if version else None, project_id=project_id, mode=generation_mode, input_slots_json={}, status="rendered", result_json={"generation_mode": generation_mode})
    db.add(row); db.commit(); db.refresh(row); return row

def ingest_performance_snapshot(db: Session, template_pack_id: str, project_id: str, payload: dict) -> TemplatePerformanceSnapshot:
    row = TemplatePerformanceSnapshot(id=uuid.uuid4(), template_pack_id=template_pack_id, snapshot_json=payload)
    db.add(row); db.commit(); db.refresh(row); return row

def score_template(db: Session, template_pack_id: str) -> TemplateScore:
    snaps = db.query(TemplatePerformanceSnapshot).filter(TemplatePerformanceSnapshot.template_pack_id == template_pack_id).all()
    runs = db.query(TemplateUsageRun).filter(TemplateUsageRun.template_pack_id == template_pack_id).all()
    snapshot_count = len(snaps); runs_considered = len(runs)
    if snapshot_count == 0:
        render_score = upload_score = retention_score = final_score = 0.0; details = {"reason": "no_snapshots"}
    else:
        render_success = sum(1 for s in snaps if s.snapshot_json.get("render_success")) / snapshot_count
        upload_success = sum(1 for s in snaps if s.snapshot_json.get("upload_success")) / snapshot_count
        avg_retry = sum(_safe_num(s.snapshot_json.get("retry_count")) for s in snaps) / snapshot_count
        avg_scene_fail = sum(_safe_num(s.snapshot_json.get("scene_failure_count")) for s in snaps) / snapshot_count
        avg_ctr = sum(_safe_num(s.snapshot_json.get("ctr")) for s in snaps) / snapshot_count
        avg_ret_mid = sum(_safe_num(s.snapshot_json.get("retention_midpoint")) for s in snaps) / snapshot_count
        avg_ret_comp = sum(_safe_num(s.snapshot_json.get("retention_completion")) for s in snaps) / snapshot_count
        render_score = max(0.0, min(100.0, (render_success * 100.0) - (avg_retry * 5.0) - (avg_scene_fail * 4.0)))
        upload_score = max(0.0, min(100.0, (upload_success * 100.0) - (avg_retry * 2.0)))
        retention_score = max(0.0, min(100.0, (avg_ctr * 100.0 * 0.3) + (avg_ret_mid * 0.35) + (avg_ret_comp * 0.35)))
        final_score = round((0.35*render_score) + (0.20*upload_score) + (0.45*retention_score), 2)
        details = {"render_success_rate": render_success, "upload_success_rate": upload_success, "avg_retry_count": avg_retry, "avg_scene_failure_count": avg_scene_fail, "avg_ctr": avg_ctr, "avg_retention_midpoint": avg_ret_mid, "avg_retention_completion": avg_ret_comp}
    row = TemplateScore(id=uuid.uuid4(), template_pack_id=template_pack_id, render_score=round(render_score, 2), upload_score=round(upload_score, 2), retention_score=round(retention_score, 2), final_priority_score=round(final_score, 2), runs_considered=runs_considered, snapshot_count=snapshot_count, score_version="v1", scoring_window="all", weight_profile={"render":0.35,"upload":0.20,"retention":0.45}, score_details_json=details)
    db.add(row); db.commit(); db.refresh(row); return row

def evaluate_memory(db: Session, template_pack_id: str) -> TemplateMemory:
    latest_score = db.query(TemplateScore).filter(TemplateScore.template_pack_id == template_pack_id).order_by(desc(TemplateScore.scored_at)).first()
    memory = db.query(TemplateMemory).filter(TemplateMemory.template_pack_id == template_pack_id).first()
    if memory is None:
        memory = TemplateMemory(id=uuid.uuid4(), template_pack_id=template_pack_id, state="candidate", stats_json={})
        db.add(memory); db.commit(); db.refresh(memory)
    prev = memory.state; score = _safe_num(latest_score.final_priority_score if latest_score else 0); runs = int(latest_score.runs_considered if latest_score else 0)
    if runs < 5: state, reason = "candidate", "minimum_sample_rule"
    elif score >= 92: state, reason = "dominant", "dominant_threshold"
    elif score >= 85: state, reason = "promoted", "promote_threshold"
    elif score < 55: state, reason = "retired", "retire_threshold"
    elif score < 70: state, reason = "demoted", "demote_threshold"
    else: state, reason = ("candidate" if prev == "candidate" else "promoted"), "hold_threshold"
    memory.previous_state = prev; memory.state = state; memory.reason = reason; memory.last_score = score; memory.transition_count = int(memory.transition_count or 0) + (1 if state != prev else 0)
    db.commit(); db.refresh(memory); return memory

def ranked_templates(db: Session, limit: int = 20) -> list[dict]:
    packs = db.query(TemplatePack).all(); items = []
    for pack in packs:
        score = db.query(TemplateScore).filter(TemplateScore.template_pack_id == pack.id).order_by(desc(TemplateScore.scored_at)).first()
        memory = db.query(TemplateMemory).filter(TemplateMemory.template_pack_id == pack.id).first()
        items.append({"template_id": str(pack.id), "template_name": pack.template_name, "status": pack.status, "final_priority_score": _safe_num(score.final_priority_score if score else 0), "render_score": _safe_num(score.render_score if score else 0), "upload_score": _safe_num(score.upload_score if score else 0), "retention_score": _safe_num(score.retention_score if score else 0), "memory_state": memory.state if memory else "candidate"})
    items.sort(key=lambda x: (x["final_priority_score"], x["retention_score"]), reverse=True)
    return items[:limit]

def auto_pick_template(db: Session, request: dict) -> dict:
    items = ranked_templates(db, limit=10); platform = request.get("target_platform"); fmt = request.get("format") or request.get("aspect_ratio"); eligible=[]
    for item in items:
        fit = item["final_priority_score"]; reason=[]
        if item["memory_state"] == "dominant": fit += 5; reason.append("dominant_state")
        if platform in ("shorts","tiktok","reels"): fit += 3; reason.append("short_form_fit")
        if fmt == "9:16": fit += 4; reason.append("vertical_format_fit")
        if item["memory_state"] == "retired": continue
        eligible.append((fit,item,reason))
    eligible.sort(key=lambda x: x[0], reverse=True)
    if not eligible: return {"recommended": None, "alternatives": [], "reason": ["no_eligible_templates"], "fit_score": 0}
    fit,item,reason=eligible[0]
    alt=[{"template_id": row[1]["template_id"], "template_name": row[1]["template_name"], "fit_score": row[0], "memory_state": row[1]["memory_state"]} for row in eligible[1:4]]
    return {"recommended": item, "alternatives": alt, "reason": reason, "fit_score": round(fit,2)}

def persist_selection_decision(db: Session, template_pack_id: str, project_id: str | None, request_context: dict, pick_result: dict) -> TemplateSelectionDecision:
    row = TemplateSelectionDecision(id=uuid.uuid4(), template_pack_id=template_pack_id, project_id=project_id, decision_mode="recommend", request_context_json=request_context, fit_score=pick_result.get("fit_score",0), reason_json={"reason": pick_result.get("reason",[])}, alternatives_json=pick_result.get("alternatives",[]))
    db.add(row); db.commit(); db.refresh(row); return row

def process_project_feedback(db: Session, project_id: str) -> dict:
    run = db.query(TemplateUsageRun).filter(TemplateUsageRun.project_id == project_id).order_by(desc(TemplateUsageRun.created_at)).first()
    if run is None:
        return {"status": "skipped", "reason": "no_template_usage_run"}
    project = load_project(project_id) or {}
    payload = {"render_success": project.get("status") in {"final_ready","completed","render_succeeded"}, "upload_success": bool(project.get("uploaded")) or False, "retry_count": 0, "scene_failure_count": 0 if project.get("status") != "render_failed" else 1, "ctr": _safe_num(project.get("metrics",{}).get("ctr")), "retention_midpoint": _safe_num(project.get("metrics",{}).get("retention_midpoint")), "retention_completion": _safe_num(project.get("metrics",{}).get("retention_completion")), "snapshot_type": "render", "time_window_hours": 24}
    ingest_performance_snapshot(db, run.template_pack_id, project_id, payload)
    score = score_template(db, run.template_pack_id)
    memory = evaluate_memory(db, run.template_pack_id)
    return {"status": "processed", "template_pack_id": str(run.template_pack_id), "score": float(score.final_priority_score), "memory_state": memory.state}
