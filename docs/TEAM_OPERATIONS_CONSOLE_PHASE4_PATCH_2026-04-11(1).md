# TEAM OPERATIONS CONSOLE — PHASE 4 PATCH (2026-04-11)

## Added

### Backend
- Team-scoped access profile listing and update APIs
  - `GET /api/v1/render/dashboard/access-profiles?actor=...&team_only=true|false`
  - `PUT /api/v1/render/dashboard/access-profiles/{target_actor}?actor=...`
- Productivity board API
  - `GET /api/v1/render/dashboard/incidents/productivity?actor=...&days=7`
- Bulk preview audit persistence
  - `POST /api/v1/render/dashboard/incidents/bulk/{action_type}/preview`
  - Preview calls now persist `render_incident_bulk_action_runs` with `mode=preview`
  - Preview items are written to `render_incident_bulk_action_items`

### Frontend
- ACL editor panel for team/admin actors
- Productivity board panel for teams and operators
- Existing bulk audit panel now includes preview-mode runs because backend persists them

## Notes
- ACL editor in this phase edits access profiles used by team-scoped sharing and governance.
- Saved view share scope editing remains in the Saved Views panel.
- Preview audit is persisted in the same audit tables as apply-path runs, distinguished by `mode`.
