from dataclasses import dataclass
from typing import Any

@dataclass
class DispatchResult:
    accepted: bool
    provider_task_id: str | None = None
    provider_operation_name: str | None = None
    raw_response: dict[str, Any] | None = None
    error_message: str | None = None
