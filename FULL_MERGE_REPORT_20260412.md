# FULL MERGE REPORT — 2026-04-12

## Goal
Chuẩn hóa và gộp toàn bộ patch vào **một** monorepo duy nhất, giữ nguyên cấu trúc gốc `render_factory_monorepo/`, không tái cấu trúc cây thư mục.

## Base used
- `render_factory_monorepo_audio_studio_patch_20260411(2).zip`

Lý do:
- bundle này đã bao gồm audio studio
- đồng thời cũng đã bao gồm nhánh observability / autopilot / control fabric trước đó

## Additional bundles normalized and merged
- `production_timeline_patch_monorepo(2).zip`
- `enterprise_strategy_patch_monorepo(3).zip`

## Root normalization handled
Các bundle được chuẩn hóa về cùng một root:
- `render_factory_monorepo/`
- `audio_studio_patch_monorepo/`
- rootless files ở top-level

Mọi file sau merge đều được đặt dưới:
- `render_factory_monorepo/...`

## Merge policy used
1. Dùng base monorepo hoàn chỉnh nhất làm nền.
2. Copy **file unique** từ các bundle nhỏ hơn.
3. Với các file xương sống dễ xung đột:
   - `backend/app/main.py`
   - `backend/app/core/config.py`
   - `backend/app/models/__init__.py`
   - `frontend/src/lib/api.ts`
   - `frontend/src/app/page.tsx`

   đã thực hiện **hợp nhất thủ công** để tránh bundle nhỏ hơn ghi đè ngược cấu trúc hoàn chỉnh.

## Unique files copied from additional bundles
- `production_timeline_patch_monorepo(2).zip` → `backend/app/models/production_run.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/models/production_timeline_event.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/models/render_job_summary.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/schemas/production.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/services/audio/__init__.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/services/production/__init__.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/services/production/timeline_repository.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/services/production/status_rollup.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/services/production/timeline_service.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/services/production/event_writer.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/workers/celery_app.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/api/production.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/app/state.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/alembic/versions/20260412_0018_add_production_timeline_tables.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/tests/test_production_timeline_rollup.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/tests/test_production_timeline_service.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/tests/test_production_api.py`
- `production_timeline_patch_monorepo(2).zip` → `backend/tests/conftest.py`
- `production_timeline_patch_monorepo(2).zip` → `frontend/src/app/dashboard/page.tsx`
- `production_timeline_patch_monorepo(2).zip` → `frontend/src/app/render-jobs/[id]/page.tsx`
- `production_timeline_patch_monorepo(2).zip` → `docs/PRODUCTION_TIMELINE_PATCH_2026-04-12.md`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/models/enterprise_strategy_signal.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/models/objective_profile.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/models/contract_sla_profile.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/models/campaign_window.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/models/roadmap_priority.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/models/portfolio_allocation_plan.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/models/business_outcome_snapshot.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/models/strategy_directive.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/schemas/strategy.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/__init__.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/repository.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/strategy_ingestion_service.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/objective_translation_engine.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/tradeoff_governance_engine.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/portfolio_allocator.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/business_feedback_service.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/strategy_directive_bridge.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/strategy_service.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/workers/strategy_refresh_worker.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/workers/objective_rollup_worker.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/workers/portfolio_rebalance_worker.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/workers/business_outcome_rollup_worker.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/workers/strategy_mode_expiry_worker.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/api/strategy.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/alembic/versions/20260412_0019_add_enterprise_strategy_tables.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/tests/test_objective_translation_engine.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/tests/test_tradeoff_governance_engine.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/tests/test_strategy_directive_bridge.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/tests/test_portfolio_allocator.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/tests/test_strategy_api.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `frontend/src/app/strategy/page.tsx`
- `enterprise_strategy_patch_monorepo(3).zip` → `frontend/src/components/strategy/StrategyStateCard.tsx`
- `enterprise_strategy_patch_monorepo(3).zip` → `frontend/src/components/strategy/PortfolioAllocationTable.tsx`
- `enterprise_strategy_patch_monorepo(3).zip` → `frontend/src/components/strategy/DirectivePanel.tsx`
- `enterprise_strategy_patch_monorepo(3).zip` → `frontend/src/components/strategy/SlaRiskHeatmap.tsx`
- `enterprise_strategy_patch_monorepo(3).zip` → `frontend/src/components/strategy/CampaignTimeline.tsx`
- `enterprise_strategy_patch_monorepo(3).zip` → `docs/ENTERPRISE_STRATEGY_PATCH_2026-04-12.md`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/contract_sla_service.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/campaign_sync_service.py`
- `enterprise_strategy_patch_monorepo(3).zip` → `backend/app/services/strategy/directive_dispatcher.py`

## Manual merge summary
- `backend/app/main.py`
  - giữ toàn bộ router cũ
  - thêm `production_router`
  - thêm `strategy_router`

- `backend/app/core/config.py`
  - giữ toàn bộ settings runtime/control/observability/audio cũ
  - thêm các biến audio/provider thiếu từ bundle enterprise/production

- `backend/app/models/__init__.py`
  - thêm import/export cho production timeline models
  - thêm import/export cho enterprise strategy models

- `frontend/src/lib/api.ts`
  - giữ toàn bộ API helper cũ
  - thêm helper production + strategy từ bundle enterprise

- `frontend/src/app/page.tsx`
  - giữ homepage của monorepo đầy đủ
  - thêm card `Autopilot`
  - thêm card `Strategy`

## Honest limits
- Tôi không dùng cách overlay mù cho `main.py`, `config.py`, `models/__init__.py` vì các bundle nhỏ hơn dùng skeleton riêng, sẽ làm mất chức năng đã có.
- Tôi không khẳng định mọi test trong tất cả bundle đều pass trong sandbox này.
- Đây là **merge chuẩn hóa cấu trúc + hợp nhất code tree**, không phải xác minh runtime 100% của mọi patch mới thêm.

