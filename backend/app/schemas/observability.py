from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MetricSample(BaseModel):
    name: str
    value: float
    labels: dict[str, str] = Field(default_factory=dict)


class ObservabilityStatusResponse(BaseModel):
    generated_at: datetime
    metrics: list[MetricSample]
    release_gate_blocked: bool
    global_kill_switch_enabled: bool
    active_provider_overrides: int
    notification_failures_last_24h: int
    autopilot_last_execution_at: str | None = None


class KillSwitchUpdateRequest(BaseModel):
    actor: str
    enabled: bool
    reason: str | None = None


class KillSwitchResponse(BaseModel):
    switch_name: str
    enabled: bool
    reason: str | None = None
    updated_by: str | None = None


class NotificationEndpointUpsertRequest(BaseModel):
    actor: str
    name: str
    channel_type: str
    target: str
    event_filter: str = "*"
    enabled: bool = True
    secret: str | None = None


class NotificationEndpointResponse(BaseModel):
    name: str
    channel_type: str
    target: str
    event_filter: str | None = None
    enabled: bool
    updated_by: str | None = None


class NotificationDeliveryLogResponse(BaseModel):
    id: str
    event_type: str
    endpoint_name: str
    channel_type: str
    delivery_status: str
    payload_json: str | None = None
    response_text: str | None = None
    error_message: str | None = None
    created_at: datetime


class AutopilotDashboardResponse(BaseModel):
    generated_at: datetime
    kill_switch_enabled: bool
    release_gate_blocked: bool
    active_provider_overrides: int
    worker_dispatch_batch_limit: int
    worker_poll_countdown_seconds: int
    autopilot_states: dict[str, int]
    latest_decision_audits: list[dict[str, Any]]
    latest_notification_deliveries: list[dict[str, Any]]
