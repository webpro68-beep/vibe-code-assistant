# CI FULL STACK E2E — 2026-04-11

Bản patch này thêm pipeline CI chạy trọn chuỗi local:

1. `docker compose up --build`
2. chờ healthchecks cho:
   - backend API
   - frontend
   - edge relay
3. chạy Playwright bằng container profile `e2e`
4. export artifacts:
   - HTML report
   - JSON report
   - JUnit XML
   - screenshots / videos / traces khi fail
5. export fail-fast report:
   - `docker compose ps -a`
   - logs cho `api`, `worker`, `frontend`, `edge-relay`
   - Playwright JSON summary nếu có

## File mới / sửa
- `.github/workflows/full-stack-e2e.yml`
- `scripts/ci/wait_for_stack.py`
- `scripts/ci/export_fail_fast_report.py`
- `docker-compose.yml`
- `e2e/playwright.config.ts`
- `Makefile`

## Lệnh local tương ứng
```bash
make ci-e2e
```

## Artifacts sau khi chạy
- `artifacts/playwright/html-report`
- `artifacts/playwright/results.json`
- `artifacts/playwright/results.xml`
- `artifacts/playwright/test-results`
- `artifacts/ci/fail_fast_report.md`

## Ghi chú trung thực
- Pipeline này giả định Docker Compose v2.
- Tôi đã sửa một lỗi cấu trúc thật trong `docker-compose.yml`: `edge-relay` và `playwright` phải nằm dưới `services`.
- Tôi chưa chạy GitHub Actions thật trong sandbox.


## Matrix mode
Bản này thêm matrix CI chạy song song theo:

- provider: `runway`, `veo`, `kling`
- delivery mode: `poll`, `direct-relay`, `edge-callback`

Tổng cộng: **9 shard jobs**

### Artifact tách riêng theo shard
Mỗi shard sẽ ghi artifact vào:
- `artifacts/playwright/<provider>-<mode>/html-report`
- `artifacts/playwright/<provider>-<mode>/results.json`
- `artifacts/playwright/<provider>-<mode>/results.xml`
- `artifacts/playwright/<provider>-<mode>/test-results`
- `artifacts/ci/<provider>-<mode>/fail_fast_report.md`

### GitHub Actions artifact names
- `e2e-runway-poll`
- `e2e-runway-direct-relay`
- `e2e-runway-edge-callback`
- `e2e-veo-poll`
- `e2e-veo-direct-relay`
- `e2e-veo-edge-callback`
- `e2e-kling-poll`
- `e2e-kling-direct-relay`
- `e2e-kling-edge-callback`

### Local sequential matrix
Nếu muốn chạy tuần tự ở local:
```bash
make ci-e2e-matrix
```

## Ghi chú trung thực
- Matrix GitHub Actions được cấu hình chạy song song bằng strategy matrix.
- Local `make ci-e2e-matrix` chạy tuần tự để giảm xung đột cổng và dễ debug.


## CI optimization patch
Bản này bổ sung 3 lớp tối ưu cho CI:

### 1. Concurrency control
Workflow giờ dùng:
```yaml
concurrency:
  group: full-stack-e2e-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

Ý nghĩa:
- cùng một branch/PR chỉ giữ lại run mới nhất
- run cũ đang chạy sẽ bị hủy
- giảm tốn runner minutes và giảm artifact rác

### 2. Cancel stale runs
`cancel-in-progress: true` là lớp chặn stale run hiệu quả nhất cho push liên tiếp.

### 3. Caching
Đã thêm cache cho:
- pip: `~/.cache/pip`
- npm: `~/.npm`, `e2e/node_modules`, `frontend/node_modules`
- Playwright browsers: `~/.cache/ms-playwright`
- Docker image layers qua `docker/bake-action` + `type=gha`

### 4. Build context cleanup
Đã thêm `.dockerignore` cho:
- `backend/`
- `frontend/`
- `edge/cloud_run_relay/`

Điều này giúp:
- giảm kích thước context
- build nhanh hơn
- ít invalid cache hơn

## Ghi chú trung thực
- Tôi không có số đo runtime thật trong GitHub Actions của repo này.
- Hiệu quả tăng tốc sẽ phụ thuộc vào mức ổn định của lockfiles, Dockerfiles, và tần suất thay đổi source.


## Smart CI patch: path filters + workflow split + conditional matrix

### 1. Path filters
Thêm workflow reusable:
- `.github/workflows/_changed-areas.yml`

Nó dùng `dorny/paths-filter` để phát hiện:
- `backend_changed`
- `frontend_changed`
- `e2e_changed`
- `edge_changed`
- `infra_changed`

### 2. Conditional matrix
Workflow chính giờ chọn chế độ chạy:

- **full matrix 9 shards** khi thay đổi đụng:
  - `backend/**`
  - `e2e/**`
  - `scripts/ci/**`
  - `scripts/smoke/**`
  - `docker-compose.yml`
  - `Makefile`
  - `.env.example`
  - `.github/workflows/**`

- **frontend-focused matrix** khi chỉ frontend đổi:
  - `runway × edge-callback`
  - `runway × direct-relay`

- **edge-focused matrix** khi chỉ edge relay đổi:
  - `runway × edge-callback`
  - `kling × edge-callback`

- **no-op summary** khi chỉ docs hoặc phần không cần E2E nặng thay đổi

### 3. Workflow split
Thêm quick workflows riêng:
- `.github/workflows/frontend-quick-check.yml`
- `.github/workflows/backend-quick-check.yml`

Mục tiêu:
- PR nhỏ chỉ cần typecheck frontend hoặc compile/pytest backend
- không phải kéo full-stack E2E nặng mọi lúc

### 4. Lợi ích thực tế
- tiết kiệm runner minutes
- giảm Docker boot không cần thiết
- giảm contention cho matrix 9 shards
- vẫn giữ full-matrix khi thay đổi có nguy cơ ảnh hưởng pipeline end-to-end

## Ghi chú trung thực
- Đây là chiến lược cắt giảm thông minh dựa trên vùng thay đổi, không phải proof tuyệt đối rằng khu vực khác không bị ảnh hưởng gián tiếp.
- Vì vậy backend/e2e/infra vẫn được map vào full matrix để an toàn hơn.


## Governance patch: required status + branch protection + flaky quarantine

### Added
- `.github/workflows/flaky-test-quarantine.yml`
- `.github/CODEOWNERS`
- `docs/REQUIRED_STATUS_STRATEGY_2026-04-11.md`
- `docs/BRANCH_PROTECTION_MAP_2026-04-11.md`
- `scripts/ci/export_quarantine_report.py`

### Flaky quarantine workflow
Workflow mới dùng cho:
- replay test nghi ngờ flaky theo lịch hằng ngày
- hoặc chạy tay qua `workflow_dispatch`
- có hỗ trợ `grep` để replay một nhóm test Playwright cụ thể

### Operational guidance
- branch protection map và required-status strategy là **tài liệu vận hành GitHub**
- chúng không tự áp branch protection vào repo
- bạn vẫn cần vào GitHub Settings để cấu hình rules/rulesets thật


## Decision engine note
- `GET /api/v1/decision-engine/evaluate` có thể được gọi ở bước pre-release để chặn deploy khi rule `block_release` được khuyến nghị.


## Autopilot note
- `POST /api/v1/autopilot/run` có thể được gọi trong smoke/admin flows để kiểm tra autonomous control fabric.
