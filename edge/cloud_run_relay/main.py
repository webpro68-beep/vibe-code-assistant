from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title="provider-callback-relay-edge", version="1.0.0")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


BACKEND_RELAY_BASE_URL = (_env("BACKEND_RELAY_BASE_URL", "http://localhost:8000/api/v1/provider-callbacks/relay") or "").rstrip("/")
DEFAULT_SHARED_SECRET = _env("PROVIDER_RELAY_SHARED_SECRET")
ALLOWED_PROVIDERS = {p.strip().lower() for p in (_env("EDGE_ALLOWED_PROVIDERS", "runway,veo,kling") or "").split(",") if p.strip()}
FORWARD_TIMEOUT_SECONDS = float(_env("EDGE_FORWARD_TIMEOUT_SECONDS", "30") or "30")


def resolve_secret(provider: str) -> str | None:
    provider_key = provider.strip().lower()
    specific = _env(f"{provider_key.upper()}_RELAY_SHARED_SECRET")
    return specific or DEFAULT_SHARED_SECRET


def build_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = timestamp.encode("utf-8") + b"." + raw_body
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "provider-callback-relay-edge",
        "backend_relay_base_url": BACKEND_RELAY_BASE_URL,
        "allowed_providers": sorted(ALLOWED_PROVIDERS),
    }


@app.post("/hooks/{provider}")
async def relay_provider_callback(provider: str, request: Request) -> dict[str, Any]:
    provider_key = provider.strip().lower()
    if provider_key not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unsupported provider: {provider_key}")

    secret = resolve_secret(provider_key)
    if not secret:
        raise HTTPException(status_code=500, detail=f"Missing relay secret for provider: {provider_key}")

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

    timestamp = str(int(time.time()))
    signature = build_signature(secret, timestamp, raw_body)
    forward_url = f"{BACKEND_RELAY_BASE_URL}/{provider_key}"

    forward_headers = {
        "Content-Type": "application/json",
        "X-Render-Relay-Timestamp": timestamp,
        "X-Render-Relay-Signature": signature,
        "X-Edge-Relay-Provider": provider_key,
    }

    source_headers = {k.lower(): v for k, v in request.headers.items()}
    for key in ["x-provider-signature", "x-render-signature", "x-kling-signature", "x-runway-signature"]:
        if key in source_headers:
            forward_headers[f"X-Original-{key.title()}"] = source_headers[key]

    async with httpx.AsyncClient(timeout=FORWARD_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.post(forward_url, headers=forward_headers, content=raw_body)

    response_text = response.text
    try:
        response_payload = response.json()
    except Exception:
        response_payload = {"raw": response_text}

    return {
        "ok": response.is_success,
        "provider": provider_key,
        "forward_url": forward_url,
        "backend_status_code": response.status_code,
        "backend_response": response_payload,
        "payload_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
    }
