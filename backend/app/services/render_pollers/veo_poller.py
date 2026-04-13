from .types import PollResult

async def poll_veo_operation(operation_name: str) -> PollResult:
    return PollResult(state="succeeded", output_video_url="https://example.com/veo-output.mp4", raw_response={"name": operation_name, "done": True})
