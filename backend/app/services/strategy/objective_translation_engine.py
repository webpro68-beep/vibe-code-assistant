from __future__ import annotations


MODE_STACKS = {
    "balanced": ["safety", "sla", "quality", "margin", "throughput"],
    "launch_mode": ["safety", "launch_deadline", "sla", "throughput", "quality", "margin"],
    "margin_mode": ["safety", "margin", "sla", "quality_floor", "throughput"],
    "sla_protection_mode": ["safety", "enterprise_sla", "premium_sla", "quality", "margin", "throughput"],
    "quality_first_mode": ["safety", "quality", "sla", "margin", "throughput"],
}


class ObjectiveTranslationEngine:
    def translate(self, mode: str, signals: list[dict]) -> dict:
        stack = MODE_STACKS.get(mode, MODE_STACKS["balanced"])
        rationale = []
        for signal in signals:
            if not signal.get("is_active", True):
                continue
            if signal["signal_type"] == "launch_calendar":
                rationale.append(f"Launch signal active: {signal['title']}")
            elif signal["signal_type"] == "sla_commitment":
                rationale.append(f"SLA protection input: {signal['title']}")
            elif signal["signal_type"] == "campaign":
                rationale.append(f"Campaign pressure: {signal['title']}")
            elif signal["signal_type"] == "revenue_target":
                rationale.append(f"Revenue target pressure: {signal['title']}")
            elif signal["signal_type"] == "roadmap_priority":
                rationale.append(f"Roadmap emphasis: {signal['title']}")
        if not rationale:
            rationale.append("No active strategic pressure detected; using balanced baseline.")
        return {
            "mode": mode,
            "name": mode.replace("_", " ").title(),
            "objective_stack": stack,
            "rationale": rationale,
        }
