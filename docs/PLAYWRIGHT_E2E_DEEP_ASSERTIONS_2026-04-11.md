# PLAYWRIGHT E2E DEEP ASSERTIONS PATCH (2026-04-11)

## Added
- stronger create-job payload for backend contract (`script_text`, `provider_target_duration_sec`)
- create response handling accepts `id` and normalizes to `job_id`
- success-path assertions for:
  - final video URL presence
  - final timeline presence
  - storage download endpoint when available
  - direct asset fetch when the final URL is backend `/storage/...`
- incident dashboard assertions via a second failure-path Playwright test
- stable frontend selectors:
  - `data-testid=render-job-final-video`
  - `data-testid=render-job-final-video-url`
  - `data-testid=render-job-final-timeline`
  - `data-testid=render-job-subtitle-summary`
  - `data-testid=incident-card`
  - `data-testid=incident-drawer`

## Backend bug fixed
- `provider_callback_service.ingest_provider_callback()` now resolves scene references before attempting timeline projection and scene state transition.

## Honest limits
- subtitle timeline assertions are summary-level because the current merged frontend job detail page does not render a full subtitle table from the status snapshot.
- MinIO object assertions are conditional because the current merged pipeline may expose the final asset via backend static `/storage/...` before or instead of an object-storage signed URL, depending on the active storage path and worker wiring.
