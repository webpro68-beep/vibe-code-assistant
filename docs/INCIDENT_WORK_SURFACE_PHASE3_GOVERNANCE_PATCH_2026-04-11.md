# Incident Work Surface Phase 3 — Governance Patch (2026-04-11)

This patch extends the dashboard from a single-user operational panel into a team-oriented control surface with three additions:

1. Saved incident view sharing policy
2. RBAC scope surface
3. Bulk result history / audit panel

## Backend

### New models
- `backend/app/models/render_operator_access_profile.py`
- `backend/app/models/render_incident_bulk_action_run.py`
- `backend/app/models/render_incident_bulk_action_item.py`

### Patched models
- `backend/app/models/render_incident_saved_view.py`
  - added `share_scope`
  - added `shared_team_id`
  - added `allowed_roles_json`

### New schemas
- `backend/app/schemas/render_access_control.py`
- `backend/app/schemas/render_bulk_audit.py`

### New services
- `backend/app/services/render_access_control.py`
- `backend/app/services/render_incident_bulk_audit.py`

### Patched services
- `backend/app/services/render_incident_saved_views.py`
  - saved view visibility now considers owner + scope
  - team/role/global sharing requires elevated access

### Migration
- `backend/alembic/versions/20260410_0012_add_rbac_and_bulk_audit.py`

### New routes
- `GET /api/v1/render/dashboard/access-profile?actor=...`
- `GET /api/v1/render/dashboard/incidents/bulk/history?actor=...`
- `GET /api/v1/render/dashboard/incidents/bulk/history/{run_id}?actor=...`

### Patched routes
- bulk action write-path now persists audit rows
- saved view create/update now accept sharing scope fields

## Frontend

### Patched API client
- `frontend/src/lib/api.ts`
  - access profile types + requests
  - bulk audit history/detail types + requests
  - saved view sharing fields

### Patched dashboard page
- `frontend/src/app/render-jobs/page.tsx`
  - access profile panel
  - bulk action history list
  - audit detail panel
  - saved view share scope/team/role edit controls

## Honest limitations

- RBAC in this patch is intentionally lightweight:
  - default profile is inferred when actor has no stored record yet
  - no dedicated admin UI for editing access profiles yet
- bulk audit is persisted for apply-path only, not preview-path
- frontend build was not fully re-run in sandbox because the extracted bundle still has unstable Next/React dependency state from earlier artifacts; backend compile/test was run successfully
