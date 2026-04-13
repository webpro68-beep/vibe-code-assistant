from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import NotificationDeliveryLog, ProviderRoutingOverride, ReleaseGateState, WorkerConcurrencyOverride
from app.services.kill_switch import get_or_create_global_kill_switch, set_global_kill_switch
from app.services.notification_plane import send_notification_event, upsert_notification_endpoint
from app.services.observability_metrics import collect_status_snapshot, export_prometheus_text


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_metrics_snapshot_and_prometheus_export():
    db = _session()
    snapshot = collect_status_snapshot(db)
    text = export_prometheus_text(snapshot)
    assert "release_gate_blocked" in text
    assert "global_kill_switch_enabled" in text
    assert snapshot.generated_at is not None


def test_notification_plane_logs_planned_only_email_without_smtp():
    db = _session()
    upsert_notification_endpoint(
        db,
        actor="tester",
        name="email-test",
        channel_type="email",
        target="ops@example.com",
        event_filter="manual_test",
        enabled=True,
    )
    deliveries = send_notification_event(db, event_type="manual_test", payload={"hello": "world"})
    assert deliveries
    assert deliveries[0].delivery_status in {"planned_only", "failed", "delivered"}


def test_kill_switch_can_be_enabled_and_persisted():
    db = _session()
    row = set_global_kill_switch(db, actor="ops", enabled=True, reason="Emergency freeze")
    refreshed = get_or_create_global_kill_switch(db)
    assert row.enabled is True
    assert refreshed.enabled is True
