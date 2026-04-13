from __future__ import annotations

from app.services.provider_registry import get_provider_adapter


def verify_provider_callback(provider: str, headers: dict[str, str], raw_body: bytes) -> bool:
    adapter = get_provider_adapter(provider)
    return adapter.verify_callback(headers, raw_body)