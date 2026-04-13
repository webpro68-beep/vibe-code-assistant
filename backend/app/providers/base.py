from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.provider_common import (
    NormalizedCallbackEvent,
    NormalizedStatusResult,
    NormalizedSubmitResult,
)


class BaseVideoProviderAdapter(ABC):
    """
    Interface chuẩn cho mọi video provider adapter.

    Mục tiêu:
    - ép toàn bộ Veo / Runway / Kling trả về cùng một normalized contract
    - giữ provider_router.py, dispatch/poll services, callback route
      không phụ thuộc vào provider-specific response shapes
    """

    provider_name: str

    @abstractmethod
    async def submit(
        self,
        scene_payload: dict,
        callback_url: str | None,
    ) -> NormalizedSubmitResult:
        """
        Submit một scene sang provider.

        Input:
        - scene_payload: payload đã được dispatch service normalize
        - callback_url: URL webhook/callback backend muốn provider gọi về

        Output:
        - NormalizedSubmitResult
        """
        raise NotImplementedError

    @abstractmethod
    async def query(
        self,
        *,
        provider_task_id: str | None,
        provider_operation_name: str | None,
    ) -> NormalizedStatusResult:
        """
        Query/poll trạng thái scene từ provider.

        Quy ước:
        - Veo thường dùng provider_operation_name
        - Runway / Kling thường dùng provider_task_id

        Output:
        - NormalizedStatusResult
        """
        raise NotImplementedError

    @abstractmethod
    def verify_callback(
        self,
        headers: dict[str, str],
        raw_body: bytes,
    ) -> bool:
        """
        Verify callback signature / authenticity.

        Return:
        - True nếu callback hợp lệ
        - False nếu callback không hợp lệ
        """
        raise NotImplementedError

    @abstractmethod
    def normalize_callback(
        self,
        headers: dict[str, str],
        payload: dict,
    ) -> NormalizedCallbackEvent:
        """
        Chuẩn hóa callback payload từ provider về contract thống nhất.

        Output:
        - NormalizedCallbackEvent
        """
        raise NotImplementedError