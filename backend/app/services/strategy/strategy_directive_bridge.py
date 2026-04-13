from __future__ import annotations


class StrategyDirectiveBridge:
    def build(self, mode: str, objective_profile: dict, governance: dict, portfolio: dict) -> list[dict]:
        directives = [
            {
                "directive_type": "priority_weight_by_tier",
                "scope": "portfolio",
                "priority": 90,
                "payload": {k: v["weight"] for k, v in portfolio["tiers"].items()},
                "rationale": f"Align dispatch priority with {mode} objective stack.",
            },
            {
                "directive_type": "capacity_reservation",
                "scope": "global",
                "priority": 85,
                "payload": {"reserve_capacity_percent": portfolio["reserve_capacity_percent"]},
                "rationale": "Protect critical workloads under current strategic mode.",
            },
            {
                "directive_type": "quality_floor_by_segment",
                "scope": "portfolio",
                "priority": 80,
                "payload": {
                    "enterprise": "strict",
                    "premium": governance["quality_floor"],
                    "standard": "standard",
                    "batch": "standard",
                },
                "rationale": "Translate business strategy into bounded quality guarantees.",
            },
            {
                "directive_type": "experiment_freeze_flag",
                "scope": "global",
                "priority": 70,
                "payload": {"enabled": governance["freeze_experiments"]},
                "rationale": "Reduce risk when launch or SLA pressure is elevated.",
            },
            {
                "directive_type": "cost_ceiling_by_mode",
                "scope": "global",
                "priority": 75,
                "payload": {"allow_cost_expansion": governance["allow_cost_expansion"], "mode": mode},
                "rationale": "Keep runtime trade-offs bounded under enterprise strategy.",
            },
        ]
        if mode == "launch_mode":
            directives.append({
                "directive_type": "deadline_mode",
                "scope": "global",
                "priority": 95,
                "payload": {"enabled": True, "ttl_minutes": 240},
                "rationale": "Launch window requires higher throughput and tighter deadline adherence.",
            })
        if mode == "sla_protection_mode":
            directives.append({
                "directive_type": "sla_protection_mode",
                "scope": "enterprise",
                "priority": 96,
                "payload": {"enabled": True, "escalation_sensitivity": "high"},
                "rationale": "Enterprise SLA and penalty risk require stronger guardrails.",
            })
        return directives
