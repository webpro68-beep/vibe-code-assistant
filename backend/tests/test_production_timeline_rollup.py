from datetime import datetime, timedelta, timezone

from app.services.production.status_rollup import rollup_run


def test_rollup_marks_blocked_and_preserves_reason():
    base = datetime(2026, 4, 12, tzinfo=timezone.utc)
    run = {"id": "run-1", "current_stage": "queued", "status": "queued", "percent_complete": 0}
    events = [
        {"phase": "render", "stage": "rendering", "status": "running", "progress_percent": 35, "occurred_at": base, "worker_name": "render_dispatch", "details": {}},
        {"phase": "mix", "stage": "mixing", "status": "blocked", "progress_percent": 72, "occurred_at": base + timedelta(minutes=1), "is_blocking": True, "message": "Missing music asset", "details": {}},
    ]

    rolled = rollup_run(run, events)
    assert rolled["status"] == "blocked"
    assert rolled["blocking_reason"] == "Missing music asset"
    assert rolled["percent_complete"] == 72
    assert rolled["active_worker"] == "render_dispatch"


def test_rollup_marks_ready_when_completed_output_exists():
    base = datetime(2026, 4, 12, tzinfo=timezone.utc)
    run = {"id": "run-2", "current_stage": "queued", "status": "queued", "percent_complete": 0}
    events = [
        {"phase": "mux", "stage": "completed", "status": "succeeded", "progress_percent": 100, "occurred_at": base, "details": {"output_url": "https://cdn.example/final.mp4"}},
    ]

    rolled = rollup_run(run, events)
    assert rolled["status"] == "succeeded"
    assert rolled["percent_complete"] == 100
    assert rolled["output_readiness"] == "ready"
    assert rolled["output_url"] == "https://cdn.example/final.mp4"
