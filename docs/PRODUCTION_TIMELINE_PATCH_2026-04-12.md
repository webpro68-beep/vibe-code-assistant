# Production Timeline Patch — 2026-04-12

This patch unifies render and audio pipeline state into a single operator-facing timeline.

## Added domains
- `ProductionRun`
- `ProductionTimelineEvent`
- `RenderJobSummary`

## Added backend surfaces
- `GET /api/v1/render-jobs/{id}/timeline`
- `GET /api/v1/render-jobs/{id}/status-detail`
- `GET /api/v1/dashboard/production-runs`
- `POST /api/v1/production/events`

## Timeline phases
- ingest
- render
- narration
- music
- mix
- mux
- publish
- operator

## Rollup behavior
- failed beats running
- blocked beats running
- completed + output_url => ready
- progress is the max observed progress

## Frontend pages
- `/dashboard`
- `/render-jobs/[id]`

## Worker integration pattern
Each worker can emit normalized events through the timeline service.
Example payload:

```json
{
  "render_job_id": "render-123",
  "phase": "mix",
  "stage": "mixing",
  "event_type": "mix_started",
  "status": "running",
  "title": "Audio mix started",
  "worker_name": "audio_mix_worker",
  "progress_percent": 68
}
```
