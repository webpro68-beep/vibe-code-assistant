from .base import DispatchResult

async def dispatch_runway_video(payload: dict) -> DispatchResult:
    return DispatchResult(accepted=True, provider_task_id="runway-task-mock-id", raw_response={"id": "runway-task-mock-id", "status": "PENDING"})
