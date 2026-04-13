#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> tuple[int, Any, str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method.upper())
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8")
            try:
                return response.status, json.loads(body), body
            except json.JSONDecodeError:
                return response.status, {"raw": body}, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed, body


def build_job_payload(provider: str, aspect_ratio: str, prompt_text: str) -> dict[str, Any]:
    return {
        "project_id": f"smoke-{provider}-{int(time.time())}",
        "provider": provider,
        "aspect_ratio": aspect_ratio,
        "subtitle_mode": "soft",
        "planned_scenes": [
            {
                "scene_index": 1,
                "title": "Smoke scene 1",
                "script_text": prompt_text,
                "provider_target_duration_sec": 4 if provider == "veo" else 5,
                "target_duration_sec": 4 if provider == "veo" else 5,
                "visual_prompt": prompt_text,
            }
        ],
    }


def extract_job(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and (payload.get("job_id") or payload.get("id")):
        if payload.get("id") and not payload.get("job_id"):
            payload = dict(payload)
            payload["job_id"] = payload["id"]
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        data = dict(payload["data"])
        if data.get("id") and not data.get("job_id"):
            data["job_id"] = data["id"]
        return data
    raise RuntimeError(f"Unexpected job payload: {payload!r}")


def get_status(backend_base_url: str, job_id: str) -> dict[str, Any]:
    url = f"{backend_base_url.rstrip('/')}/api/v1/render/jobs/{job_id}"
    code, payload, _ = http_json("GET", url)
    if code >= 400:
        raise RuntimeError(f"Status API failed: {code} {payload}")
    return extract_job(payload)


def wait_for_submission(backend_base_url: str, job_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last = None
    while time.time() < deadline:
        last = get_status(backend_base_url, job_id)
        scenes = last.get("scenes") or []
        if scenes:
            scene = scenes[0]
            if scene.get("provider_task_id") or scene.get("provider_operation_name") or (scene.get("status") or "").lower() not in {"queued"}:
                return last
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for provider submission. Last snapshot: {last}")


def wait_for_terminal(backend_base_url: str, job_id: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last = None
    while time.time() < deadline:
        last = get_status(backend_base_url, job_id)
        if (last.get("status") or "").lower() in {"completed", "failed", "canceled"}:
            return last
        scenes = last.get("scenes") or []
        if scenes and (scenes[0].get("status") or "").lower() in {"succeeded", "failed", "canceled"}:
            return last
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for terminal state. Last snapshot: {last}")


def build_direct_signature(secret: str, raw_body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def build_relay_signature(secret: str, raw_body: bytes) -> tuple[str, str]:
    timestamp = str(int(time.time()))
    message = timestamp.encode("utf-8") + b"." + raw_body
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return timestamp, signature


def build_success_callback(provider: str, scene: dict[str, Any], job: dict[str, Any], asset_url: str) -> dict[str, Any]:
    provider_task_id = scene.get("provider_task_id")
    provider_operation_name = scene.get("provider_operation_name")
    job_id = job.get("job_id")

    if provider == "runway":
        return {
            "id": f"evt-{job_id}",
            "taskId": provider_task_id,
            "status": "SUCCEEDED",
            "outputUrl": asset_url,
            "thumbnailUrl": asset_url + ".jpg",
            "event": "task.completed",
        }
    if provider == "kling":
        return {
            "request_id": f"evt-{job_id}",
            "data": {
                "task_id": provider_task_id,
                "task_status": "succeed",
                "task_result": {
                    "videos": [{"url": asset_url, "cover_url": asset_url + ".jpg"}]
                },
            },
            "event": "kling.task.completed",
        }
    return {
        "name": provider_operation_name or f"operations/{job_id}",
        "done": True,
        "response": {
            "generateVideoResponse": {
                "generatedSamples": [
                    {"video": {"uri": asset_url}}
                ]
            }
        },
        "type": "veo.operation.completed",
    }


def verify_frontend(frontend_base_url: str, job_id: str) -> dict[str, Any]:
    url = f"{frontend_base_url.rstrip('/')}/api/render-jobs/{job_id}/snapshot"
    code, payload, _ = http_json("GET", url)
    if code >= 400:
        raise RuntimeError(f"Frontend snapshot route failed: {code} {payload}")
    return extract_job(payload)


def verify_frontend_page(frontend_base_url: str, job_id: str) -> tuple[int, str]:
    req = urllib.request.Request(f"{frontend_base_url.rstrip('/')}/render-jobs/{job_id}", method="GET")
    with urllib.request.urlopen(req, timeout=60) as response:
        html = response.read().decode("utf-8", errors="replace")
        return response.status, html[:1000]


def main() -> int:
    parser = argparse.ArgumentParser(description="Live E2E smoke runner for render provider pipeline")
    parser.add_argument("--backend-base-url", default="http://localhost:8000")
    parser.add_argument("--frontend-base-url", default="http://localhost:3000")
    parser.add_argument("--provider", choices=["runway", "veo", "kling"], required=True)
    parser.add_argument("--delivery-mode", choices=["poll", "direct-callback", "relay-callback", "edge-callback"], default="relay-callback")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--aspect-ratio", default="16:9")
    parser.add_argument("--prompt-text", default="A cinematic smoke test shot of a neon city street in the rain.")
    parser.add_argument("--asset-url", default="https://example.com/final-smoke.mp4")
    parser.add_argument("--callback-secret", default="")
    parser.add_argument("--relay-secret", default="")
    parser.add_argument("--edge-base-url", default="http://localhost:8080")
    args = parser.parse_args()

    create_url = f"{args.backend_base_url.rstrip('/')}/api/v1/render/jobs"
    payload = build_job_payload(args.provider, args.aspect_ratio, args.prompt_text)
    code, create_payload, _ = http_json("POST", create_url, payload)
    if code >= 400:
        raise RuntimeError(f"Create job failed: {code} {create_payload}")

    job = extract_job(create_payload)
    job_id = job.get("job_id") or job.get("id")
    if not job_id:
        raise RuntimeError(f"Create response missing job id: {create_payload}")

    print(json.dumps({"step": "created", "job_id": job_id, "provider": args.provider}, ensure_ascii=False))

    submitted = wait_for_submission(args.backend_base_url, job_id, args.timeout_seconds)
    scene = (submitted.get("scenes") or [None])[0]
    if not scene:
        raise RuntimeError(f"No scenes returned after submission wait: {submitted}")
    print(json.dumps({"step": "submitted", "scene_status": scene.get("status"), "provider_task_id": scene.get("provider_task_id"), "provider_operation_name": scene.get("provider_operation_name")}, ensure_ascii=False))

    if args.delivery_mode != "poll":
        callback_payload = build_success_callback(args.provider, scene, submitted, args.asset_url)
        raw_body = json.dumps(callback_payload).encode("utf-8")
        if args.delivery_mode == "direct-callback":
            if not args.callback_secret:
                raise RuntimeError("--callback-secret is required for direct-callback")
            signature = build_direct_signature(args.callback_secret, raw_body)
            callback_url = f"{args.backend_base_url.rstrip('/')}/api/v1/provider-callbacks/{args.provider}"
            code, callback_result, _ = http_json("POST", callback_url, callback_payload, {"X-Render-Signature": signature})
        elif args.delivery_mode == "relay-callback":
            if not args.relay_secret:
                raise RuntimeError("--relay-secret is required for relay-callback")
            timestamp, signature = build_relay_signature(args.relay_secret, raw_body)
            callback_url = f"{args.backend_base_url.rstrip('/')}/api/v1/provider-callbacks/relay/{args.provider}"
            code, callback_result, _ = http_json("POST", callback_url, callback_payload, {
                "X-Render-Relay-Timestamp": timestamp,
                "X-Render-Relay-Signature": signature,
            })
        else:
            callback_url = f"{args.edge_base_url.rstrip('/')}/hooks/{args.provider}"
            code, callback_result, _ = http_json("POST", callback_url, callback_payload)
        if code >= 400:
            raise RuntimeError(f"Callback injection failed: {code} {callback_result}")
        print(json.dumps({"step": "callback_sent", "delivery_mode": args.delivery_mode, "callback_result": callback_result}, ensure_ascii=False))

    terminal = wait_for_terminal(args.backend_base_url, job_id, args.timeout_seconds)
    scene_terminal = (terminal.get("scenes") or [None])[0]
    print(json.dumps({"step": "terminal", "job_status": terminal.get("status"), "scene_status": scene_terminal.get("status") if scene_terminal else None}, ensure_ascii=False))

    frontend_snapshot = verify_frontend(args.frontend_base_url, job_id)
    print(json.dumps({"step": "frontend_snapshot", "frontend_job_status": frontend_snapshot.get("status")}, ensure_ascii=False))

    page_status, page_excerpt = verify_frontend_page(args.frontend_base_url, job_id)
    print(json.dumps({"step": "frontend_page", "http_status": page_status, "html_excerpt": page_excerpt}, ensure_ascii=False))

    print(json.dumps({
        "ok": True,
        "job_id": job_id,
        "provider": args.provider,
        "backend_status": terminal.get("status"),
        "frontend_status": frontend_snapshot.get("status"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
