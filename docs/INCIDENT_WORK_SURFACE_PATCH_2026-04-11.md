# INCIDENT WORK SURFACE PATCH — 2026-04-11

## Scope
Upgrade the dashboard from a per-incident panel into a work surface with:
- incident list segmentation
- saved incident views
- bulk incident actions

## Backend
Added:
- `backend/app/models/render_incident_saved_view.py`
- `backend/app/schemas/render_incident_saved_views.py`
- `backend/app/services/render_incident_saved_views.py`
- `backend/alembic/versions/20260410_0011_add_render_incident_saved_views.py`

Updated:
- `backend/app/api/render_dashboard.py`
- `backend/app/services/render_dashboard_summary.py`
- `backend/app/models/__init__.py`

### New routes
- `GET /api/v1/render/dashboard/incidents/views`
- `POST /api/v1/render/dashboard/incidents/views`
- `PUT /api/v1/render/dashboard/incidents/views/{view_id}`
- `DELETE /api/v1/render/dashboard/incidents/views/{view_id}`
- `POST /api/v1/render/dashboard/incidents/bulk/acknowledge`
- `POST /api/v1/render/dashboard/incidents/bulk/assign`
- `POST /api/v1/render/dashboard/incidents/bulk/mute`
- `POST /api/v1/render/dashboard/incidents/bulk/resolve`

### Incident list filters extended
`GET /api/v1/render/dashboard/incidents/recent` now supports:
- `provider`
- `workflow_status`
- `assigned_to`
- `segment`
- `show_muted`
- `limit`

### Segments implemented
- `active`
- `untriaged`
- `assigned`
- `muted`
- `resolved`
- `mine`

## Frontend
Updated:
- `frontend/src/app/render-jobs/page.tsx`
- `frontend/src/lib/api.ts`

### New UX capabilities
- segment tabs for incident inbox
- saved views panel
- save current filter set as reusable view
- apply/delete saved view
- multi-select incidents on current page
- bulk acknowledge / assign / mute / resolve
- bulk action optimistic patching on current page

## Validation run
- `python -m compileall backend/app` ✅
- `pytest -q` ✅

## Honest notes
- frontend build was not validated end-to-end in sandbox because the extracted bundle still has incomplete Next/React dependency/runtime state from earlier steps.
- saved views are owner/shared only in this patch; team/role ACL was not introduced here.
