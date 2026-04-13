# MONOREPO AUDIT REPORT — 2026-04-11

## Verified from the uploaded context
- Existing hardening note says backend `compileall` and `pytest -q` passed, migration graph was reduced to one head, and frontend API routes were synced. These claims come from the uploaded hardening report and runbook.
- Migration head count in the uploaded JSON is `1`.

## Fixes applied in this optimized bundle
1. Fixed frontend incident guardrail action mapping so `reopen` is not forwarded into a narrower union.
2. Expanded the `RenderJob` frontend type to include fields already consumed by the UI from the backend payload.
3. Upgraded `next` from `15.0.0` to `15.5.9` to move off the vulnerable 15.0.x line.

## Honest limits
- I did not invent missing provider credentials, signed URL secrets, or external callback behavior.
- This bundle is still dependent on real Veo / Runway / Kling API keys and runtime endpoints.
- The uploaded repo has minimal automated tests; backend includes a smoke test and the prior uploaded report explicitly said Docker runtime smoke was not executed in sandbox.

## Backend dependencies
```txt
alembic
boto3
botocore
celery[redis]
fastapi
flower
google-genai
httpx
kombu
psycopg[binary]
PyJWT
pydantic
python-docx
python-dotenv
python-multipart
redis
sqlalchemy
uvicorn[standard]
```

## Frontend dependencies
```json
{
  "name": "render-core-frontend",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "15.5.9",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "recharts": "2.12.7"
  },
  "devDependencies": {
    "typescript": "5.6.3",
    "@types/node": "22.7.4",
    "@types/react": "18.3.3",
    "@types/react-dom": "18.3.0"
  }
}
```

## High-level tree
```txt
.env.example
.github/workflows/alembic-check.yml
.github/workflows/ci.yml
.gitignore
Makefile
README.md
TREE.txt
TREE_MERGED_PHASES.txt
backend/.env.dev
backend/.env.example
backend/Dockerfile.dev
backend/Makefile
backend/README_RUN_LOCAL.md
backend/alembic/env.py
backend/alembic/script.py.mako
backend/alembic/versions/20260408_0001_create_render_jobs_and_scene_tasks.py
backend/alembic/versions/20260408_0002_add_object_storage_fields.py
backend/alembic/versions/20260408_0003_add_provider_runtime_fields.py
backend/alembic/versions/20260408_0004_add_webhook_events_table.py
backend/alembic/versions/20260410_000001_add_render_job_storage_and_subtitles.py
backend/alembic/versions/20260410_000002_expand_render_scene_tasks_for_provider_pipeline.py
backend/alembic/versions/20260410_0005_add_provider_status_raw_nullable.py
backend/alembic/versions/20260410_0006_backfill_provider_status_raw.py
backend/alembic/versions/20260410_0007_enforce_provider_status_raw_not_null.py
backend/alembic/versions/20260410_0008_add_state_transition_events_table.py
backend/alembic/versions/20260410_0009_add_render_timeline_and_health_snapshot.py
backend/alembic/versions/20260410_0010_add_render_incident_state_and_actions.py
backend/alembic/versions/20260410_0011_add_render_incident_saved_views.py
backend/alembic/versions/20260410_0012_add_rbac_and_bulk_audit.py
backend/alembic/versions/20260411_0013_merge_post_merge_heads.py
backend/alembic.ini
backend/app/__init__.py
backend/app/api/__init__.py
backend/app/api/health.py
backend/app/api/orchestration_timeline.py
backend/app/api/project_from_preview.py
backend/app/api/provider_callbacks.py
backend/app/api/provider_payload_preview.py
backend/app/api/render_dashboard.py
backend/app/api/render_events.py
backend/app/api/render_execution.py
backend/app/api/render_job_health.py
backend/app/api/render_job_status.py
backend/app/api/script_regeneration_routes.py
backend/app/api/script_upload_preview.py
backend/app/api/script_validation.py
backend/app/api/storage.py
backend/app/core/__init__.py
backend/app/core/celery_app.py
backend/app/core/config.py
backend/app/db/__init__.py
backend/app/db/base.py
backend/app/db/session.py
backend/app/enums/provider.py
backend/app/enums/render_state.py
backend/app/main.py
backend/app/media/subtitle_burner.py
backend/app/media/video_merger.py
backend/app/models/__init__.py
backend/app/models/provider_webhook_event.py
backend/app/models/render_incident_action.py
backend/app/models/render_incident_bulk_action_item.py
backend/app/models/render_incident_bulk_action_run.py
backend/app/models/render_incident_saved_view.py
backend/app/models/render_incident_state.py
backend/app/models/render_job.py
backend/app/models/render_operator_access_profile.py
backend/app/models/render_scene_task.py
backend/app/models/render_timeline_event.py
backend/app/models/state_transition_event.py
backend/app/providers/base.py
backend/app/providers/factory.py
backend/app/schemas/__init__.py
backend/app/schemas/provider_common.py
backend/app/schemas/render_access_control.py
backend/app/schemas/render_bulk_audit.py
backend/app/schemas/render_console_explainability.py
backend/app/schemas/render_dashboard_incidents.py
backend/app/schemas/render_dashboard_summary.py
backend/app/schemas/render_events.py
backend/app/schemas/render_execution.py
backend/app/schemas/render_health.py
backend/app/schemas/render_incident_history.py
backend/app/schemas/render_incident_saved_views.py
backend/app/schemas/render_incident_work_surface.py
backend/app/schemas/render_job_list.py
backend/app/schemas/render_job_status.py
backend/app/schemas/render_productivity.py
backend/app/schemas/script_preview.py
backend/app/schemas/state_transition_event.py
backend/app/schemas/storage.py
backend/app/schemas/validation.py
backend/app/services/__init__.py
backend/app/services/asset_collector.py
backend/app/services/asset_uploader.py
backend/app/services/callback_verifier.py
backend/app/services/final_timeline_builder.py
backend/app/services/healthcheck_service.py
backend/app/services/object_storage.py
backend/app/services/provider_callback_service.py
backend/app/services/provider_capability_registry.py
backend/app/services/provider_registry.py
backend/app/services/provider_router.py
backend/app/services/provider_scene_planner.py
backend/app/services/render_access_control.py
backend/app/services/render_console_explainability.py
backend/app/services/render_dashboard_summary.py
backend/app/services/render_dispatch_service.py
backend/app/services/render_fsm.py
backend/app/services/render_incident_bulk_audit.py
backend/app/services/render_incident_history.py
backend/app/services/render_incident_projector.py
backend/app/services/render_incident_saved_views.py
backend/app/services/render_incident_work_surface.py
backend/app/services/render_job_health.py
backend/app/services/render_plan.py
backend/app/services/render_poll_service.py
backend/app/services/render_productivity_board.py
backend/app/services/render_provider_registry.py
backend/app/services/render_queue.py
backend/app/services/render_repository.py
backend/app/services/render_timeline_dedupe.py
backend/app/services/render_timeline_poll_writer.py
backend/app/services/render_timeline_writer.py
backend/app/services/script_ingestion.py
backend/app/services/script_preview_validation.py
backend/app/services/script_regeneration.py
backend/app/services/script_validation_issues.py
backend/app/services/signed_url_service.py
backend/app/services/state_transition_audit.py
backend/app/services/storage_service.py
backend/app/services/subtitle_burner.py
backend/app/services/video_merger.py
backend/app/workers/__init__.py
backend/app/workers/render_dispatch_worker.py
backend/app/workers/render_poll_worker.py
backend/app/workers/render_postprocess_worker.py
backend/app/workers/render_tasks.py
backend/app/workers/stuck_job_recovery_worker.py
backend/docker-compose.dev.yml
backend/docs/migration_review_policy.md
backend/docs/migration_workflow.md
backend/docs/zero_downtime_migration_checklist.md
backend/pytest.ini
backend/requirements.txt
backend/scripts/bootstrap-env.sh
backend/scripts/check_autogenerate_clean.py
backend/scripts/check_migration_head.py
backend/scripts/check_missing_migration.py
backend/scripts/start-api.sh
backend/scripts/start-beat.sh
backend/scripts/start-worker.sh
backend/scripts/wait_for_postgres.py
backend/seed_mock_job.py
backend/tests/test_smoke_imports.py
docker-compose.yml
docs/CONTINUATION_PATCH_2026-04-11.md
docs/DEPENDENCIES.md
docs/DEPLOYMENT.md
docs/E2E_CHECKLIST.md
docs/FRONTEND_DASHBOARD_PLANE_PATCH_2026-04-11.md
docs/FRONTEND_INCIDENT_DRAWER_AND_RECONCILIATION_PATCH_2026-04-11.md
docs/FRONTEND_OPERATIONAL_PANEL_PATCH_2026-04-11.md
docs/INCIDENT_HISTORY_AND_NOTE_PERSISTENCE_PATCH_2026-04-11.md
docs/INCIDENT_PROJECTION_RESOLVE_REOPEN_PATCH_2026-04-11.md
docs/INCIDENT_WORK_SURFACE_PATCH_2026-04-11.md
docs/INCIDENT_WORK_SURFACE_PHASE2_PATCH_2026-04-11.md
docs/INCIDENT_WORK_SURFACE_PHASE3_GOVERNANCE_PATCH_2026-04-11.md
docs/LOCAL_DEV.md
docs/MERGE_ALL_PHASES_MANIFEST_2026-04-11.json
docs/MERGE_ALL_PHASES_PROVENANCE_2026-04-11.md
docs/MIGRATION_HEADS_CHECK_2026-04-11.json
docs/POST_MERGE_HARDENING_RESULTS_2026-04-11.md
docs/RUNBOOK_POST_MERGE.md
docs/SOURCE_PROVENANCE.md
docs/TEAM_OPERATIONS_CONSOLE_PHASE4_PATCH_2026-04-11(1).md
docs/TEAM_OPERATIONS_CONSOLE_PHASE4_PATCH_2026-04-11.md
docs/TEAM_OPERATIONS_CONSOLE_PHASE5_EXPLAINABILITY_PATCH_2026-04-11(1).md
docs/TEAM_OPERATIONS_CONSOLE_PHASE5_EXPLAINABILITY_PATCH_2026-04-11.md
frontend/.env.local
frontend/.env.local.example
frontend/Dockerfile
frontend/next-env.d.ts
frontend/next.config.js
frontend/package-lock.json
frontend/package.json
frontend/src/app/globals.css
frontend/src/app/layout.tsx
frontend/src/app/page.tsx
frontend/src/components/DashboardShell.tsx
frontend/src/components/IncidentDrawer.tsx
frontend/src/components/InlineFieldError.tsx
frontend/src/components/PreviewEditingLayer.tsx
frontend/src/components/RealtimeProgressUI.tsx
frontend/src/components/ScriptUploadPreviewFlow.tsx
frontend/src/components/Sidebar.tsx
frontend/src/components/ToastViewport.tsx
frontend/src/components/ValidationPanel.tsx
frontend/src/hooks/useFieldRegistry.ts
frontend/src/lib/api.ts
frontend/src/lib/field-highlight.ts
frontend/src/lib/preview-editing.ts
frontend/src/lib/useProjectEvents.ts
frontend/src/lib/validation-field-key.ts
frontend/src/lib/validation-map.ts
frontend/tsconfig.json
```
