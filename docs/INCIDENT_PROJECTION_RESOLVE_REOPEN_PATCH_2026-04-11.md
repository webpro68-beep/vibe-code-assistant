# Incident Projection + Resolve/Reopen Patch — 2026-04-11

## Scope
This patch turns the incident drawer into a fuller workflow panel by adding:
- incident-specific projected timeline from backend
- resolve incident action
- reopen incident action
- drawer UX wiring for resolve/reopen

## Backend
Added/updated:
- `backend/app/schemas/render_incident_history.py`
  - `projected_timeline` added to `IncidentHistoryResponse`
- `backend/app/services/render_incident_projector.py`
  - `resolve` action write-path
  - `reopen` / `unresolve` action write-path
  - better state handling for resolved vs reopened incidents
- `backend/app/services/render_incident_history.py`
  - `build_incident_projected_timeline()`
  - merges incident action log with related timeline events into an incident-focused view
- `backend/app/api/render_dashboard.py`
  - `POST /api/v1/render/dashboard/incidents/{incident_key}/resolve`
  - `POST /api/v1/render/dashboard/incidents/{incident_key}/reopen`

## Frontend
Added/updated:
- `frontend/src/lib/api.ts`
  - `resolveRenderIncident()`
  - `reopenRenderIncident()`
  - `IncidentHistoryResponse.projected_timeline`
- `frontend/src/components/IncidentDrawer.tsx`
  - projected incident timeline block
  - Resolve button
  - Reopen button when current incident workflow status is resolved
- `frontend/src/app/render-jobs/page.tsx`
  - loads projected timeline instead of the broader history list when available
  - optimistic patching for resolve/reopen
  - backend round-trip and refresh after resolve/reopen

## Verification
Backend checked with:
- `python -m compileall backend/app`

## Notes
- The projection is incident-focused but still derived from existing job timeline and incident action log. It does not require a new `incident_timeline_events` table.
- Reopen currently operates on the incident state/read model and action log. It does not rewrite historical render timeline events.
