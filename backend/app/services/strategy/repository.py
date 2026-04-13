from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryStrategyRepository:
    signals: list[dict[str, Any]] = field(default_factory=list)
    modes: list[dict[str, Any]] = field(default_factory=list)
    objective_profile: dict[str, Any] | None = None
    directives: list[dict[str, Any]] = field(default_factory=list)
    portfolio: dict[str, Any] | None = None
    business_outcomes: list[dict[str, Any]] = field(default_factory=list)
