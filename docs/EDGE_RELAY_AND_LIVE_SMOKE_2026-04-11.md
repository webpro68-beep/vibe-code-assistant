# Edge relay + live smoke runner

## What this patch adds
- configurable callback URL strategy from backend dispatch:
  - direct backend callback ingress
  - relay edge callback ingress
- sample relay edge worker for Cloud Run
- sample Nginx fronting config
- sample ngrok tunnel config
- end-to-end smoke runner:
  - create render job
  - wait until scene is submitted
  - deliver callback by direct / relay / edge path, or wait for poll mode
  - verify backend status API
  - verify frontend snapshot proxy
  - fetch frontend page HTML

## New env
```env
PROVIDER_CALLBACK_USE_RELAY=false
PROVIDER_CALLBACK_PUBLIC_BASE_URL=
PROVIDER_CALLBACK_RELAY_PATH_TEMPLATE=/hooks/{provider}
```

If `PROVIDER_CALLBACK_USE_RELAY=true`, the worker submits provider jobs with callback URL:
```txt
{PROVIDER_CALLBACK_PUBLIC_BASE_URL}{PROVIDER_CALLBACK_RELAY_PATH_TEMPLATE}
```
Example:
```env
PROVIDER_CALLBACK_USE_RELAY=true
PROVIDER_CALLBACK_PUBLIC_BASE_URL=https://your-edge-relay.example.com
PROVIDER_CALLBACK_RELAY_PATH_TEMPLATE=/hooks/{provider}
```

## Cloud Run relay
See `edge/cloud_run_relay/README.md`

## Nginx sample
See `edge/nginx/nginx.conf`

## ngrok sample
```bash
ngrok start --all --config ./edge/ngrok/ngrok.example.yml
```

## Live smoke examples

### 1) Relay callback directly to backend relay ingress
```bash
python ./scripts/smoke/live_provider_e2e.py \
  --provider runway \
  --backend-base-url http://localhost:8000 \
  --frontend-base-url http://localhost:3000 \
  --delivery-mode relay-callback \
  --relay-secret replace-me
```

### 2) Callback through edge relay worker
```bash
python ./scripts/smoke/live_provider_e2e.py \
  --provider kling \
  --backend-base-url http://localhost:8000 \
  --frontend-base-url http://localhost:3000 \
  --edge-base-url http://localhost:8080 \
  --delivery-mode edge-callback
```

### 3) Poll-only live provider run
```bash
python ./scripts/smoke/live_provider_e2e.py \
  --provider veo \
  --backend-base-url http://localhost:8000 \
  --frontend-base-url http://localhost:3000 \
  --delivery-mode poll \
  --timeout-seconds 900
```

## Honest limits
- The smoke runner can simulate callback success to validate callback ingress and frontend wiring even if the real provider job is still running.
- Frontend verification is implemented through a server-side proxy route at `/api/render-jobs/{jobId}/snapshot` plus page fetch. It does not run a browser automation stack.
- If you want true browser-level UI assertions, add Playwright in a later patch.
