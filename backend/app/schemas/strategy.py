from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StrategySignalWrite(BaseModel):
    signal_type: Literal["revenue_target", "customer_tier", "launch_calendar", "sla_commitment", "campaign", "roadmap_priority"]
    title: str
    description: str | None = None
    project_id: str | None = None
    customer_tier: Literal["enterprise", "premium", "standard", "batch"] | None = None
    priority: int = Field(default=50, ge=0, le=100)
    weight: int = Field(default=50, ge=0, le=100)
    is_active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class StrategyModeWrite(BaseModel):
    mode: Literal["balanced", "launch_mode", "margin_mode", "sla_protection_mode", "quality_first_mode"]
    ttl_minutes: int = Field(default=240, ge=15, le=10080)
    note: str | None = None


class StrategySignalRead(StrategySignalWrite):
    id: str


class ObjectiveProfileRead(BaseModel):
    mode: str
    name: str
    objective_stack: list[str]
    rationale: list[str]
    ttl_minutes: int | None = None


class StrategyDirectiveRead(BaseModel):
    directive_type: str
    scope: str
    priority: int
    payload: dict
    rationale: str | None = None


class PortfolioAllocationRead(BaseModel):
    mode: str
    reserve_capacity_percent: int
    tiers: dict


class BusinessOutcomeRead(BaseModel):
    mode: str
    revenue_index: int
    sla_attainment_bps: int
    throughput_index: int
    margin_index: int
    captured_at: datetime


class StrategyStateRead(BaseModel):
    current_mode: str
    active_modes: list[dict]
    signals: list[StrategySignalRead]
    objective_profile: ObjectiveProfileRead
    directives: list[StrategyDirectiveRead]
    portfolio: PortfolioAllocationRead
    business_outcomes: list[BusinessOutcomeRead]
    generated_at: datetime
