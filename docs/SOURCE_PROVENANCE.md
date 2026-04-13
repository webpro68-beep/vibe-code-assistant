# Source provenance

## Repo-level sources used
- `render_factory_repo.zip`: primary backend, migrations, render worker chain, script preview UI components.
- `template_engine_bundle(2).zip`: Next.js frontend scaffold, Dockerfile, env example, upload/script utility patterns.
- `full_render_pipeline_and_bandit_bundle.zip`: realtime progress widget pattern.
- Current conversation/file library snippets: render execution chain, script upload preview-first flow, local dev goals.

## Direct fixes applied by merge
- fixed syntax errors in `backend/app/core/config.py` and `backend/app/models/render_job.py`
- fixed FastAPI app construction order in `backend/app/main.py`
- added missing `script_preview` schema and preview validation service
- added missing API routes for script upload preview and preview regeneration
- added frontend app shell files and root repo `docker-compose.yml`

## Known gaps not fabricated
- Provider SDK calls remain partially mocked where the source bundles only contained scaffold adapters.
- Auth / RBAC / audit features exist in other uploaded bundles but were not merged into the runtime path here because they were not part of the focused render-factory codepath.
- Some advanced resilience/policy-control-plane bundles were intentionally left out of the runtime repo to avoid inventing integration behavior not present in the render-focused code.
