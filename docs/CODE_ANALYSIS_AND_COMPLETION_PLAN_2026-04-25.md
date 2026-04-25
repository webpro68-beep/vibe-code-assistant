# Code analysis, bug-fix proposals, and completion plan (2026-04-25)

## 1) Current health snapshot

After running the backend tests, the repo shows **fundamental integration breakages during test collection**, not just single business-logic failures.

### Confirmed breakages

1. **Model import regression in `ProviderWebhookEvent`**
   - Symptom: `NameError: name 'Base' is not defined` during test collection.
   - Root cause: file had model class body but missing all required imports.
   - Status: fixed in this patch.

2. **Wrong SQLAlchemy base import path in governance model module**
   - Symptom: `ModuleNotFoundError: No module named 'app.db.base_class'`.
   - Root cause: module imported `Base` from non-existent `app.db.base_class`.
   - Status: fixed in this patch (`app.db.base`).

3. **Missing runtime override function in dispatch service**
   - Symptom: worker import failed due to missing `get_dispatch_runtime_override` symbol.
   - Root cause: worker expected function from service, service did not expose it.
   - Status: fixed in this patch (added function + default fallback path).

4. **Remaining architecture-level circular import (`render_queue` ↔ `render_tasks` ↔ `render_dispatch_worker`)**
   - Symptom: `ImportError: cannot import name 'enqueue_render_dispatch' from partially initialized module`.
   - Root cause: queue and worker modules import each other at module load time.
   - Status: **not fixed yet**; requires small refactor.

## 2) Completed fixes in this change

- Restored required imports and model declarations for `ProviderWebhookEvent`.
- Corrected governance model base import path.
- Added `get_dispatch_runtime_override()` and provider-override resolution hook in dispatch service.

## 3) Proposed bug-fix plan to stabilize repo

### Phase A — Stop import-time failures (priority: critical)

1. Break circular import in queue/worker flow:
   - Option 1 (recommended): move enqueue calls to a tiny adapter module (no worker imports).
   - Option 2: local/lazy import inside functions to avoid module-level dependency cycle.
2. Add smoke-import test for `app.main` route graph to detect cycle regressions early.

### Phase B — Guarantee contract compatibility between services/workers

1. Define explicit public service API surface (`__all__` or interface tests).
2. Add test verifying worker-required functions exist in service modules.
3. Add lint/static rule (or CI script) for forbidden cross-layer imports.

### Phase C — Improve migration/model consistency

1. Audit all model files for legacy import paths (`base_class`, old package names).
2. Add one CI check to import every model module in a loop.
3. Align Alembic env/model registry initialization to fail fast with clear message.

### Phase D — Reliability hardening

1. Expand collection-stage CI job to run before expensive test matrix.
2. Add architectural boundary docs for `services/`, `workers/`, `queue` responsibilities.
3. Add release checklist item: “import graph check + app startup check”.

## 4) Suggested execution order (1-week sprint)

- Day 1: fix circular import and add guard tests.
- Day 2–3: model/import path audit + CI import sweep.
- Day 4: service/worker API contract tests.
- Day 5: docs + release checklist + retro.

## 5) Success criteria

- `pytest -q backend/tests` reaches execution stage (no collection-time import errors).
- `app.main` imports cleanly in CI.
- Worker dispatch flow can enqueue dispatch/poll without import recursion.
- No `base_class`/missing symbol regressions in subsequent merges.

