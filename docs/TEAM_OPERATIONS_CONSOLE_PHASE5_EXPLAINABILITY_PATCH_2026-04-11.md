# Phase 5 Patch — Explainable Console Layer

Added in this patch:

- saved view effective-access preview
- team-level bulk guardrails with explainable blocking reasons
- productivity trend windows (1d / 7d / 14d) and daily team trend buckets

## Backend

### New schemas
- `backend/app/schemas/render_console_explainability.py`
- extended `backend/app/schemas/render_incident_work_surface.py`
- extended `backend/app/schemas/render_productivity.py`

### New service
- `backend/app/services/render_console_explainability.py`

### New routes
- `GET /api/v1/render/dashboard/incidents/views/{view_id}/effective-access?actor=...`
- `POST /api/v1/render/dashboard/incidents/bulk/{action_type}/guardrails`
- `GET /api/v1/render/dashboard/incidents/productivity/trends?actor=...&windows=1,7,14`

### Guardrail behavior
Bulk preview now includes a `guardrails` block.
Bulk apply now enforces the same guardrails and returns 403 if blocked.

Current default policy by role:
- operator: max 25 items, max 5 high-severity items
- team_lead: max 100 items, max 20 high-severity items
- admin: max 200 items, max 100 high-severity items

Operator bulk mutation is also blocked when the selected incidents are already assigned to other assignees.

## Frontend

### Updated
- `frontend/src/lib/api.ts`
- `frontend/src/app/render-jobs/page.tsx`

### UI additions
- saved view effective-access preview card
- bulk dry-run guardrails card
- productivity trend windows card

## Verification
- `python -m compileall backend/app` ✅
- `cd backend && pytest -q` ✅

## Honest limitations
- no frontend production build confirmation inside this sandbox
- guardrails are computed on read/apply, not materialized yet
- effective-access preview uses currently visible access profiles within scope, not a global directory service
