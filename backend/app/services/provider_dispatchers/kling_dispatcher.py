from .base import DispatchResult

async def dispatch_kling_video(payload: dict) -> DispatchResult:
    return DispatchResult(accepted=True, provider_task_id="kling-task-mock-id", raw_response={"task_id": "kling-task-mock-id", "status": "submitted"})
