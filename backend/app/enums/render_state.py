from enum import Enum


class RenderState(str, Enum):
    QUEUED = "queued"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"