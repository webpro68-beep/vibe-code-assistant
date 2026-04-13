# PLAYWRIGHT E2E + DOCKER COMPOSE LOCAL CHAIN

This patch adds a one-command local end-to-end path that covers:

1. create render job through backend API
2. wait until queue/worker submits scene to provider adapter
3. deliver callback through edge relay or direct relay
4. verify backend status API
5. verify frontend snapshot route
6. open frontend render-job page in Playwright and assert the page is alive

## What this suite is for

It is a **local chain verification** suite. It is designed to work even without real provider keys because the backend bundle already supports mock provider fallback when provider secrets are absent.

## One command

```bash
make e2e-local
```

This boots:
- postgres
- redis
- minio
- api
- worker
- beat
- flower
- frontend
- edge-relay

Then it runs Playwright inside the `playwright` service.

## Provider selection

Default:
```bash
E2E_PROVIDER=runway
E2E_DELIVERY_MODE=edge-callback
```

Examples:

```bash
E2E_PROVIDER=veo make e2e-local
E2E_PROVIDER=kling make e2e-local
E2E_DELIVERY_MODE=direct-relay make e2e-local
E2E_DELIVERY_MODE=poll make e2e-local
```

## Notes

- `edge-callback` posts callback payloads to `http://edge-relay:8080/hooks/{provider}`
- `direct-relay` signs the payload and posts directly to backend relay ingress
- `poll` skips callback injection and waits for provider poll fallback
- because this is local-chain oriented, the suite validates page load and backend snapshot consistency, not pixel-perfect UI behavior

## Honest limitation

This suite does **not** yet run browser-level assertions against live provider assets or completed merged video playback.
For that, a stronger next layer would be:
- Playwright artifact assertions
- MinIO object presence assertions
- subtitle/timeline UI assertions
