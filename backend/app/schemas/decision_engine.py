from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


DecisionSeverity = Literal["low", "medium", "high", "critical"]
DecisionType = Literal[
    "scale_worker",
    "switch_provider",
    "block_release",
    "rebalance_queue",
    "ack_incident",
    "assign_incident",
    "resolve_incident",
]


class DecisionContextSnapshot(BaseModel):
    queued_jobs: int = 0
    processing_jobs: int = 0
    failed_scenes_last_24h_by_provider: dict[str, int] = Field(default_factory=dict)
    open_incidents_by_provider: dict[str, int] = Field(default_factory=dict)
    critical_open_incidents: int = 0
    open_incidents_by_assignee: dict[str, int] = Field(default_factory=dict)


class DecisionRecommendation(BaseModel):
    decision_key: str
    decision_type: DecisionType
    severity: DecisionSeverity
    title: str
    rationale: str
    owner: str
    action_payload: dict[str, Any] = Field(default_factory=dict)
    planned_only: bool = False


class DecisionEvaluationResponse(BaseModel):
    engine_name: str
    policy_version: str
    evaluated_at: datetime
    snapshot: DecisionContextSnapshot
    recommendations: list[DecisionRecommendation] = Field(default_factory=list)


class DecisionExecuteRequest(BaseModel):
    actor: str
    decision_type: DecisionType
    action_payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    dry_run: bool = False
    recommendation_key: str | None = None
    policy_version: str | None = None


class DecisionExecutionResult(BaseModel):
    decision_type: DecisionType
    status: Literal["executed", "planned_only", "dry_run", "rejected"]
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
