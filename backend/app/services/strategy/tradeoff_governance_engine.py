from __future__ import annotations


class TradeoffGovernanceEngine:
    def resolve(self, objective_profile: dict) -> dict:
        stack = objective_profile["objective_stack"]
        allow_cost_expansion = "launch_deadline" in stack or "enterprise_sla" in stack
        freeze_experiments = "launch_deadline" in stack or "enterprise_sla" in stack
        quality_floor = "strict" if "quality" in stack[:3] else "standard"
        return {
            "allow_cost_expansion": allow_cost_expansion,
            "freeze_experiments": freeze_experiments,
            "quality_floor": quality_floor,
            "top_priority": stack[1] if len(stack) > 1 else stack[0],
        }
