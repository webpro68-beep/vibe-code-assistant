# CONTROL FABRIC — 2026-04-11

Bản patch này nối decision engine với **runtime actuator thật trong phạm vi repo hiện có**.

## Những gì đã trở thành actuator runtime thật

### 1. Worker concurrency override
Persisted table:
- `worker_concurrency_overrides`

Runtime effect:
- dispatch worker không còn luôn bắn toàn bộ queued scenes ngay một lượt
- nó đọc `dispatch_batch_limit`
- chỉ dispatch một batch
- nếu còn scene queued, tự re-enqueue `render.dispatch`
- poll fallback countdown cũng đọc từ override

Điều này biến decision `scale_worker` thành **thực thi runtime trong repo**, dù chưa phải autoscale container ở hạ tầng ngoài.

### 2. Provider routing override store
Persisted table:
- `provider_routing_overrides`

Runtime effect:
- trước khi submit scene, dispatch service resolve effective provider
- nếu có override `runway -> veo`, scene mới sẽ được gửi sang `veo`
- scene provider được cập nhật theo provider thật đã dispatch để poll/callback tiếp tục đúng

### 3. Release gate state persisted
Persisted table:
- `release_gate_states`

Runtime effect:
- route `POST /api/v1/render/jobs` sẽ từ chối tạo job mới với `423 LOCKED` khi release gate đang blocked

### 4. Audit log cho every decision execution
Persisted table:
- `decision_execution_audit_logs`

Runtime effect:
- mọi `execute_decision(...)` đều ghi audit row:
  - dry_run
  - executed
  - planned_only
  - rejected

## API mới
- `GET /api/v1/control-plane/worker-override`
- `POST /api/v1/control-plane/worker-override`
- `POST /api/v1/control-plane/provider-routing`
- `GET /api/v1/control-plane/release-gate`
- `POST /api/v1/control-plane/release-gate`
- `GET /api/v1/control-plane/decision-audit`

## Những gì vẫn chưa auto-execute hoàn toàn
- container autoscaling ngoài Docker/Celery runtime
- queue rebalance bulk reassignment an toàn
- deployment pipeline mutation ngoài repo

Những thứ này vẫn cần external control plane hoặc infrastructure API.

## Kết quả kiến trúc
Decision engine giờ đi được tới:
- evaluate
- persist control intent
- affect dispatch/runtime behavior
- block new release traffic
- record audit trail

Nói cách khác: **decision engine -> control plane -> control fabric** đã bắt đầu thành hình thật.
