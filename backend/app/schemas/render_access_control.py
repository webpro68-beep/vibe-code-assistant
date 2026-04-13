from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class RenderAccessProfileResponse(BaseModel):
    actor_id: str
    role: str
    team_id: str | None = None
    is_active: bool = True
    scopes: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime



class RenderAccessProfileUpdateRequest(BaseModel):
    role: str | None = None
    team_id: str | None = None
    is_active: bool | None = None
    scopes: dict = Field(default_factory=dict)


class RenderAccessProfileListResponse(BaseModel):
    items: list[RenderAccessProfileResponse] = Field(default_factory=list)
