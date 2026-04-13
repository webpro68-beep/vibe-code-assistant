from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.template_runtime import (
    TemplateEvolutionEvent,
    TemplateExtractedDraft,
    TemplateExtractionJob,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ExtractionDecision:
    allowed: bool
    fingerprint: str | None
    reason: str | None = None


class TemplateExtractionService:
    """
    Extract reusable template drafts from a successfully rendered project.

    Assumptions kept intentionally narrow:
    - project is file-backed at storage/projects/<project_id>/project.json
    - render success has already happened before this service is called
    - output is persisted as TemplateExtractedDraft for reuse/preview/create flows
    """

    def __init__(self, db: Session, storage_root: str = "storage") -> None:
        self.db = db
        self.storage_root = Path(storage_root)

    def enqueue_or_get_existing(
        self,
        project_id: str,
        source_render_job_id: str | None = None,
        force: bool = False,
    ) -> TemplateExtractionJob:
        project_json = self._load_project_json(project_id)
        decision = self.should_extract(project_id=project_id, project_json=project_json, force=force)

        if not decision.allowed:
            existing = self._find_existing_job_by_fingerprint(project_id, decision.fingerprint) if decision.fingerprint else None
            if existing:
                return existing

            job = TemplateExtractionJob(
                project_id=project_id,
                source_render_job_id=source_render_job_id,
                status="skipped",
                source_project_fingerprint=decision.fingerprint or self._fingerprint_payload({"project_id": project_id}),
                reason=decision.reason,
                extraction_summary_json={"skipped": True, "reason": decision.reason},
            )
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            return job

        existing = self._find_existing_job_by_fingerprint(project_id, decision.fingerprint)
        if existing:
            return existing

        job = TemplateExtractionJob(
            project_id=project_id,
            source_render_job_id=source_render_job_id,
            status="pending",
            source_project_fingerprint=decision.fingerprint,
            reason="queued",
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def run_job(self, job_id: str) -> TemplateExtractionJob:
        job = self.db.get(TemplateExtractionJob, job_id)
        if job is None:
            raise ValueError(f"TemplateExtractionJob not found: {job_id}")

        if job.status == "succeeded":
            return job

        job.status = "running"
        job.started_at = utcnow()
        self.db.add(job)
        self.db.commit()

        try:
            project_json = self._load_project_json(job.project_id)
            payload = self.build_template_payload(job.project_id, project_json)
            preview_payload = self.build_preview_payload(payload)

            draft = self._persist_extracted_draft(
                project_id=job.project_id,
                source_render_job_id=job.source_render_job_id,
                source_project_fingerprint=job.source_project_fingerprint,
                payload=payload,
                preview_payload=preview_payload,
                extraction_job_id=job.id,
            )

            job.output_template_id = draft.id
            job.status = "succeeded"
            job.finished_at = utcnow()
            job.reason = "extracted"
            job.extraction_summary_json = {
                "template_id": draft.id,
                "scene_count": draft.scene_count,
                "ratio": draft.ratio,
                "platform": draft.platform,
            }
            self.db.add(job)

            self._log_evolution_event(
                template_id=draft.id,
                event_type="extracted",
                source_project_id=job.project_id,
                source_render_job_id=job.source_render_job_id,
                payload={
                    "scene_count": draft.scene_count,
                    "ratio": draft.ratio,
                    "platform": draft.platform,
                    "scope_key": draft.scope_key,
                },
            )

            self.db.commit()
            self.db.refresh(job)
            return job

        except Exception as exc:
            job.status = "failed"
            job.finished_at = utcnow()
            job.error_message = str(exc)
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            return job

    def should_extract(self, project_id: str, project_json: dict[str, Any], force: bool = False) -> ExtractionDecision:
        if force:
            return ExtractionDecision(allowed=True, fingerprint=self._fingerprint_payload(project_json))

        if not isinstance(project_json, dict):
            return ExtractionDecision(allowed=False, fingerprint=None, reason="project_json_invalid")

        status = str(project_json.get("status") or project_json.get("project_status") or "").lower()
        render_status = str(project_json.get("render_status") or "").lower()

        final_video_url = (
            project_json.get("final_video_url")
            or project_json.get("final_url")
            or project_json.get("output_url")
        )

        if project_json.get("template_extraction_disabled") is True:
            return ExtractionDecision(allowed=False, fingerprint=None, reason="template_extraction_disabled")

        if not final_video_url:
            return ExtractionDecision(allowed=False, fingerprint=None, reason="missing_final_video_url")

        if render_status in {"failed", "error", "canceled", "cancelled"}:
            return ExtractionDecision(allowed=False, fingerprint=None, reason=f"render_status_{render_status}")

        final_ready_markers = {"final_render_ready", "ready", "completed", "succeeded", "success"}
        if status not in final_ready_markers and render_status not in final_ready_markers:
            return ExtractionDecision(allowed=False, fingerprint=None, reason="project_not_final_render_ready")

        fingerprint = self._fingerprint_payload(project_json)
        existing = self._find_existing_job_by_fingerprint(project_id, fingerprint)
        if existing and existing.status in {"pending", "running", "succeeded"}:
            return ExtractionDecision(allowed=False, fingerprint=fingerprint, reason=f"already_{existing.status}")

        return ExtractionDecision(allowed=True, fingerprint=fingerprint)

    def build_template_payload(self, project_id: str, project_json: dict[str, Any]) -> dict[str, Any]:
        scenes = project_json.get("scenes") or []
        ratio = str(project_json.get("ratio") or project_json.get("aspect_ratio") or "16:9")
        platform = str(project_json.get("platform") or project_json.get("target_platform") or "generic")
        style = project_json.get("style") or {}
        render_settings = project_json.get("render_settings") or {}
        subtitles = project_json.get("subtitles") or {}
        prompt_defaults = project_json.get("prompt_defaults") or {}
        transitions = project_json.get("transitions") or project_json.get("default_transitions") or {}

        scene_blueprint = []
        for index, scene in enumerate(scenes, start=1):
            scene_blueprint.append(
                {
                    "position": index,
                    "title": scene.get("title"),
                    "duration_seconds": scene.get("duration_seconds"),
                    "shot_type": scene.get("shot_type"),
                    "camera_motion": scene.get("camera_motion"),
                    "caption_style": scene.get("caption_style") or subtitles.get("style"),
                    "transition_after": scene.get("transition_after"),
                    "prompt_scaffold": {
                        "visual_intent": scene.get("visual_intent"),
                        "tone": scene.get("tone") or style.get("tone"),
                        "pace": scene.get("pace"),
                    },
                }
            )

        scope_key = self._build_scope_key(platform=platform, ratio=ratio, project_json=project_json)

        payload = {
            "schema_version": "template-extraction-v1",
            "template_type": "extracted_runtime_template",
            "project_id": project_id,
            "name": self._derive_template_name(project_json),
            "scope_key": scope_key,
            "platform": platform,
            "ratio": ratio,
            "scene_count": len(scene_blueprint),
            "style_summary": {
                "style": style,
                "subtitles": subtitles,
                "transitions": transitions,
            },
            "render_defaults": {
                "provider": render_settings.get("provider"),
                "quality": render_settings.get("quality"),
                "fps": render_settings.get("fps"),
                "codec": render_settings.get("codec"),
                "duration_target_seconds": render_settings.get("duration_target_seconds"),
            },
            "prompt_defaults": prompt_defaults,
            "scene_blueprint": scene_blueprint,
            "reusable_rules": {
                "allow_project_specific_text_override": True,
                "allow_asset_override": True,
                "extract_only_after_final_success": True,
            },
            "source_metadata": {
                "source_mode": project_json.get("source_mode"),
                "created_from": project_json.get("created_from"),
                "theme": project_json.get("theme"),
            },
        }
        return payload

    def build_preview_payload(self, template_payload: dict[str, Any]) -> dict[str, Any]:
        scene_blueprint = template_payload.get("scene_blueprint") or []

        editable_fields = [
            "title",
            "theme",
            "prompt_defaults",
            "style_summary.style",
            "render_defaults.quality",
            "render_defaults.duration_target_seconds",
            "scene_blueprint[].title",
            "scene_blueprint[].prompt_scaffold",
        ]

        warnings = []
        if len(scene_blueprint) == 0:
            warnings.append("Template has no scenes.")
        if not template_payload.get("render_defaults", {}).get("provider"):
            warnings.append("No default provider stored in render_defaults.")
        if not template_payload.get("platform"):
            warnings.append("Platform not detected from source project.")

        preview = {
            "template_id": None,
            "template_name": template_payload.get("name"),
            "template_type": template_payload.get("template_type"),
            "scope_key": template_payload.get("scope_key"),
            "ratio": template_payload.get("ratio"),
            "platform": template_payload.get("platform"),
            "scene_count": template_payload.get("scene_count"),
            "style_summary": template_payload.get("style_summary"),
            "render_defaults": template_payload.get("render_defaults"),
            "scene_blueprint": scene_blueprint,
            "expected_duration_range_seconds": self._estimate_duration_range(scene_blueprint),
            "editable_fields": editable_fields,
            "warnings": warnings,
        }
        return preview

    def _persist_extracted_draft(
        self,
        project_id: str,
        source_render_job_id: str | None,
        source_project_fingerprint: str,
        payload: dict[str, Any],
        preview_payload: dict[str, Any],
        extraction_job_id: str,
    ) -> TemplateExtractedDraft:
        existing = self.db.scalar(
            select(TemplateExtractedDraft).where(
                TemplateExtractedDraft.source_project_fingerprint == source_project_fingerprint
            )
        )
        if existing:
            return existing

        template_id = f"tplx_{uuid.uuid4().hex[:20]}"
        preview_payload["template_id"] = template_id

        draft = TemplateExtractedDraft(
            id=template_id,
            extraction_job_id=extraction_job_id,
            project_id=project_id,
            source_render_job_id=source_render_job_id,
            name=str(payload.get("name") or f"Extracted Template {template_id}"),
            status="draft_extracted",
            scope_key=payload.get("scope_key"),
            ratio=payload.get("ratio"),
            platform=payload.get("platform"),
            scene_count=int(payload.get("scene_count") or 0),
            source_project_fingerprint=source_project_fingerprint,
            template_payload=payload,
            preview_payload=preview_payload,
            tags_json=self._derive_tags(payload),
        )
        self.db.add(draft)
        self.db.flush()
        return draft

    def _load_project_json(self, project_id: str) -> dict[str, Any]:
        project_path = self.storage_root / "projects" / project_id / "project.json"
        if not project_path.exists():
            raise FileNotFoundError(f"project.json not found for project {project_id}: {project_path}")

        with project_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid project.json for project {project_id}: root is not an object")
        return data

    def _find_existing_job_by_fingerprint(self, project_id: str, fingerprint: str | None) -> TemplateExtractionJob | None:
        if not fingerprint:
            return None
        return self.db.scalar(
            select(TemplateExtractionJob).where(
                TemplateExtractionJob.project_id == project_id,
                TemplateExtractionJob.source_project_fingerprint == fingerprint,
            )
        )

    def _fingerprint_payload(self, payload: dict[str, Any]) -> str:
        stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()

    def _derive_template_name(self, project_json: dict[str, Any]) -> str:
        title = project_json.get("title") or project_json.get("name") or "Untitled Project"
        ratio = project_json.get("ratio") or project_json.get("aspect_ratio") or "16:9"
        platform = project_json.get("platform") or project_json.get("target_platform") or "generic"
        return f"{title} — Extracted {platform} {ratio}"

    def _build_scope_key(self, platform: str, ratio: str, project_json: dict[str, Any]) -> str:
        source_mode = str(project_json.get("source_mode") or "generic")
        return f"platform:{platform}|ratio:{ratio}|source:{source_mode}"

    def _estimate_duration_range(self, scene_blueprint: list[dict[str, Any]]) -> dict[str, int]:
        durations = [int(s.get("duration_seconds") or 0) for s in scene_blueprint if s.get("duration_seconds")]
        if not durations:
            return {"min": 15, "max": 60}
        total = sum(durations)
        return {"min": max(5, int(total * 0.9)), "max": int(total * 1.1)}

    def _derive_tags(self, payload: dict[str, Any]) -> list[str]:
        tags = []
        if payload.get("platform"):
            tags.append(str(payload["platform"]))
        if payload.get("ratio"):
            tags.append(str(payload["ratio"]))
        if payload.get("scene_count") is not None:
            tags.append(f"scenes:{payload['scene_count']}")
        scope_key = payload.get("scope_key")
        if scope_key:
            tags.append(scope_key)
        return tags

    def _log_evolution_event(
        self,
        template_id: str,
        event_type: str,
        source_project_id: str | None,
        source_render_job_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = TemplateEvolutionEvent(
            template_id=template_id,
            event_type=event_type,
            source_project_id=source_project_id,
            source_render_job_id=source_render_job_id,
            payload_json=payload or {},
        )
        self.db.add(event)
