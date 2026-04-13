from __future__ import annotations

import os
from typing import Any, Protocol


class ProviderClientProtocol(Protocol):
    async def dispatch_scene(self, *, job: Any, scene_task: Any) -> dict[str, Any]:
        ...

    async def poll_scene(
        self,
        *,
        provider_task_id: str | None,
        provider_operation_name: str | None,
        scene_task: Any,
        job: Any,
    ) -> dict[str, Any]:
        ...


class MockProviderClient:
    """
    Mock production-safe client để pipeline chạy kín local/dev.
    Có thể thay bằng Veo / Runway / Kling thật sau.
    """

    async def dispatch_scene(self, *, job: Any, scene_task: Any) -> dict[str, Any]:
        return {
            "status": "submitted",
            "provider_task_id": f"mock-task-{scene_task.id}",
            "provider_operation_name": f"mock-op-{scene_task.id}",
            "provider_payload": {
                "provider": getattr(job, "provider", "mock"),
                "scene_index": getattr(scene_task, "scene_index", None),
            },
        }

    async def poll_scene(
        self,
        *,
        provider_task_id: str | None,
        provider_operation_name: str | None,
        scene_task: Any,
        job: Any,
    ) -> dict[str, Any]:
        output_path = getattr(scene_task, "mock_output_path", None) or getattr(scene_task, "output_path", None)

        return {
            "status": "succeeded",
            "provider_task_id": provider_task_id,
            "provider_operation_name": provider_operation_name,
            "output_url": None,
            "output_path": output_path,
            "provider_payload": {
                "provider": getattr(job, "provider", "mock"),
                "provider_task_id": provider_task_id,
                "provider_operation_name": provider_operation_name,
            },
            "error_message": None,
        }


def get_provider_client(provider_name: str) -> ProviderClientProtocol:
    normalized = str(provider_name or "").strip().lower()

    # Tạm thời route hết về mock cho local/dev.
    # Sau này thay bằng:
    # if normalized in {"veo", "veo_3", "veo_3_1"}: return VeoProviderClient(...)
    # if normalized == "runway": return RunwayProviderClient(...)
    # if normalized == "kling": return KlingProviderClient(...)
    return MockProviderClient()