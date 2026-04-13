# FRONTEND OPERATIONAL PANEL PATCH — 2026-04-11

## Scope completed
- Deepened the incident drawer into an operational panel on `/render-jobs`
- Added a history mini-timeline sourced from `GET /api/v1/render/jobs/{job_id}/events`
- Added a dedicated action reason input for acknowledge / assign / mute
- Added a note box with local persistence per `incident_key`

## Files changed
- `frontend/src/app/render-jobs/page.tsx`
- `frontend/src/components/IncidentDrawer.tsx`

## Behavior
### History mini-timeline
- Loads job-level events when an incident is selected
- Builds a compact timeline focused on:
  - `job_health_*`
  - `scene_failed`
  - `scene_processing_stalled`
  - `scene_processing_recovered`
  - nearby events within a time window around the incident

### Note box
- Stored in browser `localStorage`
- Keyed by `incident_key`
- Explicit save/clear actions
- Clearly labeled as local-only until backend gets a note endpoint

### Action reason input
- Separate textarea in the drawer
- Sent through existing backend action routes via `reason`
- If empty, frontend auto-builds a fallback reason
- If local note exists and action reason is empty, note content is appended to fallback reason

## Why local note instead of backend persistence
Current backend routes in scope expose incident actions:
- acknowledge
- assign
- mute

But there is no dedicated note-only write endpoint in the current merged repo. This patch stays honest to that constraint and does not invent a backend contract.
