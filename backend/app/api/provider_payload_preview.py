from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.provider_adapters.batch_builder import build_render_payloads


RenderProvider = Literal["veo_3_1", "runway_gen4_turbo", "kling_text", "kling_image"]


class BuildProviderPayloadsRequest(BaseModel):
    provider: RenderProvider
    aspect_ratio: Literal["16:9", "9:16", "1:1"]
    style_preset: str | None = None
    planned_scenes: list[dict[str, Any]]


router = APIRouter(tags=["provider-payloads"])


@router.post("/api/v1/render/build-provider-payloads")
async def build_provider_payloads(payload: BuildProviderPayloadsRequest):
    try:
        outputs = build_render_payloads(
            planned_scenes=payload.planned_scenes,
            provider=payload.provider,
            aspect_ratio=payload.aspect_ratio,
            style_preset=payload.style_preset,
        )

        return {
            "ok": True,
            "data": {
                "provider": payload.provider,
                "payloads": outputs,
            },
            "error": None,
            "meta": {
                "count": len(outputs),
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc