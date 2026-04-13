from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.script_ingestion import build_preview_payload, parse_script_file_bytes, validate_script_file

router = APIRouter(tags=["script-upload-preview"])


@router.post("/api/v1/script-upload/preview")
async def script_upload_preview(
    file: UploadFile = File(...),
    aspect_ratio: str = Form("9:16"),
    target_platform: str = Form("shorts"),
    style_preset: str | None = Form(default=None),
):
    try:
        content = await file.read()
        ext = validate_script_file(file.filename or "", content)
        script_text = parse_script_file_bytes(ext, content)
        preview = build_preview_payload(
            filename=file.filename,
            script_text=script_text,
            aspect_ratio=aspect_ratio,
            target_platform=target_platform,
            style_preset=style_preset,
        )
        return {
            "ok": True,
            "data": preview,
            "error": None,
            "meta": {
                "scene_count": len(preview.get("scenes", [])),
                "subtitle_count": len(preview.get("subtitle_segments", [])),
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to build script preview") from exc
