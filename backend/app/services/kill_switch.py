from __future__ import annotations

import uuid
from sqlalchemy.orm import Session

from app.models.global_kill_switch import GlobalKillSwitch

DEFAULT_KILL_SWITCH = "global-autopilot"


def get_or_create_global_kill_switch(db: Session, *, switch_name: str = DEFAULT_KILL_SWITCH) -> GlobalKillSwitch:
    row = db.query(GlobalKillSwitch).filter(GlobalKillSwitch.switch_name == switch_name).first()
    if row:
        return row
    row = GlobalKillSwitch(id=str(uuid.uuid4()), switch_name=switch_name, enabled=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def set_global_kill_switch(db: Session, *, actor: str, enabled: bool, reason: str | None, switch_name: str = DEFAULT_KILL_SWITCH) -> GlobalKillSwitch:
    row = get_or_create_global_kill_switch(db, switch_name=switch_name)
    row.enabled = bool(enabled)
    row.reason = reason
    row.updated_by = actor
    db.commit()
    db.refresh(row)
    return row
