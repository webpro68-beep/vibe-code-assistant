# Frontend Dashboard Plane Patch — 2026-04-11

- Adds a dashboard plane at `/render-jobs` wired to summary, jobs list, and recent incidents routes.
- Expands `/render-jobs/[jobId]` into a job detail plane reading job snapshot, health, job events, scene events, and incident actions.
- Adds a shared `DashboardShell` wrapper and extends `frontend/src/lib/api.ts` with dashboard and incident route helpers.
- Cleans `frontend/src/lib/validation-map.ts` so the frontend type-check path is no longer blocked by duplicate declarations.
