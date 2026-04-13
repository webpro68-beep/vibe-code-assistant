from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import DecisionExecutionAuditLog
from app.services.autopilot_control_fabric import run_autopilot_cycle
from app.services.kill_switch import set_global_kill_switch


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_autopilot_stops_when_kill_switch_enabled():
    db = _session()
    set_global_kill_switch(db, actor="ops", enabled=True, reason="Emergency")
    result = run_autopilot_cycle(db)
    assert result["recommendation_count"] == 0
    assert result["suppressed"]
    audit = db.query(DecisionExecutionAuditLog).filter_by(decision_type="autopilot_kill_switch_skip").first()
    assert audit is not None
