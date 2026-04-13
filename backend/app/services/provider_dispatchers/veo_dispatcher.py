from .base import DispatchResult

async def dispatch_veo_video(payload: dict) -> DispatchResult:
    return DispatchResult(accepted=True, provider_operation_name="operations/mock-veo-operation-id", raw_response={"name": "operations/mock-veo-operation-id"})
