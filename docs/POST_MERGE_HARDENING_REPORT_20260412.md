# POST-MERGE HARDENING REPORT — 2026-04-12

## Hardening actions performed
- scanned router imports/includes
- scanned model class names for duplicates
- checked Alembic revision graph and final head
- created live-code vs spec-only manifest
- normalized migration chain issues found in merged repo

## Router scan
- router imports: **27**
- router includes: **27**
- missing include aliases: **0**
- orphan include aliases: **0**

## Duplicate imports in key files
- No duplicate import lines found in `backend/app/main.py`, `backend/app/models/__init__.py`, or `frontend/src/lib/api.ts`.

## Duplicate model class names
- No duplicate class names detected under `backend/app/models/`.

## Migration graph status
- total migration files: **26**
- root revisions: **20260408_0001**
- final head revisions: **20260412_0024**

### Migration hardening applied
- fixed duplicate revision id collision between template extraction and Veo workspace migrations
- changed Veo workspace migration from revision `20260412_0022` to `20260412_0023`
- fixed broken governance migration reference from nonexistent `20260412_0028` to a valid linear continuation
- changed governance scheduling migration revision to `20260412_0024` with `down_revision = 20260412_0023`

## Live code vs spec-only summary
- total_files: **516**
- executable-support: **42**
- reference-only: **97**
- executable: **377**

## Classification rules
- `backend/app/**`, `backend/alembic/**`, `backend/tests/**`, `frontend/src/**`, `edge/**`, `e2e/**`, `scripts/ci/**`, `scripts/smoke/**` → executable
- `.github/**`, `.env.example`, `docker-compose.yml`, `Makefile`, and other runtime support files → executable-support
- `docs/**` and imported spec trees under `docs/specs/**` → reference-only

## Honest limits
- This pass hardened merge integrity and migration topology; it did not execute the full application stack.
- Some imported spec bundles remain intentionally reference-only until their upstream executable services are fully present.
