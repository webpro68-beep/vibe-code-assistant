from app.services.strategy.tradeoff_governance_engine import TradeoffGovernanceEngine


def test_sla_stack_freezes_experiments_and_allows_cost_expansion():
    governance = TradeoffGovernanceEngine().resolve(
        {"objective_stack": ["safety", "enterprise_sla", "quality", "margin"]}
    )
    assert governance["allow_cost_expansion"] is True
    assert governance["freeze_experiments"] is True
    assert governance["quality_floor"] == "strict"
