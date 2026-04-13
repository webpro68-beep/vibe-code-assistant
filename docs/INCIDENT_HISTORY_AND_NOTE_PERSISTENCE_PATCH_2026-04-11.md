# Incident history + note persistence patch — 2026-04-11

## Scope
This patch moves the dashboard incident drawer from local-only note behavior to persisted workflow state.

## Backend additions
- Added `backend/app/schemas/render_incident_history.py`
- Added `backend/app/services/render_incident_history.py`
- Extended `backend/app/api/render_dashboard.py` with:
  - `GET /api/v1/render/dashboard/incidents/{incident_key}`
  - `GET /api/v1/render/dashboard/incidents/{incident_key}/history`
  - `PUT /api/v1/render/dashboard/incidents/{incident_key}/note`

## Backend behavior
- Reads persisted incident state from `render_incident_states`
- Reads persisted workflow actions from `render_incident_actions`
- Reads nearby timeline context from `render_timeline_events`
- Persists notes to `render_incident_states.note`
- Appends `note_updated` into `render_incident_actions`

## Frontend additions
- Extended `frontend/src/lib/api.ts` with:
  - `getRenderIncidentHistory()`
  - `updateRenderIncidentNote()`
  - incident history / state / action interfaces
- Updated `frontend/src/components/IncidentDrawer.tsx` to show:
  - persisted workflow history
  - persisted timeline history
  - backend note save button
- Updated `frontend/src/app/render-jobs/page.tsx` to:
  - fetch incident detail/history from backend
  - save notes to backend
  - refresh drawer after actions and note saves
  - stop using browser-local note storage for this drawer

## Verification
- `python -m compileall backend/app` ✅
- `pytest -q` ✅

## Known limitations
- Frontend workspace still contains older type/build issues unrelated to this patch because the extracted repo is missing usable Next/React type dependencies in this sandbox.
- Drawer history currently uses a practical backend slice of nearby job timeline events, not a dedicated incident-only timeline table.
