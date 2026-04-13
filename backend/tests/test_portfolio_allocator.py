from app.services.strategy.portfolio_allocator import PortfolioAllocator


def test_sla_mode_heavily_weights_enterprise():
    plan = PortfolioAllocator().allocate(
        "sla_protection_mode",
        signals=[],
        governance={"top_priority": "enterprise_sla"},
    )
    assert plan["reserve_capacity_percent"] >= 25
    assert plan["tiers"]["enterprise"]["weight"] > plan["tiers"]["standard"]["weight"]
