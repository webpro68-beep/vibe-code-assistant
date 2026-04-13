from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.template_runtime import TemplateExtractedDraft, TemplateReusePreview


class TemplatePreviewBuilder:
    """
    Build cached reuse previews from extracted template drafts.

    This intentionally avoids depending on any separate template-library table,
    so it can plug directly into the current runtime-scoring phase.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_build_preview(
        self,
        template_id: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        template = self._get_template(template_id)
        base_preview = template.preview_payload or self._build_preview_payload(template.template_payload)
        preview_hash = self._preview_hash(template_id=template_id, preview=base_preview, overrides=overrides)

        cached = self.db.scalar(
            select(TemplateReusePreview).where(
                TemplateReusePreview.template_id == template_id,
                TemplateReusePreview.preview_hash == preview_hash,
            )
        )
        if cached:
            return cached.preview_payload

        merged = self._apply_overrides(base_preview, overrides or {})
        reusable = TemplateReusePreview(
            template_id=template_id,
            preview_hash=preview_hash,
            preview_payload=merged,
            warnings_json=merged.get("warnings") or [],
            editable_fields_json=merged.get("editable_fields") or [],
        )
        self.db.add(reusable)
        self.db.commit()
        self.db.refresh(reusable)
        return reusable.preview_payload

    def build_project_payload(
        self,
        template_id: str,
        user_inputs: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        template = self._get_template(template_id)
        preview = self.get_or_build_preview(template_id=template_id, overrides=overrides)
        template_payload = template.template_payload or {}

        project_payload = {
            "source_mode": "template",
            "status": "ready_to_render",
            "project_status": "ready_to_render",
            "template_id": template_id,
            "title": (user_inputs or {}).get("title") or preview.get("template_name"),
            "theme": (user_inputs or {}).get("theme"),
            "ratio": preview.get("ratio"),
            "platform": preview.get("platform"),
            "style": (preview.get("style_summary") or {}).get("style") or {},
            "subtitles": (preview.get("style_summary") or {}).get("subtitles") or {},
            "transitions": (preview.get("style_summary") or {}).get("transitions") or {},
            "render_settings": preview.get("render_defaults") or {},
            "prompt_defaults": template_payload.get("prompt_defaults") or {},
            "scenes": self._build_scenes_from_blueprint(
                scene_blueprint=preview.get("scene_blueprint") or [],
                user_inputs=user_inputs or {},
            ),
            "template_reuse_meta": {
                "template_scope_key": preview.get("scope_key"),
                "template_type": preview.get("template_type"),
                "editable_fields": preview.get("editable_fields") or [],
            },
        }
        return project_payload

    def _get_template(self, template_id: str) -> TemplateExtractedDraft:
        template = self.db.get(TemplateExtractedDraft, template_id)
        if template is None:
            raise ValueError(f"TemplateExtractedDraft not found: {template_id}")
        return template

    def _build_preview_payload(self, template_payload: dict[str, Any]) -> dict[str, Any]:
        scene_blueprint = template_payload.get("scene_blueprint") or []
        return {
            "template_id": None,
            "template_name": template_payload.get("name"),
            "template_type": template_payload.get("template_type"),
            "scope_key": template_payload.get("scope_key"),
            "ratio": template_payload.get("ratio"),
            "platform": template_payload.get("platform"),
            "scene_count": template_payload.get("scene_count"),
            "style_summary": template_payload.get("style_summary") or {},
            "render_defaults": template_payload.get("render_defaults") or {},
            "scene_blueprint": scene_blueprint,
            "editable_fields": [
                "title",
                "theme",
                "style_summary.style",
                "render_defaults.quality",
                "scene_blueprint[].title",
                "scene_blueprint[].prompt_scaffold",
            ],
            "warnings": [],
        }

    def _apply_overrides(self, preview: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        if not overrides:
            return preview

        merged = json.loads(json.dumps(preview))
        for key, value in overrides.items():
            if key == "ratio":
                merged["ratio"] = value
            elif key == "platform":
                merged["platform"] = value
            elif key == "render_defaults" and isinstance(value, dict):
                merged.setdefault("render_defaults", {}).update(value)
            elif key == "style_summary" and isinstance(value, dict):
                merged.setdefault("style_summary", {}).update(value)
            elif key == "template_name":
                merged["template_name"] = value
        return merged

    def _build_scenes_from_blueprint(
        self,
        scene_blueprint: list[dict[str, Any]],
        user_inputs: dict[str, Any],
    ) -> list[dict[str, Any]]:
        scene_overrides = user_inputs.get("scene_overrides") or {}
        scenes = []

        for scene in scene_blueprint:
            position = scene.get("position")
            override = scene_overrides.get(str(position)) or scene_overrides.get(position) or {}
            built_scene = {
                "title": override.get("title") or scene.get("title"),
                "duration_seconds": override.get("duration_seconds") or scene.get("duration_seconds"),
                "shot_type": override.get("shot_type") or scene.get("shot_type"),
                "camera_motion": override.get("camera_motion") or scene.get("camera_motion"),
                "caption_style": override.get("caption_style") or scene.get("caption_style"),
                "transition_after": override.get("transition_after") or scene.get("transition_after"),
                "visual_intent": override.get("visual_intent") or (scene.get("prompt_scaffold") or {}).get("visual_intent"),
                "tone": override.get("tone") or (scene.get("prompt_scaffold") or {}).get("tone"),
                "pace": override.get("pace") or (scene.get("prompt_scaffold") or {}).get("pace"),
            }
            scenes.append(built_scene)

        return scenes

    def _preview_hash(self, template_id: str, preview: dict[str, Any], overrides: dict[str, Any] | None) -> str:
        payload = {
            "template_id": template_id,
            "preview": preview,
            "overrides": overrides or {},
        }
        stable = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(stable.encode("utf-8")).hexdigest()
