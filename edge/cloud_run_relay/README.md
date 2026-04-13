# Cloud Run relay edge

This service receives provider webhooks on `/hooks/{provider}` and forwards them to the backend signed relay ingress:

- inbound: `/hooks/runway`, `/hooks/veo`, `/hooks/kling`
- outbound: `${BACKEND_RELAY_BASE_URL}/{provider}`

Required env:
- `BACKEND_RELAY_BASE_URL`
- `PROVIDER_RELAY_SHARED_SECRET` or provider-specific secret

Example local run:
```bash
cd edge/cloud_run_relay
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export BACKEND_RELAY_BASE_URL=http://localhost:8000/api/v1/provider-callbacks/relay
export PROVIDER_RELAY_SHARED_SECRET=replace-me
uvicorn main:app --reload --port 8080
```

Example Cloud Run deploy:
```bash
gcloud run deploy provider-callback-relay \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars BACKEND_RELAY_BASE_URL=https://your-backend.example.com/api/v1/provider-callbacks/relay,PROVIDER_RELAY_SHARED_SECRET=replace-me
```
