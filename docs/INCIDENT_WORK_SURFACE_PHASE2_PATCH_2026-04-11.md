# INCIDENT WORK SURFACE PHASE 2 PATCH — 2026-04-11

This patch extends the incident dashboard from a usable operator surface into a more team-lead friendly work surface.

## Added

### Backend
- `GET /api/v1/render/dashboard/incidents/metrics`
  - returns queue metrics grouped by segment
  - includes totals, unacknowledged, assigned, muted, resolved, stale over 30m, and high severity counts
- `POST /api/v1/render/dashboard/incidents/bulk/{action_type}/preview`
  - supports `acknowledge`, `assign`, `mute`, `resolve`
  - returns dry-run eligibility and predicted state without mutating incident state
- new shared work-surface schemas in:
  - `backend/app/schemas/render_incident_work_surface.py`
- new work-surface service:
  - `backend/app/services/render_incident_work_surface.py`

### Frontend
- dashboard segment metrics panel
- bulk preview / dry-run panel before executing bulk actions
- saved incident view edit/update UX for owner-managed views
- view editor keeps current dashboard filters as the source of truth when updating a view

## Notes
- bulk preview is read-only and does not write `render_incident_actions`
- metrics are computed from `render_incident_states`, so they are lightweight and align with current workflow state
- no new migration was required in this phase
