from __future__ import annotations


class PortfolioAllocator:
    def allocate(self, mode: str, signals: list[dict], governance: dict) -> dict:
        reserve = 10
        tiers = {
            "enterprise": {"weight": 35, "lane": "protected"},
            "premium": {"weight": 30, "lane": "priority"},
            "standard": {"weight": 25, "lane": "elastic"},
            "batch": {"weight": 10, "lane": "opportunistic"},
        }
        if mode == "launch_mode":
            reserve = 30
            tiers["premium"]["weight"] = 35
            tiers["standard"]["weight"] = 20
            tiers["batch"]["weight"] = 5
        elif mode == "margin_mode":
            reserve = 12
            tiers["batch"]["weight"] = 15
            tiers["premium"]["weight"] = 25
        elif mode == "sla_protection_mode":
            reserve = 25
            tiers["enterprise"]["weight"] = 45
            tiers["batch"]["weight"] = 5
        elif mode == "quality_first_mode":
            reserve = 18
            tiers["enterprise"]["lane"] = "quality_protected"
            tiers["premium"]["lane"] = "quality_priority"
        if governance.get("top_priority") == "launch_deadline":
            reserve = max(reserve, 30)
        return {
            "mode": mode,
            "reserve_capacity_percent": reserve,
            "tiers": tiers,
        }
