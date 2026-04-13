from app.state import strategy_service


class _Task:
    def delay(self, *args, **kwargs):
        return self(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return strategy_service.get_state()


strategy_refresh_task = _Task()
