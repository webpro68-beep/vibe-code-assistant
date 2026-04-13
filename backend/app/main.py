from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.health import router as health_router
from app.api.project_from_preview import router as project_from_preview_router
from app.api.project_workspace import router as project_workspace_router
from app.api.provider_callbacks import router as provider_callbacks_router
from app.api.provider_payload_preview import router as provider_payload_preview_router
from app.api.render_execution import router as render_execution_router
from app.api.render_job_status import router as render_job_status_router
from app.api.script_regeneration_routes import router as script_regeneration_router
from app.api.script_upload_preview import router as script_upload_preview_router
from app.api.script_validation import router as script_validation_router
from app.api.storage import router as storage_router
from app.api.render_dashboard import router as render_dashboard_router
from app.api.render_job_health import router as render_job_health_router
from app.api.render_events import router as render_events_router
from app.api.orchestration_timeline import router as orchestration_timeline_router
from app.api.decision_engine import router as decision_engine_router
from app.api.control_plane import router as control_plane_router
from app.api.autopilot import router as autopilot_router
from app.api.observability import router as observability_router
from app.api.audio import router as audio_router
from app.api.strategy import router as strategy_router
from app.api.production import router as production_router
from app.api.templates import router as templates_router
from app.api.template_runtime import router as template_runtime_router
from app.api.veo_workspace import router as veo_workspace_router
from app.api.template_extraction import router as template_extraction_router
from app.api.template_governance_scheduling import router as template_governance_scheduling_router
from app.core.config import settings

app = FastAPI(
    title="Render Factory API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        settings.public_base_url.rstrip("/"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_storage_dir = Path("storage")
_storage_dir.mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(_storage_dir)), name="storage")

app.include_router(health_router)
app.include_router(script_upload_preview_router)
app.include_router(script_validation_router)
app.include_router(script_regeneration_router)
app.include_router(project_from_preview_router)
app.include_router(project_workspace_router)
app.include_router(provider_payload_preview_router)
app.include_router(render_execution_router)
app.include_router(render_job_status_router)
app.include_router(provider_callbacks_router)
app.include_router(storage_router)
app.include_router(render_dashboard_router)
app.include_router(render_job_health_router)
app.include_router(render_events_router)
app.include_router(orchestration_timeline_router)
app.include_router(decision_engine_router)
app.include_router(control_plane_router)
app.include_router(autopilot_router)
app.include_router(observability_router)
app.include_router(audio_router)
app.include_router(strategy_router)
app.include_router(production_router)
app.include_router(templates_router)
app.include_router(template_runtime_router)
app.include_router(veo_workspace_router)
app.include_router(template_extraction_router)
app.include_router(template_governance_scheduling_router)


@app.get("/", tags=["root"])
async def root() -> dict[str, object]:
    return {
        "ok": True,
        "service": "render_factory_api",
        "env": settings.app_env,
        "docs_url": "/docs",
        "health_url": "/healthz",
    }


@app.get("/metrics")
async def metrics_alias():
    from app.db.session import SessionLocal
    from fastapi.responses import PlainTextResponse
    from app.services.observability_metrics import collect_status_snapshot, export_prometheus_text

    db = SessionLocal()
    try:
        snapshot = collect_status_snapshot(db)
        return PlainTextResponse(export_prometheus_text(snapshot), media_type="text/plain; version=0.0.4")
    finally:
        db.close()
