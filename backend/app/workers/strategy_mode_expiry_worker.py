from datetime import datetime, timezone

from app.state import strategy_service


class _Task:
    def delay(self, *args, **kwargs):
        return self(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        now = datetime.now(timezone.utc)
        for mode in strategy_service.repository.modes:
            if mode.get("ends_at") and mode["ends_at"] <= now:
                mode["is_active"] = False
        return strategy_service.get_state()


strategy_mode_expiry_task = _Task()
