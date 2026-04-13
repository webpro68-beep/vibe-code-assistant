from __future__ import annotations

from datetime import datetime

PHASE_ORDER = ["ingest", "render", "narration", "music", "mix", "mux", "publish", "operator"]
READINESS_BY_STAGE = {
    "queued": "not_ready",
    "rendering": "not_ready",
    "narration": "not_ready",
    "mixing": "not_ready",
    "muxing": "not_ready",
    "publishing": "not_ready",
    "finalizing": "almost_ready",
    "completed": "ready",
    "published": "ready",
}


def phase_rank(phase: str) -> int:
    try:
        return PHASE_ORDER.index(phase)
    except ValueError:
        return len(PHASE_ORDER)


def rollup_run(run: dict, events: list[dict]) -> dict:
    events_sorted = sorted(events, key=lambda e: (e["occurred_at"], phase_rank(e["phase"])))
    current_stage = run.get("current_stage", "queued")
    status = run.get("status", "queued")
    percent_complete = int(run.get("percent_complete") or 0)
    blocking_reason = run.get("blocking_reason")
    active_worker = run.get("active_worker")
    output_url = run.get("output_url")
    last_event_at = run.get("last_event_at")
    started_at = run.get("started_at")
    completed_at = run.get("completed_at")

    for e in events_sorted:
        current_stage = e.get("stage") or current_stage
        if e.get("status") == "failed":
            status = "failed"
        elif e.get("status") == "blocked":
            status = "blocked"
        elif e.get("status") == "needs_review":
            status = "needs_review"
        elif e.get("status") == "running" and status not in {"failed", "blocked", "needs_review"}:
            status = "running"
        elif e.get("status") == "queued" and status == "queued":
            status = "queued"
        elif e.get("status") in {"succeeded", "retried"} and status not in {"failed", "blocked", "needs_review"}:
            status = "running"

        if e.get("progress_percent") is not None:
            percent_complete = max(percent_complete, int(e["progress_percent"]))
        if e.get("is_blocking"):
            blocking_reason = e.get("message") or e.get("title")
        if e.get("worker_name"):
            active_worker = e["worker_name"]
        if e.get("occurred_at"):
            last_event_at = e["occurred_at"]
            if started_at is None:
                started_at = e["occurred_at"]
        details = e.get("details") or {}
        if details.get("output_url"):
            output_url = details["output_url"]
        if e.get("status") == "succeeded" and e.get("stage") in {"completed", "published"}:
            completed_at = e.get("occurred_at")
            percent_complete = 100
            status = "succeeded"
            current_stage = e.get("stage") or current_stage

    output_readiness = READINESS_BY_STAGE.get(current_stage, "not_ready")
    if status == "succeeded" and percent_complete >= 100:
        output_readiness = "ready"
    elif output_url and output_readiness == "not_ready":
        output_readiness = "almost_ready"

    return {
        **run,
        "current_stage": current_stage,
        "status": status,
        "percent_complete": min(100, max(0, percent_complete)),
        "blocking_reason": blocking_reason,
        "active_worker": active_worker,
        "output_readiness": output_readiness,
        "output_url": output_url,
        "last_event_at": last_event_at,
        "started_at": started_at,
        "completed_at": completed_at,
    }
