# Deployment Notes

## Recommended production services
- API: Cloud Run / ECS / Kubernetes
- Worker: dedicated Celery worker deployment
- Broker: Redis managed service
- DB: managed PostgreSQL
- Object storage: S3 / GCS / MinIO

## Required changes before production
- Wire real provider SDKs
- Add secrets management
- Serve output videos from object storage
- Replace mock task polling with provider polling/webhooks
- Add authentication and authorization
