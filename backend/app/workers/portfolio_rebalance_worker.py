from app.state import strategy_service


class _Task:
    def delay(self, *args, **kwargs):
        return self(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return strategy_service.get_portfolio()


portfolio_rebalance_task = _Task()
