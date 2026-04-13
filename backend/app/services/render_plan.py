from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, Any

from app.services.provider_scene_planner import plan_provider_scenes
from app.services.render_provider_registry import get_provider_capabilities


RenderProvider = Literal["veo_3_1", "runway_gen4", "kling_3"]


class PrepareRenderPlanRequest(BaseModel):
    provider: RenderProvider
    aspect_ratio: Literal["9:16", "16:9", "1:1"]
    scenes: list[dict[str, Any]]


router = APIRouter(tags=["render-plan"])


@router.post("/api/v1/render/prepare-plan")
async def prepare_render_plan(payload: PrepareRenderPlanRequest):
    try:
        caps = get_provider_capabilities(payload.provider)
        planned_scenes = plan_provider_scenes(payload.scenes, payload.provider)

        return {
            "ok": True,
            "data": {
                "provider": payload.provider,
                "provider_label": caps.label,
                "aspect_ratio": payload.aspect_ratio,
                "supports_native_audio": caps.supports_native_audio,
                "supports_multi_shot_prompt": caps.supports_multi_shot_prompt,
                "planned_scenes": planned_scenes,
            },
            "error": None,
            "meta": {
                "scene_count_before": len(payload.scenes),
                "scene_count_after": len(planned_scenes),
                "max_scene_duration_sec": caps.max_scene_duration_sec,
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc