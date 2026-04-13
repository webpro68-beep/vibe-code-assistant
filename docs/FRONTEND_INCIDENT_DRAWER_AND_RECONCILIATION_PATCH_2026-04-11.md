# Frontend Incident Drawer + Optimistic Reconciliation Patch — 2026-04-11

## Scope
This patch upgrades the dashboard plane UX in two production-feel directions:

1. **Incident drawer / detail panel on `/render-jobs`**
   - Operators can inspect and action incidents without leaving the dashboard list.
   - The selected incident is synced through `?incident=<incident_key>` in the URL.

2. **Optimistic polling reconciliation**
   - Polling continues to refresh dashboard data.
   - In-flight or recently completed optimistic incident actions are merged over polled data for a short TTL.
   - Temporary optimistic state clears automatically after the backend response catches up or the TTL expires.

## Files added
- `frontend/src/components/ToastViewport.tsx`
- `frontend/src/components/IncidentDrawer.tsx`

## Files changed
- `frontend/src/app/render-jobs/page.tsx`

## UX changes
- Dashboard incidents feed can open a detail drawer inline.
- Drawer supports:
  - acknowledge
  - assign
  - mute 1h
- Action buttons show per-incident loading state.
- Success/error feedback appears as toast notifications.
- Filters and selected incident sync into URL:
  - `provider`
  - `health`
  - `show_muted`
  - `incident`
- Added `Refresh now` and `Clear filters` controls.

## Optimistic reconciliation design
- A short-lived in-memory optimistic patch map is keyed by `incident_key`.
- Each patch has a TTL of 15 seconds.
- During each poll refresh:
  - expired patches are dropped
  - remote data that already matches the optimistic patch clears the patch
  - otherwise the optimistic patch is layered over the server payload
- On API failure the UI rolls back to the previous incident snapshot.

## Validation note
The extracted frontend bundle originally had incomplete `node_modules`, so local sandbox build validation was blocked by missing package binaries after extraction. The code patch itself is self-contained and does not require backend API changes.
