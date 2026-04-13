# RUNBOOK — POST MERGE HARDENING

This runbook is for the consolidated repo created from real phase artifacts.

## 1) Backend sanity checks

```bash
cd backend
python -m compileall app
pytest -q
```

Expected:
- `compileall` completes without syntax errors
- pytest passes the current smoke test suite

## 2) Alembic graph check

This merge adds a no-op merge revision to collapse multiple heads into one.

Key files:
- `backend/alembic/versions/20260410_000001_add_render_job_storage_and_subtitles.py`
- `backend/alembic/versions/20260411_0013_merge_post_merge_heads.py`

What changed:
- fixed placeholder `down_revision`
- merged heads `20260410_000002`, `20260410_0007`, `20260410_0012`

Manual verification:
- ensure only one Alembic head remains
- ensure migrations still apply in order on a clean database

## 3) Frontend API sync check

`frontend/src/lib/api.ts` was verified against the merged dashboard routes and now includes:
- access profile helpers
- bulk audit helpers
- effective-access preview helper
- bulk guardrail helper
- productivity trend helpers
- incident detail helper

Suggested follow-up on a dev machine:

```bash
cd frontend
npm ci
npx tsc --noEmit
npm run build
```

## 4) Local boot suggestion

```bash
docker compose up --build
```

Then verify:
- API docs open
- dashboard loads
- incident list renders
- bulk preview works
- productivity board renders
- effective-access preview renders

## 5) Recommended smoke path

1. create or seed 1 render job
2. open `/render-jobs`
3. open an incident drawer
4. save an incident view
5. run bulk preview on a small selection
6. inspect bulk history
7. inspect productivity board
8. inspect effective-access preview for a saved view

## 6) Honest limitations

This bundle is a source merge artifact first.
Runtime verification for Docker/Next production build should be run on a stable local dev machine or CI runner.
