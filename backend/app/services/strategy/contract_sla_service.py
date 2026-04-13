from __future__ import annotations

from typing import Iterable, List

from app.models import ContractSlaProfile
from app.state import AppState


class ContractSlaService:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def upsert_many(self, profiles: Iterable[ContractSlaProfile]) -> List[ContractSlaProfile]:
        saved = []
        for profile in profiles:
            self.state.contract_slas[profile.id] = profile
            saved.append(profile)
        return saved

    def risk_snapshot(self) -> dict:
        risk_by_tier = {}
        for profile in self.state.contract_slas.values():
            risk_by_tier[profile.customer_tier] = {
                "breach_penalty_weight": profile.breach_penalty_weight,
                "protected_capacity_percent": profile.protected_capacity_percent,
                "escalation_sensitivity": profile.escalation_sensitivity,
            }
        return {"tiers": risk_by_tier, "count": len(risk_by_tier)}
