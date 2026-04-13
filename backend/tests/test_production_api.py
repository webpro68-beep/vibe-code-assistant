from fastapi.testclient import TestClient

from app.main import app
from app.state import timeline_repository


client = TestClient(app)


def setup_function():
    timeline_repository.runs.clear()
    timeline_repository.events.clear()


def test_dashboard_and_timeline_endpoints():
    event = {
        "render_job_id": "render-api-1",
        "title": "Mux finished",
        "phase": "mux",
        "stage": "completed",
        "event_type": "mux_finished",
        "status": "succeeded",
        "progress_percent": 100,
        "details": {"output_url": "https://cdn.example/render-api-1.mp4"},
    }
    create_res = client.post("/api/v1/production/events", json=event)
    assert create_res.status_code == 200

    dashboard_res = client.get("/api/v1/dashboard/production-runs")
    assert dashboard_res.status_code == 200
    dashboard = dashboard_res.json()
    assert dashboard["items"][0]["status"] == "succeeded"

    timeline_res = client.get("/api/v1/render-jobs/render-api-1/timeline")
    assert timeline_res.status_code == 200
    detail = timeline_res.json()
    assert detail["run"]["output_readiness"] == "ready"
    assert detail["timeline"][0]["event_type"] == "mux_finished"
