from app.services.strategy.strategy_directive_bridge import StrategyDirectiveBridge


def test_launch_mode_emits_deadline_directive():
    directives = StrategyDirectiveBridge().build(
        "launch_mode",
        {"objective_stack": ["safety", "launch_deadline"]},
        {"allow_cost_expansion": True, "freeze_experiments": True, "quality_floor": "strict"},
        {
            "mode": "launch_mode",
            "reserve_capacity_percent": 30,
            "tiers": {
                "enterprise": {"weight": 35, "lane": "protected"},
                "premium": {"weight": 35, "lane": "priority"},
                "standard": {"weight": 20, "lane": "elastic"},
                "batch": {"weight": 5, "lane": "opportunistic"},
            },
        },
    )
    kinds = {d["directive_type"] for d in directives}
    assert "deadline_mode" in kinds
    assert "capacity_reservation" in kinds
