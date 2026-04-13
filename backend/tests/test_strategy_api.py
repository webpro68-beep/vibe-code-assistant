from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_strategy_state_and_signal_ingest_flow():
    created = client.post(
        "/api/v1/strategy/signals",
        json={
            "signal_type": "campaign",
            "title": "Enterprise spring campaign",
            "description": "Boost premium throughput during campaign window",
            "customer_tier": "enterprise",
            "priority": 88,
            "weight": 82,
            "is_active": True,
        },
    )
    assert created.status_code == 200
    state = client.get("/api/v1/strategy/state")
    assert state.status_code == 200
    body = state.json()
    assert any(item["title"] == "Enterprise spring campaign" for item in body["signals"])
    assert body["objective_profile"]["mode"] in {"balanced", "launch_mode", "margin_mode", "sla_protection_mode", "quality_first_mode"}
    assert len(body["directives"]) >= 4
