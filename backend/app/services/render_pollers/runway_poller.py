from .types import PollResult

async def poll_runway_task(task_id: str) -> PollResult:
    return PollResult(state="succeeded", output_video_url="https://example.com/runway-output.mp4", raw_response={"id": task_id, "status": "SUCCEEDED"})
