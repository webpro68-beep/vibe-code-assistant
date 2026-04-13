from __future__ import annotations

import hashlib
import hmac
import time

from app.core.config import settings


class ProviderIngressSignatureError(ValueError):
    pass


def _normalize_signature(value: str | None) -> str:
    raw = (value or "").strip()
    if raw.startswith("sha256="):
        raw = raw[len("sha256="):]
    return raw


def build_ingress_signature(*, secret: str, timestamp: str, raw_body: bytes) -> str:
    message = timestamp.encode("utf-8") + b"." + raw_body
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_ingress_signature(
    *,
    secret: str | None,
    timestamp: str | None,
    signature: str | None,
    raw_body: bytes,
    tolerance_seconds: int | None = None,
) -> bool:
    if not secret:
        return False
    if not timestamp or not signature:
        return False
    try:
        timestamp_int = int(str(timestamp).strip())
    except ValueError:
        return False

    now = int(time.time())
    tolerance = tolerance_seconds or settings.provider_ingress_signature_ttl_seconds
    if abs(now - timestamp_int) > max(1, tolerance):
        return False

    expected = build_ingress_signature(
        secret=secret,
        timestamp=str(timestamp_int),
        raw_body=raw_body,
    )
    return hmac.compare_digest(_normalize_signature(signature), _normalize_signature(expected))


def resolve_ingress_secret(provider: str) -> str | None:
    normalized = provider.strip().lower()
    if normalized == "runway":
        return settings.runway_relay_shared_secret or settings.provider_relay_shared_secret
    if normalized == "kling":
        return settings.kling_relay_shared_secret or settings.provider_relay_shared_secret
    if normalized == "veo":
        return settings.veo_relay_shared_secret or settings.provider_relay_shared_secret
    return settings.provider_relay_shared_secret
