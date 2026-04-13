from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field
from uuid import UUID

class TemplateExtractRequest(BaseModel):
    source_project_id: UUID
    auto_publish: bool = False

class TemplateGenerateRequest(BaseModel):
    input_slots: dict[str, Any]
    mode: str = "single"
    auto_render: bool = True
    auto_upload: bool = False

class TemplateBatchGenerateRequest(BaseModel):
    items: list[dict[str, Any]]
    auto_render: bool = True
    auto_upload: bool = False

class TemplatePackCreate(BaseModel):
    template_name: str
    template_type: str = "composite"
    description: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

class TemplateVersionCreate(BaseModel):
    change_notes: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
