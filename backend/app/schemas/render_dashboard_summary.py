from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderCountItem(BaseModel):
    provider: str
    total_jobs: int
    healthy_jobs: int
    degraded_jobs: int
    stalled_jobs: int
    failed_jobs: int
    completed_jobs: int


class TransitionWindowSummary(BaseModel):
    window: str
    total_transitions: int
    degraded_transitions: int
    stalled_transitions: int
    recovered_transitions: int
    failed_transitions: int
    completed_transitions: int


class RenderDashboardSummaryResponse(BaseModel):
    total_jobs: int
    healthy_jobs: int
    degraded_jobs: int
    stalled_jobs: int
    failed_jobs: int
    completed_jobs: int
    queued_jobs: int
    total_active_scenes: int
    total_stalled_scenes: int
    total_degraded_scenes: int
    counts_by_provider: list[ProviderCountItem] = Field(default_factory=list)
    recent_transitions: list[TransitionWindowSummary] = Field(default_factory=list)
