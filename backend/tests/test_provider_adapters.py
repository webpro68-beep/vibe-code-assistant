
from app.providers.kling.adapter import KlingAdapter
from app.providers.runway.adapter import RunwayAdapter
from app.providers.veo.adapter import VeoAdapter


def test_runway_callback_normalization():
    adapter = RunwayAdapter()
    event = adapter.normalize_callback(
        headers={},
        payload={
            "type": "task.completed",
            "id": "evt_1",
            "taskId": "task_1",
            "status": "SUCCEEDED",
            "output": ["https://cdn.example.com/video.mp4"],
        },
    )
    assert event.provider == "runway"
    assert event.state == "succeeded"
    assert event.provider_task_id == "task_1"


def test_kling_callback_normalization():
    adapter = KlingAdapter()
    event = adapter.normalize_callback(
        headers={},
        payload={
            "event": "task.callback",
            "request_id": "req_1",
            "data": {
                "task_id": "kt_1",
                "task_status": "succeed",
                "task_result": {"videos": [{"url": "https://cdn.example.com/kling.mp4"}]},
            },
        },
    )
    assert event.provider == "kling"
    assert event.state == "succeeded"
    assert event.provider_task_id == "kt_1"


def test_veo_callback_normalization():
    adapter = VeoAdapter()
    event = adapter.normalize_callback(
        headers={},
        payload={
            "name": "operations/abc",
            "done": True,
            "response": {
                "generateVideoResponse": {
                    "generatedSamples": [{"video": {"uri": "https://cdn.example.com/veo.mp4"}}]
                }
            },
        },
    )
    assert event.provider == "veo"
    assert event.state == "succeeded"
    assert event.provider_operation_name == "operations/abc"
