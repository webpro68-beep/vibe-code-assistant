from .types import PollResult

async def poll_kling_task(task_id: str) -> PollResult:
    return PollResult(state="succeeded", output_video_url="https://example.com/kling-output.mp4", raw_response={"task_id": task_id, "status": "succeed"})
