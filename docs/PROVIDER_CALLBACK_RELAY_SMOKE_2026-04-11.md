# Provider callback relay + signed ingress + live smoke commands

This patch adds a signed relay ingress on top of the direct provider callback ingress.

## New routes

- Direct provider callback ingress: `POST /api/v1/provider-callbacks/{provider}`
- Signed relay ingress: `POST /api/v1/provider-callbacks/relay/{provider}`

Use the relay ingress when:
- the upstream provider does not expose a stable webhook signature you can verify directly
- you terminate callbacks in a public edge worker / cloud function / API gateway first
- you want to sign the payload yourself before forwarding it into this monorepo

## Relay signature contract

Headers required by relay ingress:
- `X-Render-Relay-Timestamp: <unix_epoch_seconds>`
- `X-Render-Relay-Signature: sha256=<hex_digest>`

Digest input:

```text
<timestamp>.<raw_request_body>
```

Algorithm:
- HMAC-SHA256
- shared secret resolution order:
  - runway -> `RUNWAY_RELAY_SHARED_SECRET` then `PROVIDER_RELAY_SHARED_SECRET`
  - kling -> `KLING_RELAY_SHARED_SECRET` then `PROVIDER_RELAY_SHARED_SECRET`
  - veo -> `VEO_RELAY_SHARED_SECRET` then `PROVIDER_RELAY_SHARED_SECRET`

Replay window:
- controlled by `PROVIDER_INGRESS_SIGNATURE_TTL_SECONDS`
- default: 300 seconds

## Why keep polling as the production safety net

Runway documents its tasks as asynchronous and explicitly recommends polling `GET /v1/tasks/{id}` with an interval of 5 seconds or more, plus jitter and exponential backoff. citeturn288582search3turn288582search4

Google's Veo generation docs show a long-running operation flow where the client polls the operation until `done`, then downloads the video. The docs shown here describe polling, not a first-party webhook flow. citeturn690979search0

Kling's public API pages show direct API references, but in this repo the safest assumption remains: treat callback schemas as vendor-account-dependent and keep poll fallback enabled unless your tenant contract confirms signed webhooks. citeturn288582search1

## Environment variables

Add these to `backend/.env.dev`:

```env
PROVIDER_RELAY_SHARED_SECRET=replace-me
RUNWAY_RELAY_SHARED_SECRET=
KLING_RELAY_SHARED_SECRET=
VEO_RELAY_SHARED_SECRET=
PROVIDER_INGRESS_SIGNATURE_TTL_SECONDS=300
```

## Local signing helper

```bash
python scripts/smoke/sign_relay.py "$PROVIDER_RELAY_SHARED_SECRET" ./scripts/smoke/runway_success.json
```

Output:
- line 1 = timestamp
- line 2 = signature

## Sample payloads

### Runway success payload

Save as `scripts/smoke/runway_success.json`

```json
{
  "type": "task.completed",
  "id": "evt_runway_1",
  "taskId": "task_runway_1",
  "status": "SUCCEEDED",
  "output": ["https://cdn.example.com/runway.mp4"],
  "thumbnailUrl": "https://cdn.example.com/runway.jpg"
}
```

### Kling success payload

Save as `scripts/smoke/kling_success.json`

```json
{
  "event": "task.callback",
  "request_id": "req_kling_1",
  "data": {
    "task_id": "task_kling_1",
    "task_status": "succeed",
    "task_result": {
      "videos": [
        {
          "url": "https://cdn.example.com/kling.mp4",
          "cover_url": "https://cdn.example.com/kling.jpg"
        }
      ]
    }
  }
}
```

### Veo success payload

Save as `scripts/smoke/veo_success.json`

```json
{
  "name": "operations/veo-demo-1",
  "done": true,
  "response": {
    "generateVideoResponse": {
      "generatedSamples": [
        {
          "video": {
            "uri": "gs://demo-bucket/veo-demo-1.mp4"
          }
        }
      ]
    }
  }
}
```

## Signed relay smoke commands

### Runway relay smoke

```bash
TS=$(python scripts/smoke/sign_relay.py "$PROVIDER_RELAY_SHARED_SECRET" ./scripts/smoke/runway_success.json | sed -n '1p')
SIG=$(python scripts/smoke/sign_relay.py "$PROVIDER_RELAY_SHARED_SECRET" ./scripts/smoke/runway_success.json "$TS" | sed -n '2p')

curl -X POST "http://localhost:8000/api/v1/provider-callbacks/relay/runway" \
  -H "Content-Type: application/json" \
  -H "X-Render-Relay-Timestamp: $TS" \
  -H "X-Render-Relay-Signature: $SIG" \
  --data-binary @./scripts/smoke/runway_success.json
```

### Kling relay smoke

```bash
TS=$(python scripts/smoke/sign_relay.py "$PROVIDER_RELAY_SHARED_SECRET" ./scripts/smoke/kling_success.json | sed -n '1p')
SIG=$(python scripts/smoke/sign_relay.py "$PROVIDER_RELAY_SHARED_SECRET" ./scripts/smoke/kling_success.json "$TS" | sed -n '2p')

curl -X POST "http://localhost:8000/api/v1/provider-callbacks/relay/kling" \
  -H "Content-Type: application/json" \
  -H "X-Render-Relay-Timestamp: $TS" \
  -H "X-Render-Relay-Signature: $SIG" \
  --data-binary @./scripts/smoke/kling_success.json
```

### Veo relay smoke

```bash
TS=$(python scripts/smoke/sign_relay.py "$PROVIDER_RELAY_SHARED_SECRET" ./scripts/smoke/veo_success.json | sed -n '1p')
SIG=$(python scripts/smoke/sign_relay.py "$PROVIDER_RELAY_SHARED_SECRET" ./scripts/smoke/veo_success.json "$TS" | sed -n '2p')

curl -X POST "http://localhost:8000/api/v1/provider-callbacks/relay/veo" \
  -H "Content-Type: application/json" \
  -H "X-Render-Relay-Timestamp: $TS" \
  -H "X-Render-Relay-Signature: $SIG" \
  --data-binary @./scripts/smoke/veo_success.json
```

## Direct provider smoke notes

### Runway direct submit + poll

Runway's official guide shows `POST /v1/image_to_video` with `Authorization: Bearer ...` and `X-Runway-Version`, then task polling via the task ID. citeturn288582search4turn288582search3

```bash
curl -X POST https://api.dev.runwayml.com/v1/image_to_video \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RUNWAYML_API_SECRET" \
  -H "X-Runway-Version: $RUNWAY_API_VERSION" \
  -d '{
    "model": "gen4.5",
    "promptText": "A cinematic drone shot over a tropical island at sunrise",
    "ratio": "1280:720",
    "duration": 5
  }'
```

Then poll:

```bash
curl -H "Authorization: Bearer $RUNWAYML_API_SECRET" \
  -H "X-Runway-Version: $RUNWAY_API_VERSION" \
  "https://api.dev.runwayml.com/v1/tasks/<RUNWAY_TASK_ID>"
```

### Veo direct submit + poll

Google's Veo docs show long-running generation followed by operation polling until `done`. citeturn690979search0

Gemini API REST shape in this repo:

```bash
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/$VEO_DEFAULT_MODEL:predictLongRunning?key=$GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [{"prompt": "A cinematic waterfall in a misty jungle"}],
    "parameters": {"aspectRatio": "16:9", "durationSeconds": 5}
  }'
```

Poll:

```bash
curl "https://generativelanguage.googleapis.com/v1beta/operations/<OPERATION_NAME>?key=$GEMINI_API_KEY"
```

### Kling direct submit + poll

Kling public docs expose text-to-video API references and bearer token auth. Tenant-specific callback behavior may still differ, so confirm your account contract before relying on direct webhooks. citeturn288582search1

```bash
curl -X POST "$KLING_API_BASE_URL$KLING_TEXT_TO_VIDEO_PATH" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KLING_API_TOKEN" \
  -d '{
    "model_name": "'$KLING_DEFAULT_MODEL'",
    "prompt": "A fox running across a snowy field in cinematic slow motion",
    "mode": "std",
    "aspect_ratio": "16:9",
    "duration": "5"
  }'
```

Poll:

```bash
curl -H "Authorization: Bearer $KLING_API_TOKEN" \
  "$KLING_API_BASE_URL/v1/videos/text2video/<TASK_ID>"
```

## End-to-end sequence to verify in this repo

1. boot the stack with Docker
2. create a render job from API or UI
3. confirm scene has provider task id or operation name
4. hit either direct callback ingress or signed relay ingress
5. confirm scene transitions in status API
6. confirm postprocess is enqueued when all scenes become terminal
7. verify final output and frontend job detail
