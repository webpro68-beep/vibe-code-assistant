from __future__ import annotations

from typing import Literal
from pydantic import BaseModel


ValidationSeverity = Literal["error", "warning"]
ValidationTargetType = Literal["scene", "subtitle", "preview"]


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: ValidationSeverity = "error"
    target_type: ValidationTargetType
    target_index: int | None = None
    field: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue]
	