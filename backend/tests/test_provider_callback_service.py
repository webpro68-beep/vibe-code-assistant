import pytest

pytest.importorskip("sqlalchemy")

from types import SimpleNamespace

from app.services import provider_callback_service as svc


class DummyAdapter:
    def normalize_callback(self, headers, payload):
        return SimpleNamespace(
            event_type="task.completed",
            event_idempotency_key="evt-1",
            provider_task_id="task-123",
            provider_operation_name=None,
            provider_status_raw="SUCCEEDED",
            state="succeeded",
            output_video_url="https://cdn.example.com/video.mp4",
            output_thumbnail_url="https://cdn.example.com/video.jpg",
            metadata={"source": "test"},
            error_message=None,
            failure_code=None,
            failure_category=None,
            model_dump=lambda: {"provider_task_id": "task-123", "state": "succeeded"},
        )


class QueryStub:
    def __init__(self):
        self._existing = None
    def filter(self, *args, **kwargs):
        return self
    def first(self):
        return self._existing


class DummyDB:
    def __init__(self):
        self.query_stub = QueryStub()
        self.added = []
        self.commit_count = 0
    def query(self, model):
        return self.query_stub
    def add(self, item):
        self.added.append(item)
    def commit(self):
        self.commit_count += 1


def test_ingest_provider_callback_resolves_scene_and_marks_success(monkeypatch):
    db = DummyDB()
    scene = SimpleNamespace(id="scene-1", job_id="job-1", scene_index=1)
    marked = {}
    timeline = {}

    monkeypatch.setattr(svc, "get_provider_adapter", lambda provider: DummyAdapter())
    monkeypatch.setattr(svc, "find_scene_by_provider_refs", lambda db, provider_task_id, provider_operation_name: scene)
    monkeypatch.setattr(svc, "append_timeline_event", lambda *args, **kwargs: timeline.update(kwargs))
    monkeypatch.setattr(svc, "mark_scene_processing_from_provider", lambda *args, **kwargs: marked.update({"state": "processing"}))
    monkeypatch.setattr(svc, "mark_scene_succeeded_from_provider", lambda *args, **kwargs: marked.update({"state": "succeeded", **kwargs}))
    monkeypatch.setattr(svc, "mark_scene_failed_from_provider", lambda *args, **kwargs: marked.update({"state": "failed"}))

    result = svc.ingest_provider_callback(
        db,
        provider="runway",
        headers={},
        raw_body=b'{"id":"evt-1"}',
        payload={"id": "evt-1", "taskId": "task-123"},
        signature_valid=True,
    )

    assert result["duplicate"] is False
    assert marked["state"] == "succeeded"
    assert marked["scene"] is scene
    assert marked["output_video_url"] == "https://cdn.example.com/video.mp4"
    assert timeline["scene_task_id"] == "scene-1"
