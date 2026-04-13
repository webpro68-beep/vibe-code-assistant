# AUTONOMOUS CONTROL FABRIC — 2026-04-11

Bản patch này nối control fabric với **autopilot loop**.

## Những gì mới

### 1. Periodic decision evaluation worker
- Celery task: `autopilot.evaluate_control_fabric`
- Beat schedule mặc định: mỗi 5 phút

### 2. Auto-execute only safe decisions
Decision types whitelist:
- `scale_worker`
- `switch_provider`
- `block_release`

Các quyết định khác không thuộc safe list sẽ không auto-execute.

### 3. Cooldown / suppression windows
State table:
- `autopilot_execution_states`

Mỗi recommendation có thể bị:
- cooldown nếu vừa execute
- suppression nếu vừa bị reject/suppressed

Điều này ngăn autopilot spam cùng một action liên tục.

### 4. Escalation policy
Autopilot ghi audit escalation khi:
- queue pressure vượt escalation threshold
- critical incident load vượt escalation threshold

Hiện escalation ghi vào audit trail để làm integration point cho pager/on-call layer.

### 5. Release unblocking policy
Khi:
- release gate đang blocked
- không còn critical open incidents
- đã qua cooldown window

Autopilot sẽ auto-unblock release gate.

### 6. Provider override expiry / rollback policy
Provider routing override có `expires_at`.
Khi hết hạn:
- autopilot tự deactivate override
- ghi audit log rollback

## API
- `POST /api/v1/autopilot/run`

## Migration mới
- `20260411_0015_add_autopilot_execution_state.py`

## Honest limits
- escalation hiện mới ghi audit, chưa gọi pager service ngoài repo
- cooldown/suppression là theo recommendation key + decision type, chưa phải suppression engine đa chiều
- autoscaling container runtime ngoài Celery/Docker stack vẫn cần hạ tầng ngoài
