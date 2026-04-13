from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api import deps
from app.models.template_runtime import (
    TemplateCompetitionRecord,
    TemplateExtractedDraft,
    TemplateExtractionJob,
    TemplateLearningStat,
)
from app.services.template_extraction_service import TemplateExtractionService
from app.services.template_preview_builder import TemplatePreviewBuilder


router = APIRouter(prefix="/api/v1", tags=["template-extraction"])


class TemplateExtractionRequest(BaseModel):
    source_render_job_id: str | None = None
    force: bool = False
    run_now: bool = True


class TemplatePreviewRequest(BaseModel):
    overrides: dict[str, Any] | None = None


class CreateProjectFromTemplateRequest(BaseModel):
    user_inputs: dict[str, Any] | None = None
    overrides: dict[str, Any] | None = None


class ExtractionJobResponse(BaseModel):
    id: str
    project_id: str
    source_render_job_id: str | None = None
    status: str
    source_project_fingerprint: str
    output_template_id: str | None = None
    reason: str | None = None
    error_message: str | None = None
    extraction_summary_json: dict[str, Any] | None = None


class ExtractedTemplateListItem(BaseModel):
    id: str
    name: str
    status: str
    project_id: str
    ratio: str | None = None
    platform: str | None = None
    scene_count: int
    scope_key: str | None = None
    preview_payload: dict[str, Any] | None = None
    tags_json: list[Any] | None = None


@router.post("/projects/{project_id}/template-extract", response_model=ExtractionJobResponse)
def extract_template_from_project(
    project_id: str,
    payload: TemplateExtractionRequest,
    db: Session = Depends(deps.get_db),
) -> ExtractionJobResponse:
    service = TemplateExtractionService(db=db)
    job = service.enqueue_or_get_existing(
        project_id=project_id,
        source_render_job_id=payload.source_render_job_id,
        force=payload.force,
    )

    if payload.run_now and job.status in {"pending", "running"}:
        job = service.run_job(job.id)

    return ExtractionJobResponse.model_validate(job.__dict__)


@router.get("/template-extraction-jobs/{job_id}", response_model=ExtractionJobResponse)
def get_template_extraction_job(
    job_id: str,
    db: Session = Depends(deps.get_db),
) -> ExtractionJobResponse:
    job = db.get(TemplateExtractionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Template extraction job not found")
    return ExtractionJobResponse.model_validate(job.__dict__)


@router.get("/templates/extracted", response_model=list[ExtractedTemplateListItem])
def list_extracted_templates(
    status: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    ratio: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(deps.get_db),
) -> list[ExtractedTemplateListItem]:
    stmt = select(TemplateExtractedDraft).order_by(desc(TemplateExtractedDraft.created_at)).limit(limit)

    if status:
        stmt = stmt.where(TemplateExtractedDraft.status == status)
    if platform:
        stmt = stmt.where(TemplateExtractedDraft.platform == platform)
    if ratio:
        stmt = stmt.where(TemplateExtractedDraft.ratio == ratio)

    rows = db.scalars(stmt).all()
    return [ExtractedTemplateListItem.model_validate(row.__dict__) for row in rows]


@router.get("/templates/{template_id}/reuse-preview")
def get_template_reuse_preview(
    template_id: str,
    db: Session = Depends(deps.get_db),
) -> dict[str, Any]:
    builder = TemplatePreviewBuilder(db=db)
    try:
        return builder.get_or_build_preview(template_id=template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/templates/{template_id}/build-preview")
def build_template_reuse_preview(
    template_id: str,
    payload: TemplatePreviewRequest,
    db: Session = Depends(deps.get_db),
) -> dict[str, Any]:
    builder = TemplatePreviewBuilder(db=db)
    try:
        return builder.get_or_build_preview(template_id=template_id, overrides=payload.overrides)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/templates/{template_id}/create-project")
def create_project_payload_from_template(
    template_id: str,
    payload: CreateProjectFromTemplateRequest,
    db: Session = Depends(deps.get_db),
) -> dict[str, Any]:
    builder = TemplatePreviewBuilder(db=db)
    try:
        return builder.build_project_payload(
            template_id=template_id,
            user_inputs=payload.user_inputs,
            overrides=payload.overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/templates/{template_id}/competition")
def get_template_competition(
    template_id: str,
    scope_key: str | None = Query(default=None),
    db: Session = Depends(deps.get_db),
) -> dict[str, Any]:
    stmt = select(TemplateCompetitionRecord).where(TemplateCompetitionRecord.template_id == template_id)
    if scope_key:
        stmt = stmt.where(TemplateCompetitionRecord.scope_key == scope_key)

    rows = db.scalars(stmt.order_by(desc(TemplateCompetitionRecord.sample_count))).all()

    total_samples = sum(int(r.sample_count or 0) for r in rows)
    total_wins = sum(int(r.win_count or 0) for r in rows)
    total_losses = sum(int(r.loss_count or 0) for r in rows)
    total_ties = sum(int(r.tie_count or 0) for r in rows)

    return {
        "template_id": template_id,
        "scope_key": scope_key,
        "summary": {
            "opponents": len(rows),
            "sample_count": total_samples,
            "win_count": total_wins,
            "loss_count": total_losses,
            "tie_count": total_ties,
        },
        "records": [
            {
                "id": r.id,
                "compared_against_template_id": r.compared_against_template_id,
                "scope_key": r.scope_key,
                "win_count": r.win_count,
                "loss_count": r.loss_count,
                "tie_count": r.tie_count,
                "sample_count": r.sample_count,
                "avg_score_delta": r.avg_score_delta,
                "avg_retention_delta": r.avg_retention_delta,
                "avg_render_delta": r.avg_render_delta,
                "avg_upload_delta": r.avg_upload_delta,
                "last_compared_at": r.last_compared_at,
            }
            for r in rows
        ],
    }


@router.get("/templates/{template_id}/learning-stats")
def get_template_learning_stats(
    template_id: str,
    scope_key: str | None = Query(default=None),
    db: Session = Depends(deps.get_db),
) -> dict[str, Any]:
    stmt = select(TemplateLearningStat).where(TemplateLearningStat.template_id == template_id)
    if scope_key:
        stmt = stmt.where(TemplateLearningStat.scope_key == scope_key)

    rows = db.scalars(stmt.order_by(desc(TemplateLearningStat.sample_count))).all()

    if not rows:
        return {
            "template_id": template_id,
            "scope_key": scope_key,
            "summary": None,
            "stats": [],
        }

    total_samples = sum(int(r.sample_count or 0) for r in rows)
    weighted_avg_final = (
        sum((r.avg_final_priority_score or 0.0) * (r.sample_count or 0) for r in rows) / total_samples
        if total_samples > 0
        else 0.0
    )
    avg_stability = sum(float(r.stability_index or 0.0) for r in rows) / max(len(rows), 1)
    avg_dominance = sum(float(r.dominance_confidence or 0.0) for r in rows) / max(len(rows), 1)

    return {
        "template_id": template_id,
        "scope_key": scope_key,
        "summary": {
            "scopes": len(rows),
            "sample_count": total_samples,
            "avg_final_priority_score": round(weighted_avg_final, 4),
            "avg_stability_index": round(avg_stability, 4),
            "avg_dominance_confidence": round(avg_dominance, 4),
        },
        "stats": [
            {
                "id": r.id,
                "scope_key": r.scope_key,
                "sample_count": r.sample_count,
                "success_count": r.success_count,
                "failure_count": r.failure_count,
                "retry_count": r.retry_count,
                "rerender_count": r.rerender_count,
                "avg_render_score": r.avg_render_score,
                "avg_upload_score": r.avg_upload_score,
                "avg_retention_score": r.avg_retention_score,
                "avg_final_priority_score": r.avg_final_priority_score,
                "success_rate": r.success_rate,
                "retry_rate": r.retry_rate,
                "rerender_rate": r.rerender_rate,
                "avg_scene_failure_rate": r.avg_scene_failure_rate,
                "stability_index": r.stability_index,
                "reuse_effectiveness": r.reuse_effectiveness,
                "dominance_confidence": r.dominance_confidence,
                "last_7d_score": r.last_7d_score,
                "last_30d_score": r.last_30d_score,
                "trend_direction": r.trend_direction,
                "updated_from_project_id": r.updated_from_project_id,
                "updated_at": r.updated_at,
            }
            for r in rows
        ],
    }


@router.get("/templates/{template_id}/explain")
def explain_template(
    template_id: str,
    scope_key: str | None = Query(default=None),
    db: Session = Depends(deps.get_db),
) -> dict[str, Any]:
    stats_stmt = select(TemplateLearningStat).where(TemplateLearningStat.template_id == template_id)
    comp_stmt = select(TemplateCompetitionRecord).where(TemplateCompetitionRecord.template_id == template_id)

    if scope_key:
        stats_stmt = stats_stmt.where(TemplateLearningStat.scope_key == scope_key)
        comp_stmt = comp_stmt.where(TemplateCompetitionRecord.scope_key == scope_key)

    stats = db.scalars(stats_stmt.order_by(desc(TemplateLearningStat.sample_count))).all()
    competition = db.scalars(comp_stmt.order_by(desc(TemplateCompetitionRecord.sample_count))).all()

    if not stats:
        raise HTTPException(status_code=404, detail="No learning stats found for template")

    strongest = stats[0]
    win_rate = 0.0
    total_matchups = sum((c.win_count or 0) + (c.loss_count or 0) + (c.tie_count or 0) for c in competition)
    if total_matchups > 0:
        win_rate = sum(c.win_count or 0 for c in competition) / total_matchups

    reasons = []
    risks = []

    if strongest.avg_retention_score >= 85:
        reasons.append("Retention score is strong in current scope.")
    if strongest.avg_final_priority_score >= 85:
        reasons.append("Final priority score is consistently high.")
    if strongest.stability_index >= 80:
        reasons.append("Stability index is high, indicating reliable reuse.")
    if strongest.dominance_confidence >= 0.8:
        reasons.append("Dominance confidence is high against recent competition.")

    if strongest.last_7d_score < strongest.last_30d_score:
        risks.append("7-day score is below 30-day baseline.")
    if strongest.retry_rate > 0.2:
        risks.append("Retry rate is elevated.")
    if win_rate < 0.5 and total_matchups > 0:
        risks.append("Head-to-head competition win rate is weak.")

    return {
        "template_id": template_id,
        "scope_key": strongest.scope_key,
        "reasons": reasons,
        "risks": risks,
        "metrics": {
            "sample_count": strongest.sample_count,
            "avg_final_priority_score": strongest.avg_final_priority_score,
            "avg_retention_score": strongest.avg_retention_score,
            "stability_index": strongest.stability_index,
            "dominance_confidence": strongest.dominance_confidence,
            "win_rate": round(win_rate, 4),
        },
    }


@router.get("/templates/dominant-replacement-candidates")
def get_dominant_replacement_candidates(
    scope_key: str | None = Query(default=None),
    min_sample_count: int = Query(default=5, ge=1),
    db: Session = Depends(deps.get_db),
) -> dict[str, Any]:
    stmt = select(TemplateLearningStat).where(TemplateLearningStat.sample_count >= min_sample_count)
    if scope_key:
        stmt = stmt.where(TemplateLearningStat.scope_key == scope_key)

    rows = db.scalars(stmt.order_by(desc(TemplateLearningStat.avg_final_priority_score))).all()

    ranked = [
        {
            "template_id": r.template_id,
            "scope_key": r.scope_key,
            "sample_count": r.sample_count,
            "avg_final_priority_score": r.avg_final_priority_score,
            "avg_retention_score": r.avg_retention_score,
            "dominance_confidence": r.dominance_confidence,
            "trend_direction": r.trend_direction,
            "stability_index": r.stability_index,
        }
        for r in rows
    ]
    return {"scope_key": scope_key, "candidates": ranked}
