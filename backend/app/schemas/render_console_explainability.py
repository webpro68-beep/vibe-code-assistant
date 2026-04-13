from __future__ import annotations

from pydantic import BaseModel, Field


class SavedViewEffectiveAccessEntry(BaseModel):
    actor_id: str
    role: str | None = None
    team_id: str | None = None
    can_view: bool = False
    reason: str | None = None


class SavedViewEffectiveAccessResponse(BaseModel):
    view_id: str
    view_name: str
    requester_actor: str
    requester_role: str | None = None
    requester_team_id: str | None = None
    share_scope: str
    owner_actor: str
    shared_team_id: str | None = None
    allowed_roles: list[str] = Field(default_factory=list)
    visible_to_count: int = 0
    entries: list[SavedViewEffectiveAccessEntry] = Field(default_factory=list)


class BulkGuardrailEvaluationResponse(BaseModel):
    ok: bool = True
    action_type: str
    actor: str
    actor_role: str | None = None
    actor_team_id: str | None = None
    policy: dict = Field(default_factory=dict)
    observed: dict = Field(default_factory=dict)
    blocked_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
