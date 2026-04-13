# OBSERVABILITY + NOTIFICATION PLANE — 2026-04-11

Bản patch này nối autonomous control fabric với:
- metrics exporter
- alert/notification routing
- Slack/email/webhook notifications
- autopilot status dashboard
- global kill switch

## API mới
- `GET /metrics`
- `GET /api/v1/observability/status`
- `GET /api/v1/observability/metrics`
- `GET /api/v1/observability/kill-switch`
- `POST /api/v1/observability/kill-switch`
- `GET /api/v1/observability/notification-endpoints`
- `POST /api/v1/observability/notification-endpoints`
- `POST /api/v1/observability/notifications/test`
- `GET /api/v1/observability/notification-deliveries`
- `GET /api/v1/observability/autopilot-dashboard`

## Frontend
- `/autopilot`

## Runtime behavior
### Metrics exporter
Exports Prometheus-compatible plaintext from live DB state.

### Notification plane
Supported channel types:
- `slack` via incoming webhook target
- `webhook` via generic JSON POST
- `email` via SMTP

If SMTP is not configured:
- email delivery is logged as `planned_only`, not faked.

### Kill switch
Global kill switch blocks:
- autopilot evaluation loop
- render job creation
- render dispatch worker execution

### Dashboard
Shows:
- kill switch status
- release gate
- active provider overrides
- notification failures
- autopilot state counts
- latest decision audits
- latest notification deliveries

## Honest limits
- Slack support assumes an incoming webhook URL.
- Email requires SMTP env vars and is not auto-configured by repo.
- Escalation still routes through notification events; no external pager integration is assumed unless you add a matching webhook/Slack/email endpoint.
