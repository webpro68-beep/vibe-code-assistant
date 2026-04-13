from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.script_preview import ScriptPreviewPayload
from app.services.script_validation_issues import validate_preview_with_issues

router = APIRouter(tags=["script-validation"])


@router.post("/api/v1/script-preview/validate")
async def validate_script_preview(preview: ScriptPreviewPayload):
    try:
        result = validate_preview_with_issues(preview.model_dump())

        return {
            "ok": True,
            "data": result.model_dump(),
            "error": None,
            "meta": {
                "issue_count": len(result.issues),
                "valid": result.valid,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to validate preview") from exc