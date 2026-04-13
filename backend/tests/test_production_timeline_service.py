from app.services.production.timeline_repository import InMemoryTimelineRepository
from app.services.production.timeline_service import ProductionTimelineService


def test_service_groups_events_into_run_detail():
    service = ProductionTimelineService(InMemoryTimelineRepository())
    service.write_event({
        "render_job_id": "render-1",
        "title": "Render started",
        "phase": "render",
        "stage": "rendering",
        "event_type": "render_started",
        "status": "running",
        "progress_percent": 10,
    })
    service.write_event({
        "render_job_id": "render-1",
        "title": "Narration done",
        "phase": "narration",
        "stage": "narration_done",
        "event_type": "narration_finished",
        "status": "succeeded",
        "progress_percent": 55,
    })

    detail = service.get_run_by_render_job("render-1")
    assert detail is not None
    assert detail["run"]["render_job_id"] == "render-1"
    assert len(detail["timeline"]) == 2
    assert detail["run"]["percent_complete"] == 55
