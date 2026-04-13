
# PROVIDER PRODUCTION-READY PATCH (2026-04-11)

## Added
- `backend/app/providers/common.py`
- real-ish HTTP adapters for `runway`, `veo`, `kling`
- callback signature verification via shared HMAC secret
- provider retry / timeout / mock-fallback config
- adapter normalization tests

## Runway
Implemented against official docs:
- submit: `POST /v1/image_to_video`
- poll: `GET /v1/tasks/{id}`

Current behavior:
- supports text-to-video and image-to-video via `promptImage`
- uses `Authorization: Bearer ...` and `X-Runway-Version`
- callback verification uses shared HMAC secret because direct provider webhook signature details were not visible in current source context

## Veo
Implemented with two transports:
- Gemini API REST when `GOOGLE_GENAI_USE_VERTEX=false` and `GEMINI_API_KEY` is set
- Vertex AI REST when `GOOGLE_GENAI_USE_VERTEX=true` and ADC / service account auth is available

Current behavior:
- submit uses `:predictLongRunning`
- poll uses:
  - Gemini API: `GET /v1beta/{operation_name}`
  - Vertex AI: `:fetchPredictOperation`
- only fields clearly visible from official docs were wired directly
- callback path remains generic relay-ready because direct native callback contract was not visible

## Kling
Implemented as configurable direct HTTP client with the official visible paths:
- submit default path: `/v1/videos/text2video`
- status default path template: `/v1/videos/text2video/{task_id}`

Honest limitation:
- current visible source context confirmed `Authorization: Bearer <API Token>` and AccessKey/SecretKey -> API Token flow,
  but did not expose the token generation algorithm in machine-readable detail here.
- this patch therefore requires `KLING_API_TOKEN` directly for real calls.
- if you later provide the exact signing algorithm, this adapter can be completed without touching the rest of the pipeline.

## New env vars
- `GEMINI_API_KEY`
- `PROVIDER_MAX_RETRIES`
- `PROVIDER_RETRY_BASE_SECONDS`
- `PROVIDER_ALLOW_MOCK_FALLBACK`
- `PROVIDER_CALLBACK_SHARED_SECRET`
- `RUNWAY_CALLBACK_SHARED_SECRET`
- `KLING_CALLBACK_SHARED_SECRET`
- `KLING_API_TOKEN`
- `KLING_TEXT_TO_VIDEO_PATH`
- `KLING_TEXT_TO_VIDEO_STATUS_PATH_TEMPLATE`
