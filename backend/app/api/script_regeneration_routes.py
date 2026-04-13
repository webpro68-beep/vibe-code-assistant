from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.script_preview import ScriptPreviewPayload
from app.services.script_regeneration import (
    recalculate_all_payload,
    recalculate_durations_payload,
    rebuild_subtitles_payload,
)

router = APIRouter(tags=["script-regeneration"])


@router.post("/api/v1/script-preview/rebuild-subtitles")
async def rebuild_subtitles(preview: ScriptPreviewPayload):
    try:
        payload = rebuild_subtitles_payload(preview.model_dump())
        return {"ok": True, "data": payload, "error": None, "meta": {}}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/script-preview/recalculate-durations")
async def recalc_durations(preview: ScriptPreviewPayload):
    try:
        payload = recalculate_durations_payload(preview.model_dump())
        return {"ok": True, "data": payload, "error": None, "meta": {}}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/script-preview/recalculate-all")
async def recalc_all(preview: ScriptPreviewPayload):
    try:
        payload = recalculate_all_payload(preview.model_dump())
        return {"ok": True, "data": payload, "error": None, "meta": {}}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
