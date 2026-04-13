# DECISION ENGINE — 2026-04-11

Bản patch này thêm lớp **decision intelligence** vào monorepo vận hành:

- policy-driven evaluation
- queue / provider / release guardrail recommendations
- execution API cho incident actions có thể thực thi thật
- planned-only control-plane actions cho các hành động chưa có actuator runtime

## File mới
- `backend/app/policies/default_decision_policy.json`
- `backend/app/schemas/decision_engine.py`
- `backend/app/services/decision_engine.py`
- `backend/app/api/decision_engine.py`
- `backend/tests/test_decision_engine.py`

## API mới
- `GET /api/v1/decision-engine/evaluate`
- `POST /api/v1/decision-engine/execute`

## Những gì chạy thật
Hiện tại `execute` chạy thật cho:
- `ack_incident`
- `assign_incident`
- `resolve_incident`

Thông qua projector/action flow đã tồn tại.

## Những gì mới ở trạng thái planned_only
Các action dưới đây hiện **không giả vờ auto-execute**:
- `scale_worker`
- `switch_provider`
- `block_release`
- `rebalance_queue`

Lý do:
- repo hiện chưa có actuator an toàn cho autoscaling / traffic shifting / deploy gate mutation
- decision engine trả về `planned_only` để team hoặc control plane bên ngoài nối tiếp

## Rule mặc định
1. **queue_pressure**
   - queued jobs >= 3
   - hoặc processing jobs >= 5
   - khuyến nghị `scale_worker`

2. **provider_failure_surge**
   - failed scenes 24h >= 2
   - hoặc open incidents theo provider >= 2
   - khuyến nghị `switch_provider`

3. **release_guardrail**
   - critical open incidents >= 1
   - khuyến nghị `block_release`

4. **operator_overload**
   - open incidents per assignee >= 5
   - khuyến nghị `rebalance_queue`

## Mở rộng bước tiếp theo
Để biến decision engine thành control fabric thật, lớp tiếp theo nên thêm:
- worker concurrency actuator
- provider routing override store
- release gate flag persisted in database or config service
- audit log cho mọi quyết định auto-executed
