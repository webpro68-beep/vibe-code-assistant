from app.state import strategy_service


class _Task:
    def delay(self, *args, **kwargs):
        return self(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return strategy_service.get_business_outcomes()


business_outcome_rollup_task = _Task()
