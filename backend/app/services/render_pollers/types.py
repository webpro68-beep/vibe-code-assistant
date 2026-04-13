from dataclasses import dataclass
from typing import Any, Literal

PollState = Literal["processing", "succeeded", "failed", "canceled"]

@dataclass
class PollResult:
    state: PollState
    output_video_url: str | None = None
    output_thumbnail_url: str | None = None
    raw_response: dict[str, Any] | None = None
    error_message: str | None = None
