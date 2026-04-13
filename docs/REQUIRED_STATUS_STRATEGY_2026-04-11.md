# REQUIRED STATUS STRATEGY — 2026-04-11

Mục tiêu:
- giữ branch protection đủ chặt cho `main`
- không bắt mọi PR nhỏ phải trả giá full 9-shard matrix
- vẫn đảm bảo thay đổi rủi ro cao bị chặn bởi E2E phù hợp

## Recommended required checks

### For all pull requests
Bắt buộc:
- `backend-quick-check / backend-quick`
- `frontend-quick-check / frontend-quick`
- `smart-full-stack-e2e / no-op-summary`

Lý do:
- `no-op-summary` luôn tồn tại như một anchor status ổn định cho workflow smart.
- Khi smart CI quyết định chạy nhánh nặng hơn, các job tương ứng sẽ xuất hiện và `no-op-summary` sẽ không phải nhánh active.

### For high-risk paths
Không cấu hình branch protection theo từng path được trực tiếp trong GitHub UI.
Vì vậy chiến lược nên là:

1. `backend-quick` và `frontend-quick` luôn required
2. `smart-full-stack-e2e` là workflow required ở mức policy tổ chức/repo
3. CODEOWNERS ép review bổ sung cho:
   - `backend/**`
   - `e2e/**`
   - `edge/**`
   - `.github/workflows/**`
   - `docker-compose.yml`

## Merge policy recommendation
- Require pull request before merging
- Require approvals: 1 cho thường, 2 cho infra/CI/edge/backend critical
- Dismiss stale approvals when new commits are pushed
- Require conversation resolution
- Require status checks to pass before merging
- Require branch to be up to date before merging
- Include administrators: bật cho repo production

## Why not require every shard?
Vì workflow smart có conditional matrix. Nếu bắt từng shard làm required check cứng:
- PR chỉ đổi frontend sẽ bị kẹt vì các shard không tạo ra
- runner minutes bị đốt vô ích

## Stable required status naming
Ưu tiên dùng các tên job ổn định:
- `backend-quick`
- `frontend-quick`
- `no-op-summary`
- `full-matrix`
- `frontend-focused`
- `edge-focused`

Không dùng artifact name làm required status.
