from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.strategy.business_feedback_service import BusinessFeedbackService
from app.services.strategy.objective_translation_engine import ObjectiveTranslationEngine
from app.services.strategy.portfolio_allocator import PortfolioAllocator
from app.services.strategy.repository import InMemoryStrategyRepository
from app.services.strategy.strategy_directive_bridge import StrategyDirectiveBridge
from app.services.strategy.strategy_ingestion_service import StrategyIngestionService
from app.services.strategy.tradeoff_governance_engine import TradeoffGovernanceEngine


class EnterpriseStrategyService:
    def __init__(self, repository: InMemoryStrategyRepository):
        self.repository = repository
        self.ingestion = StrategyIngestionService()
        self.translation = ObjectiveTranslationEngine()
        self.governance = TradeoffGovernanceEngine()
        self.allocator = PortfolioAllocator()
        self.directive_bridge = StrategyDirectiveBridge()
        self.feedback = BusinessFeedbackService()
        if not self.repository.modes:
            self.activate_mode("balanced", ttl_minutes=1440, note="default")

    def activate_mode(self, mode: str, ttl_minutes: int = 240, note: str | None = None) -> dict:
        now = datetime.now(timezone.utc)
        record = {
            "mode": mode,
            "ttl_minutes": ttl_minutes,
            "note": note,
            "started_at": now,
            "ends_at": now + timedelta(minutes=ttl_minutes),
            "is_active": True,
        }
        self.repository.modes = [m for m in self.repository.modes if m.get("mode") != mode]
        self.repository.modes.append(record)
        self._rebuild_state()
        return record

    def ingest_signal(self, payload: dict) -> dict:
        signal = self.ingestion.ingest_signal(payload)
        self.repository.signals.append(signal)
        self._rebuild_state()
        return signal

    def _current_mode(self) -> str:
        now = datetime.now(timezone.utc)
        active = [m for m in self.repository.modes if m["is_active"] and (m.get("ends_at") is None or m["ends_at"] > now)]
        if not active:
            return "balanced"
        active.sort(key=lambda m: m["started_at"], reverse=True)
        return active[0]["mode"]

    def _rebuild_state(self) -> None:
        mode = self._current_mode()
        signals = [s for s in self.repository.signals if s.get("is_active", True)]
        profile = self.translation.translate(mode, signals)
        governance = self.governance.resolve(profile)
        portfolio = self.allocator.allocate(mode, signals, governance)
        directives = self.directive_bridge.build(mode, profile, governance, portfolio)
        outcome = self.feedback.snapshot(mode, directives)
        self.repository.objective_profile = profile
        self.repository.portfolio = portfolio
        self.repository.directives = directives
        self.repository.business_outcomes = [outcome]

    def get_state(self) -> dict:
        self._rebuild_state()
        return {
            "current_mode": self._current_mode(),
            "active_modes": self.repository.modes,
            "signals": self.repository.signals,
            "objective_profile": self.repository.objective_profile,
            "directives": self.repository.directives,
            "portfolio": self.repository.portfolio,
            "business_outcomes": self.repository.business_outcomes,
            "generated_at": datetime.now(timezone.utc),
        }

    def get_objectives(self) -> dict:
        self._rebuild_state()
        return self.repository.objective_profile

    def get_directives(self) -> list[dict]:
        self._rebuild_state()
        return self.repository.directives

    def get_portfolio(self) -> dict:
        self._rebuild_state()
        return self.repository.portfolio

    def get_business_outcomes(self) -> list[dict]:
        self._rebuild_state()
        return self.repository.business_outcomes

    def get_sla_risk(self) -> dict:
        self._rebuild_state()
        mode = self._current_mode()
        base_risk = 0.18
        if mode == "sla_protection_mode":
            base_risk = 0.08
        elif mode == "launch_mode":
            base_risk = 0.12
        return {
            "mode": mode,
            "tiers": {
                "enterprise": {"risk_score": round(base_risk, 2), "status": "watched" if base_risk > 0.1 else "protected"},
                "premium": {"risk_score": round(base_risk + 0.06, 2), "status": "watched"},
                "standard": {"risk_score": round(base_risk + 0.14, 2), "status": "elastic"},
                "batch": {"risk_score": round(base_risk + 0.22, 2), "status": "opportunistic"},
            },
        }
