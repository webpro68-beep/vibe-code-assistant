from __future__ import annotations

from pydantic import BaseModel, Field


class OperatorProductivityItem(BaseModel):
    actor: str
    role: str | None = None
    team_id: str | None = None
    active_assigned: int = 0
    acknowledged_count: int = 0
    assigned_count: int = 0
    muted_count: int = 0
    resolved_count: int = 0
    reopened_count: int = 0
    note_updates: int = 0


class TeamProductivityItem(BaseModel):
    team_id: str
    member_count: int = 0
    active_assigned: int = 0
    acknowledged_count: int = 0
    assigned_count: int = 0
    muted_count: int = 0
    resolved_count: int = 0
    reopened_count: int = 0
    note_updates: int = 0


class ProductivityBoardResponse(BaseModel):
    days: int = 7
    operators: list[OperatorProductivityItem] = Field(default_factory=list)
    teams: list[TeamProductivityItem] = Field(default_factory=list)


class ProductivityTrendBucket(BaseModel):
    day: str
    team_id: str
    resolved_count: int = 0
    assigned_count: int = 0
    acknowledged_count: int = 0
    muted_count: int = 0


class ProductivityTrendWindow(BaseModel):
    days: int
    team_totals: list[TeamProductivityItem] = Field(default_factory=list)
    operator_totals: list[OperatorProductivityItem] = Field(default_factory=list)


class ProductivityTrendsResponse(BaseModel):
    windows: list[ProductivityTrendWindow] = Field(default_factory=list)
    daily_team_trends: list[ProductivityTrendBucket] = Field(default_factory=list)
