# Continuation Patch — 2026-04-11

Added in this pass:
- append-only `render_timeline_events`
- job health summary + persisted job health snapshot fields
- job/scene events API
- job health API
- dashboard jobs list API
- dashboard summary API
- recent incidents API
- incident acknowledge / assign / mute APIs
- incident read model (`render_incident_states`) + action audit log (`render_incident_actions`)
- timeline writing from dispatch/poll/callback/scene transitions
- scene poll dedupe / heartbeat / stalled detection helpers
- Alembic migrations for the new tables/fields

Validation run in container:
- `python -m compileall app` ✅
- `pytest -q` ✅

Known limits:
- incident projector is integrated for `job_health_*` timeline events only
- no dedicated backfill worker yet for rebuilding `render_incident_states` from historical timeline
- frontend UI wiring for the new dashboard plane is not added in this pass
