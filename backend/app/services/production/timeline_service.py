from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.services.production.status_rollup import rollup_run
from app.services.production.timeline_repository import InMemoryTimelineRepository


class ProductionTimelineService:
    def __init__(self, repository: InMemoryTimelineRepository):
        self.repository = repository

    def ensure_run(
        self,
        *,
        production_run_id: str | None,
        render_job_id: str | None,
        project_id: str | None,
        trace_id: str | None,
        title: str | None = None,
    ) -> dict:
        run_id = production_run_id or render_job_id or str(uuid.uuid4())
        existing = self.repository.get_run(run_id)
        run = {
            "id": run_id,
            "render_job_id": render_job_id,
            "project_id": project_id,
            "trace_id": trace_id,
            "title": title,
            "current_stage": existing.get("current_stage", "queued") if existing else "queued",
            "status": existing.get("status", "queued") if existing else "queued",
            "percent_complete": existing.get("percent_complete", 0) if existing else 0,
            "blocking_reason": existing.get("blocking_reason") if existing else None,
            "active_worker": existing.get("active_worker") if existing else None,
            "output_readiness": existing.get("output_readiness", "not_ready") if existing else "not_ready",
            "output_url": existing.get("output_url") if existing else None,
            "last_event_at": existing.get("last_event_at") if existing else None,
            "started_at": existing.get("started_at") if existing else None,
            "completed_at": existing.get("completed_at") if existing else None,
        }
        return self.repository.upsert_run(run)

    def write_event(self, payload: dict) -> dict:
        run = self.ensure_run(
            production_run_id=payload.get("production_run_id"),
            render_job_id=payload.get("render_job_id"),
            project_id=payload.get("project_id"),
            trace_id=payload.get("trace_id"),
            title=payload.get("title"),
        )
        event = {
            "id": str(uuid.uuid4()),
            "production_run_id": run["id"],
            "project_id": payload.get("project_id"),
            "render_job_id": payload.get("render_job_id"),
            "trace_id": payload.get("trace_id"),
            "title": payload["title"],
            "message": payload.get("message"),
            "phase": payload["phase"],
            "stage": payload["stage"],
            "event_type": payload["event_type"],
            "status": payload["status"],
            "worker_name": payload.get("worker_name"),
            "provider": payload.get("provider"),
            "progress_percent": payload.get("progress_percent"),
            "is_blocking": bool(payload.get("is_blocking")),
            "is_operator_action": bool(payload.get("is_operator_action")),
            "occurred_at": payload.get("occurred_at") or datetime.now(timezone.utc),
            "details": payload.get("details") or None,
            "details_json": json.dumps(payload.get("details") or {}),
        }
        self.repository.add_event(event)
        rolled = rollup_run(run, self.repository.list_events_for_run(run["id"]))
        self.repository.upsert_run(rolled)
        return event

    def get_run_detail(self, run_id: str) -> dict | None:
        run = self.repository.get_run(run_id)
        if not run:
            return None
        events = sorted(self.repository.list_events_for_run(run_id), key=lambda e: e["occurred_at"])
        rolled = rollup_run(run, events)
        self.repository.upsert_run(rolled)
        return {"run": rolled, "timeline": events}

    def get_run_by_render_job(self, render_job_id: str) -> dict | None:
        for run in self.repository.list_runs():
            if run.get("render_job_id") == render_job_id:
                return self.get_run_detail(run["id"])
        return None

    def list_dashboard_runs(self) -> list[dict]:
        items = []
        for run in self.repository.list_runs():
            detail = self.get_run_detail(run["id"])
            if detail:
                items.append(detail["run"])
        items.sort(key=lambda x: x.get("last_event_at") or datetime.fromtimestamp(0, tz=timezone.utc), reverse=True)
        return items
