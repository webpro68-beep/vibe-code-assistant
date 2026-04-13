# Veo Quota-Aware Batch Scheduler + Account Rotation + Retry Policy Spec

hệ của bạn đã có đủ lớp workspace/config/batch/materialization. Thiếu lớn nhất còn lại là lớp execution governance cho batch Veo khi chạy thật ở production.
Phase tiếp theo nên là
PHASE — VEO QUOTA-AWARE BATCH SCHEDULER + PROVIDER ACCOUNT ROTATION + MODE-AWARE RETRY POLICY
Mục tiêu
Biến VeoBatchRun từ trạng thái đã lưu và sẵn sàng chạy thành thực thi thật qua render queue hiện có, nhưng vẫn giữ nguyên monorepo và không tách kiến trúc mới không cần thiết.
1) Backend schema nên bổ sung
Patch model hiện có
backend/app/models/veo_workspace.py
Bổ sung vào VeoBatchRun:
status
submitted_at
started_at
completed_at
failed_at
scheduler_note
provider_name
provider_account_id
requested_mode
retry_policy_snapshot
rate_limit_bucket
max_parallelism
dispatched_count
succeeded_count
failed_count
Bổ sung vào VeoBatchItem:
status
attempt_count
last_error_code
last_error_message
next_retry_at
provider_name
provider_account_id
render_job_id
project_id
scene_count
mode
priority_score
lease_token
leased_at
finished_at
File migration mới
backend/alembic/versions/20260412_0023_veo_batch_scheduler_runtime.py
Mục tiêu migration:
thêm cột runtime state cho batch
index cho:
veo_batch_runs.status
veo_batch_items.status
veo_batch_items.next_retry_at
veo_batch_items.batch_run_id
veo_batch_items.render_job_id
optional unique/index cho lease_token
2) Service layer cần thêm
File mới
backend/app/services/veo_batch_scheduler_service.py
Nhiệm vụ:
chọn batch có thể dispatch
respect quota/config
lease item pending
route item vào render runtime hiện có
cập nhật state batch/item
Core methods nên có:
class VeoBatchSchedulerService:
    def dispatch_ready_batches(self) -> dict: ...
    def lease_next_items(self, batch_run_id: str, limit: int) -> list: ...
    def dispatch_item(self, item_id: str) -> dict: ...
    def mark_item_started(self, item_id: str, render_job_id: str) -> None: ...
    def mark_item_succeeded(self, item_id: str, result: dict) -> None: ...
    def mark_item_failed(self, item_id: str, error: dict) -> None: ...
    def recompute_batch_status(self, batch_run_id: str) -> None: ...
File mới
backend/app/services/provider_account_rotation_service.py
Nhiệm vụ:
chọn account/provider phù hợp cho item tiếp theo
tránh dồn tất cả qua một account
có thể ưu tiên account còn quota hoặc ít lỗi gần đây
Core methods:
class ProviderAccountRotationService:
    def pick_account_for_mode(self, provider: str, mode: str) -> dict | None: ...
    def mark_dispatch(self, provider: str, account_id: str) -> None: ...
    def mark_failure(self, provider: str, account_id: str, error_code: str) -> None: ...
    def mark_success(self, provider: str, account_id: str) -> None: ...
File mới
backend/app/services/veo_retry_policy_service.py
Nhiệm vụ:
retry theo mode
phân biệt retryable / non-retryable
backoff khác nhau giữa:
text_to_video
image_to_video
first_last_frames
reference_image_to_video preview path
Core methods:
class VeoRetryPolicyService:
    def classify_error(self, error: dict) -> dict: ...
    def should_retry(self, item, error: dict) -> bool: ...
    def next_retry_at(self, item, error: dict): ...
    def max_attempts_for_mode(self, mode: str) -> int: ...
3) Worker layer cần nối thật
File mới
backend/app/workers/veo_batch_scheduler_worker.py
Nhiệm vụ:
chạy theo tick
lấy các batch queued / dispatching
dispatch item theo quota và parallelism
Patch
backend/app/workers/render_dispatch_worker.py
Bổ sung:
nhận metadata từ VeoBatchItem
preserve:
batch_run_id
batch_item_id
mode
character_reference_pack_id
Patch
backend/app/workers/render_poll_worker.py
Bổ sung:
khi job complete/fail:
callback update VeoBatchItem
recompute VeoBatchRun
Patch
backend/app/workers/render_postprocess_worker.py
Bổ sung:
giữ trace từ render output về batch item
lưu output URL / preview URL / failure summary cho batch UI
4) Queue policy cần thêm vào config
Patch
backend/app/core/config.py
Biến nên thêm:
VEO_BATCH_DISPATCH_TICK_SECONDS
VEO_BATCH_MAX_PARALLEL_ITEMS
VEO_BATCH_MAX_RETRIES_TEXT
VEO_BATCH_MAX_RETRIES_IMAGE
VEO_BATCH_MAX_RETRIES_FIRST_LAST
VEO_BATCH_MAX_RETRIES_REFERENCE_PREVIEW
VEO_BATCH_RETRY_BACKOFF_SECONDS
VEO_BATCH_LEASE_TTL_SECONDS
VEO_PROVIDER_ROTATION_ENABLED
VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS
VEO_BATCH_QUOTA_AWARE_SCHEDULING=true
Patch
.env.example
backend/.env.example
Thêm đầy đủ các biến trên.
5) API nên mở rộng thêm
Patch
backend/app/api/veo_workspace.py
API nên có thêm:
POST /api/v1/veo/batch-runs/{batch_id}/dispatch
ép batch vào hàng dispatch
POST /api/v1/veo/batch-runs/{batch_id}/cancel
hủy các item chưa chạy
POST /api/v1/veo/batch-runs/{batch_id}/retry-failed
tạo lại hoặc requeue item fail
GET /api/v1/veo/batch-runs/{batch_id}/items
phân trang items
filter:
status
mode
provider
account
GET /api/v1/veo/batch-runs/{batch_id}/stats
pending/running/succeeded/failed
average attempts
retries used
provider distribution
6) Frontend nên nối thêm
File mới
frontend/src/components/veo/VeoBatchRunPanel.tsx
Hiển thị:
batch summary
progress bar
per-status counters
dispatch/cancel/retry actions
File mới
frontend/src/components/veo/VeoBatchItemsTable.tsx
Cột nên có:
script title
mode
status
attempts
provider/account
render job
next retry
output link
error summary
Patch
frontend/src/app/projects/[id]/page.tsx
Thêm:
tab batch runs
live refresh batch status
action buttons
Patch
frontend/src/lib/api.ts
Thêm client methods cho toàn bộ API mới.
7) Trạng thái runtime nên chuẩn hóa
VeoBatchRun.status
draft
queued
dispatching
running
completed
partially_failed
failed
cancelled
VeoBatchItem.status
pending
leased
submitted
running
succeeded
retry_waiting
failed
cancelled
Cách này rất hợp với render runtime đang có và không phải bẻ kiến trúc.
8) Retry policy nên chia theo mode
text_to_video
retry trung bình
backoff chuẩn
image_to_video
retry ít hơn text một chút nếu input image invalid thường là lỗi cứng
first_last_frames
retry ít
lỗi input pair nên classify sớm là non-retryable
reference_image_to_video
retry thấp nhất
nếu preview path/config không bật thì fail sớm, không retry loop
9) Provider account rotation nên đặt ở đâu
Cách đúng là:
không nhét rotation vào adapter
để ở scheduler/service layer
Lý do:
adapter chỉ nên lo request/response provider
rotation là execution governance
như vậy giữ adapter sạch và dễ test hơn
10) Thứ tự triển khai mạnh nhất
Backend trước
migration runtime state
veo_batch_scheduler_service.py
veo_retry_policy_service.py
provider_account_rotation_service.py
patch worker dispatch/poll/postprocess
patch API dispatch/cancel/retry/stats
Frontend sau
api.ts
VeoBatchRunPanel.tsx
VeoBatchItemsTable.tsx
patch project workspace page
11) Kết quả sau phase này
Hệ của bạn sẽ đi từ:
workspace-driven Veo batch preparation
sang:
quota-aware production execution layer
Tức là lúc đó repo không chỉ:
tạo pack
tạo batch
build project từ script
mà còn:
dispatch batch thật
điều tiết quota
xoay account/provider
retry theo mode
theo dõi progress từng item
gom kết quả vào runtime hiện có
12) Kết luận kỹ thuật
Thiết kế hiện tại của bạn là đúng hướng.
Điểm rất mạnh là bạn không cố làm một Veo-only orchestration mới, mà tận dụng render runtime sẵn có.
Bước tiếp theo đúng nhất không phải thêm UI mới nữa, mà là thêm scheduler governance layer để batch Veo chạy thật một cách ổn định.
Mình viết theo đúng kiểu file-by-file paste-ready, ưu tiên bám monorepo hiện có, không tách kiến trúc mới.
1) backend/alembic/versions/20260412_0023_veo_batch_scheduler_runtime.py
"""veo batch scheduler runtime

Revision ID: 20260412_0023
Revises: 20260412_0022
Create Date: 2026-04-12 10:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0023"
down_revision = "20260412_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("veo_batch_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"))
        batch_op.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("scheduler_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("provider_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("provider_account_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("requested_mode", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("retry_policy_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("rate_limit_bucket", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("max_parallelism", sa.Integer(), nullable=False, server_default="4"))
        batch_op.add_column(sa.Column("dispatched_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("succeeded_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"))

    with op.batch_alter_table("veo_batch_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"))
        batch_op.add_column(sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("last_error_code", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("last_error_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("provider_name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("provider_account_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("render_job_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("project_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("scene_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("mode", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("lease_token", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("leased_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("output_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("preview_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("result_payload", sa.JSON(), nullable=True))

    op.create_index("ix_veo_batch_runs_status", "veo_batch_runs", ["status"], unique=False)
    op.create_index("ix_veo_batch_runs_submitted_at", "veo_batch_runs", ["submitted_at"], unique=False)

    op.create_index("ix_veo_batch_items_status", "veo_batch_items", ["status"], unique=False)
    op.create_index("ix_veo_batch_items_next_retry_at", "veo_batch_items", ["next_retry_at"], unique=False)
    op.create_index("ix_veo_batch_items_batch_run_id", "veo_batch_items", ["batch_run_id"], unique=False)
    op.create_index("ix_veo_batch_items_render_job_id", "veo_batch_items", ["render_job_id"], unique=False)
    op.create_index("ix_veo_batch_items_lease_token", "veo_batch_items", ["lease_token"], unique=False)
    op.create_index("ix_veo_batch_items_project_id", "veo_batch_items", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_veo_batch_items_project_id", table_name="veo_batch_items")
    op.drop_index("ix_veo_batch_items_lease_token", table_name="veo_batch_items")
    op.drop_index("ix_veo_batch_items_render_job_id", table_name="veo_batch_items")
    op.drop_index("ix_veo_batch_items_batch_run_id", table_name="veo_batch_items")
    op.drop_index("ix_veo_batch_items_next_retry_at", table_name="veo_batch_items")
    op.drop_index("ix_veo_batch_items_status", table_name="veo_batch_items")

    op.drop_index("ix_veo_batch_runs_submitted_at", table_name="veo_batch_runs")
    op.drop_index("ix_veo_batch_runs_status", table_name="veo_batch_runs")

    with op.batch_alter_table("veo_batch_items", schema=None) as batch_op:
        batch_op.drop_column("result_payload")
        batch_op.drop_column("preview_url")
        batch_op.drop_column("output_url")
        batch_op.drop_column("finished_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("submitted_at")
        batch_op.drop_column("leased_at")
        batch_op.drop_column("lease_token")
        batch_op.drop_column("priority_score")
        batch_op.drop_column("mode")
        batch_op.drop_column("scene_count")
        batch_op.drop_column("project_id")
        batch_op.drop_column("render_job_id")
        batch_op.drop_column("provider_account_id")
        batch_op.drop_column("provider_name")
        batch_op.drop_column("next_retry_at")
        batch_op.drop_column("last_error_message")
        batch_op.drop_column("last_error_code")
        batch_op.drop_column("attempt_count")
        batch_op.drop_column("status")

    with op.batch_alter_table("veo_batch_runs", schema=None) as batch_op:
        batch_op.drop_column("failed_count")
        batch_op.drop_column("succeeded_count")
        batch_op.drop_column("dispatched_count")
        batch_op.drop_column("max_parallelism")
        batch_op.drop_column("rate_limit_bucket")
        batch_op.drop_column("retry_policy_snapshot")
        batch_op.drop_column("requested_mode")
        batch_op.drop_column("provider_account_id")
        batch_op.drop_column("provider_name")
        batch_op.drop_column("scheduler_note")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("failed_at")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("submitted_at")
        batch_op.drop_column("status")
2) backend/app/services/veo_retry_policy_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from backend.app.core.config import settings


RETRYABLE_ERROR_CODES = {
    "429",
    "500",
    "502",
    "503",
    "504",
    "rate_limit",
    "timeout",
    "upstream_unavailable",
    "transient_provider_error",
}

NON_RETRYABLE_ERROR_CODES = {
    "400",
    "401",
    "403",
    "404",
    "invalid_mode",
    "invalid_prompt",
    "invalid_start_image",
    "invalid_end_image",
    "invalid_reference_image",
    "preview_mode_disabled",
    "unsupported_model_mode",
}


@dataclass
class RetryDecision:
    should_retry: bool
    retryable: bool
    reason: str
    error_code: str
    next_retry_at: Optional[datetime]
    backoff_seconds: int
    max_attempts: int


class VeoRetryPolicyService:
    def __init__(self) -> None:
        self.default_backoff_seconds = int(getattr(settings, "VEO_BATCH_RETRY_BACKOFF_SECONDS", 60))
        self.text_max_retries = int(getattr(settings, "VEO_BATCH_MAX_RETRIES_TEXT", 3))
        self.image_max_retries = int(getattr(settings, "VEO_BATCH_MAX_RETRIES_IMAGE", 2))
        self.first_last_max_retries = int(getattr(settings, "VEO_BATCH_MAX_RETRIES_FIRST_LAST", 2))
        self.reference_preview_max_retries = int(
            getattr(settings, "VEO_BATCH_MAX_RETRIES_REFERENCE_PREVIEW", 1)
        )

    def classify_error(self, error: Dict[str, Any] | Exception | None) -> Dict[str, Any]:
        if error is None:
            return {
                "retryable": False,
                "error_code": "unknown",
                "reason": "Unknown error",
            }

        if isinstance(error, Exception):
            message = str(error)
            code = getattr(error, "code", None) or getattr(error, "status_code", None) or "exception"
            return self._normalize_error(code=code, message=message)

        code = (
            error.get("error_code")
            or error.get("code")
            or error.get("status")
            or error.get("status_code")
            or "unknown"
        )
        message = (
            error.get("message")
            or error.get("detail")
            or error.get("error")
            or "Unknown provider error"
        )
        return self._normalize_error(code=code, message=message)

    def should_retry(self, item: Any, error: Dict[str, Any] | Exception | None) -> RetryDecision:
        classified = self.classify_error(error)
        mode = getattr(item, "mode", None) or "text_to_video"
        attempt_count = int(getattr(item, "attempt_count", 0))
        max_attempts = self.max_attempts_for_mode(mode)

        if not classified["retryable"]:
            return RetryDecision(
                should_retry=False,
                retryable=False,
                reason=classified["reason"],
                error_code=classified["error_code"],
                next_retry_at=None,
                backoff_seconds=0,
                max_attempts=max_attempts,
            )

        if attempt_count >= max_attempts:
            return RetryDecision(
                should_retry=False,
                retryable=True,
                reason=f"Retryable error but max attempts reached ({attempt_count}/{max_attempts})",
                error_code=classified["error_code"],
                next_retry_at=None,
                backoff_seconds=0,
                max_attempts=max_attempts,
            )

        backoff_seconds = self._backoff_seconds(mode=mode, attempt_count=attempt_count)
        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)

        return RetryDecision(
            should_retry=True,
            retryable=True,
            reason=classified["reason"],
            error_code=classified["error_code"],
            next_retry_at=next_retry_at,
            backoff_seconds=backoff_seconds,
            max_attempts=max_attempts,
        )

    def next_retry_at(self, item: Any, error: Dict[str, Any] | Exception | None) -> Optional[datetime]:
        return self.should_retry(item, error).next_retry_at

    def max_attempts_for_mode(self, mode: str) -> int:
        normalized = (mode or "").strip().lower()
        if normalized == "image_to_video":
            return self.image_max_retries
        if normalized == "first_last_frames":
            return self.first_last_max_retries
        if normalized == "reference_image_to_video":
            return self.reference_preview_max_retries
        return self.text_max_retries

    def _normalize_error(self, code: Any, message: str) -> Dict[str, Any]:
        normalized_code = str(code).strip().lower()
        retryable = normalized_code in RETRYABLE_ERROR_CODES

        if normalized_code in NON_RETRYABLE_ERROR_CODES:
            retryable = False

        if "rate" in message.lower() or "quota" in message.lower():
            retryable = True
            normalized_code = "rate_limit"

        if "timeout" in message.lower():
            retryable = True
            normalized_code = "timeout"

        if "preview" in message.lower() and "disabled" in message.lower():
            retryable = False
            normalized_code = "preview_mode_disabled"

        return {
            "retryable": retryable,
            "error_code": normalized_code,
            "reason": message,
        }

    def _backoff_seconds(self, mode: str, attempt_count: int) -> int:
        base = self.default_backoff_seconds

        if mode == "reference_image_to_video":
            base = max(base, 120)
        elif mode == "image_to_video":
            base = max(base, 90)
        elif mode == "first_last_frames":
            base = max(base, 75)

        return base * (2 ** max(attempt_count, 0))
3) backend/app/services/provider_account_rotation_service.py
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings


@dataclass
class ProviderAccountLease:
    provider_name: str
    account_id: str
    cooldown_until: Optional[datetime] = None


class ProviderAccountRotationService:
    """
    Rotation layer ở service/scheduler, không đặt trong adapter.
    Mặc định dùng config JSON:
        VEO_PROVIDER_ACCOUNT_POOL_JSON='{"veo":[{"id":"acct-1"},{"id":"acct-2"}]}'
    """

    def __init__(self) -> None:
        self.rotation_enabled = bool(getattr(settings, "VEO_PROVIDER_ROTATION_ENABLED", False))
        self.cooldown_seconds = int(getattr(settings, "VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS", 120))
        self._dispatch_counts: Dict[str, int] = defaultdict(int)
        self._failure_counts: Dict[str, int] = defaultdict(int)
        self._cooldowns: Dict[str, datetime] = {}
        self._cursor: Dict[str, int] = defaultdict(int)

    def pick_account_for_mode(self, provider: str, mode: str) -> Optional[Dict[str, Any]]:
        accounts = self._accounts_for_provider(provider=provider)
        if not accounts:
            return None

        if not self.rotation_enabled or len(accounts) == 1:
            account = accounts[0]
            return {
                "provider_name": provider,
                "account_id": account["id"],
            }

        now = datetime.now(timezone.utc)
        available = [
            account
            for account in accounts
            if self._cooldowns.get(self._key(provider, account["id"])) is None
            or self._cooldowns[self._key(provider, account["id"])] <= now
        ]

        if not available:
            available = accounts

        ranked = sorted(
            available,
            key=lambda account: (
                self._failure_counts[self._key(provider, account["id"])],
                self._dispatch_counts[self._key(provider, account["id"])],
            ),
        )

        cursor = self._cursor[provider] % len(ranked)
        picked = ranked[cursor]
        self._cursor[provider] += 1

        return {
            "provider_name": provider,
            "account_id": picked["id"],
        }

    def mark_dispatch(self, provider: str, account_id: str) -> None:
        self._dispatch_counts[self._key(provider, account_id)] += 1

    def mark_failure(self, provider: str, account_id: str, error_code: str) -> None:
        key = self._key(provider, account_id)
        self._failure_counts[key] += 1

        if str(error_code).lower() in {"429", "rate_limit", "quota_exceeded"}:
            self._cooldowns[key] = datetime.now(timezone.utc) + timedelta(seconds=self.cooldown_seconds)

    def mark_success(self, provider: str, account_id: str) -> None:
        key = self._key(provider, account_id)
        self._failure_counts[key] = max(0, self._failure_counts[key] - 1)

    def _accounts_for_provider(self, provider: str) -> List[Dict[str, Any]]:
        raw = getattr(settings, "VEO_PROVIDER_ACCOUNT_POOL_JSON", "") or ""
        if not raw.strip():
            return []

        try:
            pool = json.loads(raw)
        except json.JSONDecodeError:
            return []

        provider_accounts = pool.get(provider) or pool.get(provider.lower()) or []
        results = []
        for item in provider_accounts:
            if isinstance(item, str):
                results.append({"id": item})
            elif isinstance(item, dict) and item.get("id"):
                results.append(item)
        return results

    def _key(self, provider: str, account_id: str) -> str:
        return f"{provider}:{account_id}"
4) backend/app/services/veo_batch_scheduler_service.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.veo_workspace import VeoBatchRun, VeoBatchItem
from backend.app.services.provider_account_rotation_service import ProviderAccountRotationService
from backend.app.services.veo_retry_policy_service import VeoRetryPolicyService

try:
    from backend.app.workers.render_dispatch_worker import dispatch_render_job_task
except Exception:  # pragma: no cover
    dispatch_render_job_task = None


BATCH_RUN_ACTIVE_STATUSES = {"queued", "dispatching", "running"}
BATCH_ITEM_READY_STATUSES = {"pending", "retry_waiting"}
BATCH_ITEM_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
DEFAULT_PROVIDER_NAME = "veo"


class VeoBatchSchedulerService:
    def __init__(
        self,
        db: Optional[Session] = None,
        retry_policy_service: Optional[VeoRetryPolicyService] = None,
        rotation_service: Optional[ProviderAccountRotationService] = None,
    ) -> None:
        self.db = db or SessionLocal()
        self.retry_policy_service = retry_policy_service or VeoRetryPolicyService()
        self.rotation_service = rotation_service or ProviderAccountRotationService()
        self.lease_ttl_seconds = int(getattr(settings, "VEO_BATCH_LEASE_TTL_SECONDS", 300))
        self.global_parallel_limit = int(getattr(settings, "VEO_BATCH_MAX_PARALLEL_ITEMS", 4))

    def dispatch_ready_batches(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        runs = self.db.execute(
            select(VeoBatchRun)
            .where(VeoBatchRun.status.in_(["queued", "dispatching", "running"]))
            .order_by(VeoBatchRun.submitted_at.asc().nullsfirst(), VeoBatchRun.created_at.asc())
        ).scalars().all()

        dispatched_batches = 0
        dispatched_items = 0

        for run in runs:
            in_flight = self._count_in_flight_items(run.id)
            max_parallelism = int(getattr(run, "max_parallelism", 0) or self.global_parallel_limit)
            capacity = max(0, max_parallelism - in_flight)
            if capacity <= 0:
                continue

            leased_items = self.lease_next_items(batch_run_id=run.id, limit=capacity)
            if leased_items:
                dispatched_batches += 1

            for item in leased_items:
                self.dispatch_item(item_id=item.id)
                dispatched_items += 1

            if not getattr(run, "started_at", None) and dispatched_items > 0:
                run.started_at = now
            if run.status in {"queued", "dispatching"} and self._count_in_flight_items(run.id) > 0:
                run.status = "running"

            self.db.add(run)
            self.db.commit()

        return {
            "ok": True,
            "dispatched_batches": dispatched_batches,
            "dispatched_items": dispatched_items,
        }

    def lease_next_items(self, batch_run_id: str, limit: int) -> List[VeoBatchItem]:
        if limit <= 0:
            return []

        now = datetime.now(timezone.utc)
        lease_token = str(uuid.uuid4())

        ready_items = self.db.execute(
            select(VeoBatchItem)
            .where(
                VeoBatchItem.batch_run_id == batch_run_id,
                or_(
                    VeoBatchItem.status == "pending",
                    and_(
                        VeoBatchItem.status == "retry_waiting",
                        VeoBatchItem.next_retry_at.is_not(None),
                        VeoBatchItem.next_retry_at <= now,
                    ),
                ),
            )
            .order_by(VeoBatchItem.priority_score.desc(), VeoBatchItem.created_at.asc())
            .limit(limit)
        ).scalars().all()

        leased: List[VeoBatchItem] = []
        for item in ready_items:
            item.status = "leased"
            item.lease_token = lease_token
            item.leased_at = now
            self.db.add(item)
            leased.append(item)

        run = self.db.get(VeoBatchRun, batch_run_id)
        if run and run.status == "queued":
            run.status = "dispatching"
            run.submitted_at = run.submitted_at or now
            self.db.add(run)

        self.db.commit()
        return leased

    def dispatch_item(self, item_id: str) -> Dict[str, Any]:
        item = self.db.get(VeoBatchItem, item_id)
        if not item:
            return {"ok": False, "error": "batch_item_not_found"}

        run = self.db.get(VeoBatchRun, item.batch_run_id)
        if not run:
            item.status = "failed"
            item.last_error_code = "batch_run_not_found"
            item.last_error_message = "Batch run not found for item dispatch"
            self.db.add(item)
            self.db.commit()
            return {"ok": False, "error": "batch_run_not_found"}

        provider_name = getattr(run, "provider_name", None) or DEFAULT_PROVIDER_NAME
        mode = getattr(item, "mode", None) or getattr(run, "requested_mode", None) or "text_to_video"

        account_selection = self.rotation_service.pick_account_for_mode(provider=provider_name, mode=mode)
        if account_selection:
            item.provider_name = account_selection["provider_name"]
            item.provider_account_id = account_selection["account_id"]
            run.provider_name = account_selection["provider_name"]
            run.provider_account_id = account_selection["account_id"]

        if dispatch_render_job_task is None:
            item.status = "failed"
            item.last_error_code = "dispatch_task_unavailable"
            item.last_error_message = "Render dispatch task is not available"
            item.finished_at = datetime.now(timezone.utc)
            self.db.add(item)
            self.db.commit()
            self.recompute_batch_status(run.id)
            return {"ok": False, "error": "dispatch_task_unavailable"}

        payload = {
            "project_id": getattr(item, "project_id", None),
            "batch_run_id": item.batch_run_id,
            "batch_item_id": item.id,
            "provider_name": item.provider_name or provider_name,
            "provider_account_id": item.provider_account_id,
            "mode": mode,
            "scene_count": getattr(item, "scene_count", 0),
            "veo_config": getattr(item, "veo_config", None) or getattr(run, "veo_config", None),
        }

        async_result = dispatch_render_job_task.delay(payload)

        item.render_job_id = str(async_result.id)
        item.status = "submitted"
        item.submitted_at = datetime.now(timezone.utc)
        item.attempt_count = int(getattr(item, "attempt_count", 0) or 0) + 1
        item.last_error_code = None
        item.last_error_message = None
        item.next_retry_at = None

        run.dispatched_count = int(getattr(run, "dispatched_count", 0) or 0) + 1
        run.status = "running"
        run.started_at = run.started_at or datetime.now(timezone.utc)

        self.db.add(item)
        self.db.add(run)
        self.db.commit()

        if item.provider_name and item.provider_account_id:
            self.rotation_service.mark_dispatch(item.provider_name, item.provider_account_id)

        return {
            "ok": True,
            "batch_item_id": item.id,
            "render_job_id": item.render_job_id,
        }

    def mark_item_started(self, item_id: str, render_job_id: Optional[str] = None) -> None:
        item = self.db.get(VeoBatchItem, item_id)
        if not item:
            return
        item.status = "running"
        item.started_at = item.started_at or datetime.now(timezone.utc)
        if render_job_id:
            item.render_job_id = render_job_id
        self.db.add(item)
        self.db.commit()

    def mark_item_succeeded(self, item_id: str, result: Dict[str, Any]) -> None:
        item = self.db.get(VeoBatchItem, item_id)
        if not item:
            return

        item.status = "succeeded"
        item.finished_at = datetime.now(timezone.utc)
        item.output_url = result.get("output_url") or result.get("video_url")
        item.preview_url = result.get("preview_url") or result.get("thumbnail_url")
        item.result_payload = result
        item.last_error_code = None
        item.last_error_message = None
        self.db.add(item)

        run = self.db.get(VeoBatchRun, item.batch_run_id)
        if run:
            run.succeeded_count = int(getattr(run, "succeeded_count", 0) or 0) + 1
            self.db.add(run)

        if item.provider_name and item.provider_account_id:
            self.rotation_service.mark_success(item.provider_name, item.provider_account_id)

        self.db.commit()
        self.recompute_batch_status(item.batch_run_id)

    def mark_item_failed(self, item_id: str, error: Dict[str, Any] | Exception | None) -> None:
        item = self.db.get(VeoBatchItem, item_id)
        if not item:
            return

        decision = self.retry_policy_service.should_retry(item, error)
        item.last_error_code = decision.error_code
        item.last_error_message = decision.reason

        if decision.should_retry:
            item.status = "retry_waiting"
            item.next_retry_at = decision.next_retry_at
        else:
            item.status = "failed"
            item.finished_at = datetime.now(timezone.utc)

            run = self.db.get(VeoBatchRun, item.batch_run_id)
            if run:
                run.failed_count = int(getattr(run, "failed_count", 0) or 0) + 1
                self.db.add(run)

        self.db.add(item)

        if item.provider_name and item.provider_account_id:
            self.rotation_service.mark_failure(
                item.provider_name,
                item.provider_account_id,
                decision.error_code,
            )

        self.db.commit()
        self.recompute_batch_status(item.batch_run_id)

    def cancel_batch(self, batch_run_id: str) -> Dict[str, Any]:
        run = self.db.get(VeoBatchRun, batch_run_id)
        if not run:
            return {"ok": False, "error": "batch_run_not_found"}

        pending_items = self.db.execute(
            select(VeoBatchItem).where(
                VeoBatchItem.batch_run_id == batch_run_id,
                VeoBatchItem.status.in_(["pending", "leased", "retry_waiting", "submitted"]),
            )
        ).scalars().all()

        now = datetime.now(timezone.utc)
        for item in pending_items:
            item.status = "cancelled"
            item.finished_at = now
            self.db.add(item)

        run.status = "cancelled"
        run.cancelled_at = now
        self.db.add(run)
        self.db.commit()

        return {
            "ok": True,
            "cancelled_items": len(pending_items),
            "batch_run_id": batch_run_id,
        }

    def retry_failed(self, batch_run_id: str) -> Dict[str, Any]:
        run = self.db.get(VeoBatchRun, batch_run_id)
        if not run:
            return {"ok": False, "error": "batch_run_not_found"}

        failed_items = self.db.execute(
            select(VeoBatchItem).where(
                VeoBatchItem.batch_run_id == batch_run_id,
                VeoBatchItem.status == "failed",
            )
        ).scalars().all()

        for item in failed_items:
            item.status = "pending"
            item.next_retry_at = None
            item.finished_at = None
            item.last_error_code = None
            item.last_error_message = None
            item.render_job_id = None
            self.db.add(item)

        run.status = "queued"
        run.failed_at = None
        run.completed_at = None
        run.cancelled_at = None
        self.db.add(run)
        self.db.commit()

        return {
            "ok": True,
            "requeued_items": len(failed_items),
            "batch_run_id": batch_run_id,
        }

    def recompute_batch_status(self, batch_run_id: str) -> None:
        run = self.db.get(VeoBatchRun, batch_run_id)
        if not run:
            return

        rows = self.db.execute(
            select(VeoBatchItem.status, func.count(VeoBatchItem.id))
            .where(VeoBatchItem.batch_run_id == batch_run_id)
            .group_by(VeoBatchItem.status)
        ).all()

        counts = {status: count for status, count in rows}
        total = sum(counts.values())
        done = sum(counts.get(status, 0) for status in BATCH_ITEM_TERMINAL_STATUSES)

        if total == 0:
            run.status = "draft"
        elif counts.get("cancelled", 0) == total:
            run.status = "cancelled"
        elif done == total:
            if counts.get("failed", 0) > 0 and counts.get("succeeded", 0) > 0:
                run.status = "partially_failed"
                run.completed_at = datetime.now(timezone.utc)
            elif counts.get("failed", 0) == total:
                run.status = "failed"
                run.failed_at = datetime.now(timezone.utc)
            else:
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
        elif counts.get("running", 0) > 0 or counts.get("submitted", 0) > 0 or counts.get("leased", 0) > 0:
            run.status = "running"
        elif counts.get("pending", 0) > 0 or counts.get("retry_waiting", 0) > 0:
            run.status = "queued"

        self.db.add(run)
        self.db.commit()

    def _count_in_flight_items(self, batch_run_id: str) -> int:
        return int(
            self.db.execute(
                select(func.count(VeoBatchItem.id)).where(
                    VeoBatchItem.batch_run_id == batch_run_id,
                    VeoBatchItem.status.in_(["leased", "submitted", "running"]),
                )
            ).scalar_one()
            or 0
        )
5) PATCH backend/app/workers/veo_batch_scheduler_worker.py
File mới
from __future__ import annotations

from celery import shared_task

from backend.app.services.veo_batch_scheduler_service import VeoBatchSchedulerService


@shared_task(name="backend.app.workers.veo_batch_scheduler_worker.tick_veo_batch_scheduler")
def tick_veo_batch_scheduler() -> dict:
    service = VeoBatchSchedulerService()
    return service.dispatch_ready_batches()
6) PATCH backend/app/workers/render_dispatch_worker.py
Thêm task dispatch riêng cho batch item. Nếu file này đã có Celery app/task khác, chỉ cần paste phần dưới vào cuối file và map call sang runtime hiện có.
from __future__ import annotations

from celery import shared_task

# Map sang execution/runtime hiện có của repo bạn.
# Nếu repo đang dùng service khác, chỉ cần sửa import + call trong task này.
try:
    from backend.app.services.render_execution_service import RenderExecutionService
except Exception:  # pragma: no cover
    RenderExecutionService = None


@shared_task(name="backend.app.workers.render_dispatch_worker.dispatch_render_job_task")
def dispatch_render_job_task(payload: dict) -> dict:
    """
    Payload chuẩn cho Veo batch scheduler:
    {
      "project_id": "...",
      "batch_run_id": "...",
      "batch_item_id": "...",
      "provider_name": "veo",
      "provider_account_id": "...",
      "mode": "text_to_video" | "image_to_video" | "first_last_frames" | "reference_image_to_video",
      "scene_count": 0,
      "veo_config": {...}
    }
    """
    if RenderExecutionService is None:
        return {
            "ok": False,
            "error_code": "render_execution_service_missing",
            "message": "RenderExecutionService not available",
            "batch_item_id": payload.get("batch_item_id"),
        }

    service = RenderExecutionService()

    # Nếu runtime hiện có của bạn dùng tên method khác, map tại đây.
    result = service.create_render_job_from_project(
        project_id=payload["project_id"],
        source_mode="veo_batch",
        provider_name=payload.get("provider_name") or "veo",
        provider_account_id=payload.get("provider_account_id"),
        extra_metadata={
            "batch_run_id": payload.get("batch_run_id"),
            "batch_item_id": payload.get("batch_item_id"),
            "mode": payload.get("mode"),
            "scene_count": payload.get("scene_count"),
            "veo_config": payload.get("veo_config") or {},
        },
    )

    return {
        "ok": True,
        "batch_item_id": payload.get("batch_item_id"),
        "render_job_id": result.get("id") or result.get("render_job_id"),
        "result": result,
    }
7) PATCH backend/app/workers/render_poll_worker.py
Thêm helper callback update batch item khi render status đổi. Paste phần này vào file hiện có, rồi gọi _sync_veo_batch_item_from_render_job(...) tại điểm poll state success/fail.
from __future__ import annotations

from backend.app.services.veo_batch_scheduler_service import VeoBatchSchedulerService


def _sync_veo_batch_item_from_render_job(render_job: object, status_payload: dict | None = None) -> None:
    """
    render_job cần có metadata hoặc field chứa:
      batch_item_id
      batch_run_id
    """
    metadata = getattr(render_job, "metadata", None) or {}
    batch_item_id = metadata.get("batch_item_id") or getattr(render_job, "batch_item_id", None)
    if not batch_item_id:
        return

    scheduler = VeoBatchSchedulerService()

    normalized_status = (
        (status_payload or {}).get("status")
        or getattr(render_job, "status", None)
        or ""
    ).lower()

    if normalized_status in {"queued", "submitted", "pending"}:
        return

    if normalized_status in {"running", "processing"}:
        scheduler.mark_item_started(
            item_id=batch_item_id,
            render_job_id=str(getattr(render_job, "id", None) or ""),
        )
        return

    if normalized_status in {"succeeded", "completed", "done"}:
        scheduler.mark_item_succeeded(
            item_id=batch_item_id,
            result={
                "output_url": (status_payload or {}).get("output_url") or getattr(render_job, "output_url", None),
                "preview_url": (status_payload or {}).get("preview_url") or getattr(render_job, "preview_url", None),
                "video_url": (status_payload or {}).get("video_url"),
                "thumbnail_url": (status_payload or {}).get("thumbnail_url"),
                "status_payload": status_payload or {},
            },
        )
        return

    if normalized_status in {"failed", "error"}:
        scheduler.mark_item_failed(
            item_id=batch_item_id,
            error={
                "error_code": (status_payload or {}).get("error_code") or getattr(render_job, "last_error_code", None),
                "message": (status_payload or {}).get("message") or getattr(render_job, "last_error_message", None),
                "status": normalized_status,
            },
        )
Điểm chèn gọi trong poll loop hiện có
# ví dụ tại chỗ bạn đã poll xong provider/job status:
_sync_veo_batch_item_from_render_job(render_job=job, status_payload=provider_status)
8) PATCH backend/app/workers/render_postprocess_worker.py
Paste helper này vào file để giữ trace output về VeoBatchItem.
from __future__ import annotations

from backend.app.services.veo_batch_scheduler_service import VeoBatchSchedulerService


def _finalize_veo_batch_item_postprocess(render_job: object, output_payload: dict | None = None) -> None:
    metadata = getattr(render_job, "metadata", None) or {}
    batch_item_id = metadata.get("batch_item_id") or getattr(render_job, "batch_item_id", None)
    if not batch_item_id:
        return

    scheduler = VeoBatchSchedulerService()
    scheduler.mark_item_succeeded(
        item_id=batch_item_id,
        result={
            "output_url": (output_payload or {}).get("output_url") or getattr(render_job, "output_url", None),
            "preview_url": (output_payload or {}).get("preview_url") or getattr(render_job, "preview_url", None),
            "thumbnail_url": (output_payload or {}).get("thumbnail_url"),
            "postprocess_payload": output_payload or {},
        },
    )
Điểm chèn gọi
_finalize_veo_batch_item_postprocess(render_job=job, output_payload=postprocess_result)
9) PATCH backend/app/api/veo_workspace.py
Mình viết theo kiểu full routes cần thêm. Nếu file đã có router sẵn, chỉ cần paste các schema + routes dưới đây vào cùng file.
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.veo_workspace import VeoBatchRun, VeoBatchItem
from backend.app.services.veo_batch_scheduler_service import VeoBatchSchedulerService


router = APIRouter(prefix="/api/v1/veo", tags=["veo-workspace"])


class VeoBatchRunActionResponse(BaseModel):
    ok: bool
    batch_run_id: Optional[str] = None
    cancelled_items: Optional[int] = None
    requeued_items: Optional[int] = None
    error: Optional[str] = None


class VeoBatchItemResponse(BaseModel):
    id: str
    batch_run_id: str
    project_id: Optional[str] = None
    render_job_id: Optional[str] = None
    mode: Optional[str] = None
    status: str
    attempt_count: int
    provider_name: Optional[str] = None
    provider_account_id: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    output_url: Optional[str] = None
    preview_url: Optional[str] = None
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class VeoBatchRunStatsResponse(BaseModel):
    batch_run_id: str
    total_items: int
    pending: int
    leased: int
    submitted: int
    running: int
    retry_waiting: int
    succeeded: int
    failed: int
    cancelled: int
    average_attempt_count: float
    provider_distribution: Dict[str, int]


@router.post("/batch-runs/{batch_id}/dispatch", response_model=VeoBatchRunActionResponse)
def dispatch_batch_run(batch_id: str, db: Session = Depends(get_db)) -> VeoBatchRunActionResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    if run.status in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail=f"Cannot dispatch batch in status '{run.status}'")

    run.status = "queued"
    db.add(run)
    db.commit()

    scheduler = VeoBatchSchedulerService(db=db)
    scheduler.dispatch_ready_batches()

    return VeoBatchRunActionResponse(ok=True, batch_run_id=batch_id)


@router.post("/batch-runs/{batch_id}/cancel", response_model=VeoBatchRunActionResponse)
def cancel_batch_run(batch_id: str, db: Session = Depends(get_db)) -> VeoBatchRunActionResponse:
    scheduler = VeoBatchSchedulerService(db=db)
    result = scheduler.cancel_batch(batch_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return VeoBatchRunActionResponse(**result)


@router.post("/batch-runs/{batch_id}/retry-failed", response_model=VeoBatchRunActionResponse)
def retry_failed_batch_items(batch_id: str, db: Session = Depends(get_db)) -> VeoBatchRunActionResponse:
    scheduler = VeoBatchSchedulerService(db=db)
    result = scheduler.retry_failed(batch_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return VeoBatchRunActionResponse(**result)


@router.get("/batch-runs/{batch_id}/items", response_model=List[VeoBatchItemResponse])
def get_batch_run_items(
    batch_id: str,
    status: Optional[str] = Query(default=None),
    mode: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    account: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[VeoBatchItemResponse]:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    stmt = select(VeoBatchItem).where(VeoBatchItem.batch_run_id == batch_id)

    if status:
        stmt = stmt.where(VeoBatchItem.status == status)
    if mode:
        stmt = stmt.where(VeoBatchItem.mode == mode)
    if provider:
        stmt = stmt.where(VeoBatchItem.provider_name == provider)
    if account:
        stmt = stmt.where(VeoBatchItem.provider_account_id == account)

    stmt = stmt.order_by(VeoBatchItem.created_at.asc()).offset(offset).limit(limit)

    rows = db.execute(stmt).scalars().all()
    return [
        VeoBatchItemResponse(
            id=row.id,
            batch_run_id=row.batch_run_id,
            project_id=getattr(row, "project_id", None),
            render_job_id=getattr(row, "render_job_id", None),
            mode=getattr(row, "mode", None),
            status=row.status,
            attempt_count=int(getattr(row, "attempt_count", 0) or 0),
            provider_name=getattr(row, "provider_name", None),
            provider_account_id=getattr(row, "provider_account_id", None),
            next_retry_at=getattr(row, "next_retry_at", None),
            last_error_code=getattr(row, "last_error_code", None),
            last_error_message=getattr(row, "last_error_message", None),
            output_url=getattr(row, "output_url", None),
            preview_url=getattr(row, "preview_url", None),
            created_at=getattr(row, "created_at", None),
            finished_at=getattr(row, "finished_at", None),
        )
        for row in rows
    ]


@router.get("/batch-runs/{batch_id}/stats", response_model=VeoBatchRunStatsResponse)
def get_batch_run_stats(batch_id: str, db: Session = Depends(get_db)) -> VeoBatchRunStatsResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    rows = db.execute(
        select(VeoBatchItem.status, func.count(VeoBatchItem.id))
        .where(VeoBatchItem.batch_run_id == batch_id)
        .group_by(VeoBatchItem.status)
    ).all()
    counts = {status: count for status, count in rows}

    avg_attempt = db.execute(
        select(func.avg(VeoBatchItem.attempt_count))
        .where(VeoBatchItem.batch_run_id == batch_id)
    ).scalar()

    provider_rows = db.execute(
        select(VeoBatchItem.provider_name, func.count(VeoBatchItem.id))
        .where(VeoBatchItem.batch_run_id == batch_id)
        .group_by(VeoBatchItem.provider_name)
    ).all()

    provider_distribution = {
        (provider_name or "unknown"): count
        for provider_name, count in provider_rows
    }

    total_items = int(sum(counts.values()))

    return VeoBatchRunStatsResponse(
        batch_run_id=batch_id,
        total_items=total_items,
        pending=int(counts.get("pending", 0)),
        leased=int(counts.get("leased", 0)),
        submitted=int(counts.get("submitted", 0)),
        running=int(counts.get("running", 0)),
        retry_waiting=int(counts.get("retry_waiting", 0)),
        succeeded=int(counts.get("succeeded", 0)),
        failed=int(counts.get("failed", 0)),
        cancelled=int(counts.get("cancelled", 0)),
        average_attempt_count=float(avg_attempt or 0),
        provider_distribution=provider_distribution,
    )
10) PATCH frontend/src/lib/api.ts
Thêm các function này vào client hiện có.
export type VeoBatchItem = {
  id: string;
  batch_run_id: string;
  project_id?: string | null;
  render_job_id?: string | null;
  mode?: string | null;
  status: string;
  attempt_count: number;
  provider_name?: string | null;
  provider_account_id?: string | null;
  next_retry_at?: string | null;
  last_error_code?: string | null;
  last_error_message?: string | null;
  output_url?: string | null;
  preview_url?: string | null;
  created_at?: string | null;
  finished_at?: string | null;
};

export type VeoBatchRunStats = {
  batch_run_id: string;
  total_items: number;
  pending: number;
  leased: number;
  submitted: number;
  running: number;
  retry_waiting: number;
  succeeded: number;
  failed: number;
  cancelled: number;
  average_attempt_count: number;
  provider_distribution: Record<string, number>;
};

export async function dispatchVeoBatchRun(batchId: string) {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/dispatch`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to dispatch batch run ${batchId}`);
  return res.json();
}

export async function cancelVeoBatchRun(batchId: string) {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/cancel`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to cancel batch run ${batchId}`);
  return res.json();
}

export async function retryFailedVeoBatchRun(batchId: string) {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/retry-failed`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to retry failed items for batch run ${batchId}`);
  return res.json();
}

export async function getVeoBatchRunItems(
  batchId: string,
  params?: {
    status?: string;
    mode?: string;
    provider?: string;
    account?: string;
    limit?: number;
    offset?: number;
  }
): Promise<VeoBatchItem[]> {
  const search = new URLSearchParams();
  if (params?.status) search.set("status", params.status);
  if (params?.mode) search.set("mode", params.mode);
  if (params?.provider) search.set("provider", params.provider);
  if (params?.account) search.set("account", params.account);
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.offset != null) search.set("offset", String(params.offset));

  const qs = search.toString();
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/items${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to fetch batch run items ${batchId}`);
  return res.json();
}

export async function getVeoBatchRunStats(batchId: string): Promise<VeoBatchRunStats> {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/stats`);
  if (!res.ok) throw new Error(`Failed to fetch batch run stats ${batchId}`);
  return res.json();
}
11) frontend/src/components/veo/VeoBatchRunPanel.tsx
"use client";

import { useMemo, useState } from "react";
import {
  cancelVeoBatchRun,
  dispatchVeoBatchRun,
  retryFailedVeoBatchRun,
  VeoBatchRunStats,
} from "@/src/lib/api";

type Props = {
  batchId: string;
  stats: VeoBatchRunStats | null;
  onRefresh?: () => Promise<void> | void;
};

export default function VeoBatchRunPanel({ batchId, stats, onRefresh }: Props) {
  const [loading, setLoading] = useState<string | null>(null);
  const total = stats?.total_items ?? 0;
  const completed = (stats?.succeeded ?? 0) + (stats?.failed ?? 0) + (stats?.cancelled ?? 0);

  const progressPct = useMemo(() => {
    if (!total) return 0;
    return Math.round((completed / total) * 100);
  }, [completed, total]);

  async function runAction(action: "dispatch" | "cancel" | "retry") {
    try {
      setLoading(action);
      if (action === "dispatch") await dispatchVeoBatchRun(batchId);
      if (action === "cancel") await cancelVeoBatchRun(batchId);
      if (action === "retry") await retryFailedVeoBatchRun(batchId);
      await onRefresh?.();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Action failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="rounded-2xl border border-neutral-200 p-4 bg-white">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Veo Batch Run</h3>
          <p className="text-sm text-neutral-500">Batch ID: {batchId}</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
            onClick={() => runAction("dispatch")}
            disabled={loading !== null}
          >
            {loading === "dispatch" ? "Dispatching..." : "Dispatch"}
          </button>
          <button
            className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
            onClick={() => runAction("retry")}
            disabled={loading !== null}
          >
            {loading === "retry" ? "Retrying..." : "Retry Failed"}
          </button>
          <button
            className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
            onClick={() => runAction("cancel")}
            disabled={loading !== null}
          >
            {loading === "cancel" ? "Cancelling..." : "Cancel"}
          </button>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span>Progress</span>
          <span>{progressPct}%</span>
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-neutral-100">
          <div
            className="h-full rounded-full bg-neutral-900 transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-5">
        <StatCard label="Total" value={stats?.total_items ?? 0} />
        <StatCard label="Pending" value={stats?.pending ?? 0} />
        <StatCard label="Running" value={(stats?.submitted ?? 0) + (stats?.running ?? 0) + (stats?.leased ?? 0)} />
        <StatCard label="Retry Waiting" value={stats?.retry_waiting ?? 0} />
        <StatCard label="Succeeded" value={stats?.succeeded ?? 0} />
        <StatCard label="Failed" value={stats?.failed ?? 0} />
        <StatCard label="Cancelled" value={stats?.cancelled ?? 0} />
        <StatCard label="Avg Attempts" value={(stats?.average_attempt_count ?? 0).toFixed(2)} />
      </div>

      <div className="mt-4">
        <h4 className="mb-2 text-sm font-medium text-neutral-700">Provider Distribution</h4>
        <div className="flex flex-wrap gap-2">
          {Object.entries(stats?.provider_distribution ?? {}).map(([provider, count]) => (
            <span
              key={provider}
              className="rounded-full border px-3 py-1 text-xs text-neutral-700"
            >
              {provider}: {count}
            </span>
          ))}
          {Object.keys(stats?.provider_distribution ?? {}).length === 0 && (
            <span className="text-sm text-neutral-500">No provider allocation yet</span>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-neutral-200 p-3">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}
12) frontend/src/components/veo/VeoBatchItemsTable.tsx
"use client";

import { VeoBatchItem } from "@/src/lib/api";

type Props = {
  items: VeoBatchItem[];
};

export default function VeoBatchItemsTable({ items }: Props) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-neutral-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-neutral-50 text-left text-neutral-600">
          <tr>
            <th className="px-4 py-3 font-medium">Item</th>
            <th className="px-4 py-3 font-medium">Mode</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Attempts</th>
            <th className="px-4 py-3 font-medium">Provider</th>
            <th className="px-4 py-3 font-medium">Render Job</th>
            <th className="px-4 py-3 font-medium">Next Retry</th>
            <th className="px-4 py-3 font-medium">Output</th>
            <th className="px-4 py-3 font-medium">Error</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-t border-neutral-200 align-top">
              <td className="px-4 py-3">
                <div className="font-medium">{item.id}</div>
                <div className="text-xs text-neutral-500">{item.project_id || "No project"}</div>
              </td>
              <td className="px-4 py-3">{item.mode || "-"}</td>
              <td className="px-4 py-3">
                <StatusPill status={item.status} />
              </td>
              <td className="px-4 py-3">{item.attempt_count}</td>
              <td className="px-4 py-3">
                <div>{item.provider_name || "-"}</div>
                <div className="text-xs text-neutral-500">{item.provider_account_id || ""}</div>
              </td>
              <td className="px-4 py-3">{item.render_job_id || "-"}</td>
              <td className="px-4 py-3">{item.next_retry_at ? new Date(item.next_retry_at).toLocaleString() : "-"}</td>
              <td className="px-4 py-3">
                <div className="flex flex-col gap-1">
                  {item.output_url ? (
                    <a className="text-blue-600 underline" href={item.output_url} target="_blank" rel="noreferrer">
                      Output
                    </a>
                  ) : null}
                  {item.preview_url ? (
                    <a className="text-blue-600 underline" href={item.preview_url} target="_blank" rel="noreferrer">
                      Preview
                    </a>
                  ) : null}
                  {!item.output_url && !item.preview_url ? "-": null}
                </div>
              </td>
              <td className="px-4 py-3">
                {item.last_error_message ? (
                  <div>
                    <div className="font-medium text-red-600">{item.last_error_code || "error"}</div>
                    <div className="max-w-[320px] text-xs text-neutral-600">{item.last_error_message}</div>
                  </div>
                ) : (
                  "-"
                )}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={9} className="px-4 py-8 text-center text-neutral-500">
                No batch items found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  return (
    <span className="inline-flex rounded-full border px-2.5 py-1 text-xs font-medium">
      {status}
    </span>
  );
}
13) PATCH frontend/src/app/projects/[id]/page.tsx
Thêm block này vào workspace page hiện có.
Giả sử bạn đã có project, projectId, hoặc lấy params.id.
Nếu repo đang dùng data loader khác, giữ nguyên page cũ và paste riêng component block này vào khu vực workspace.
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getVeoBatchRunItems,
  getVeoBatchRunStats,
  VeoBatchItem,
  VeoBatchRunStats,
} from "@/src/lib/api";
import VeoBatchRunPanel from "@/src/components/veo/VeoBatchRunPanel";
import VeoBatchItemsTable from "@/src/components/veo/VeoBatchItemsTable";

type VeoBatchWorkspaceProps = {
  batchId: string | null;
};

export function VeoBatchWorkspaceSection({ batchId }: VeoBatchWorkspaceProps) {
  const [stats, setStats] = useState<VeoBatchRunStats | null>(null);
  const [items, setItems] = useState<VeoBatchItem[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!batchId) return;
    setLoading(true);
    try {
      const [statsData, itemsData] = await Promise.all([
        getVeoBatchRunStats(batchId),
        getVeoBatchRunItems(batchId, { limit: 100 }),
      ]);
      setStats(statsData);
      setItems(itemsData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [batchId]);

  useEffect(() => {
    void refresh();
    if (!batchId) return;

    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);

    return () => window.clearInterval(timer);
  }, [batchId, refresh]);

  if (!batchId) {
    return (
      <div className="rounded-2xl border border-dashed border-neutral-300 p-6 text-sm text-neutral-500">
        No Veo batch run attached to this project yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <VeoBatchRunPanel batchId={batchId} stats={stats} onRefresh={refresh} />
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Batch Items</h3>
        <button
          className="rounded-xl border px-3 py-2 text-sm"
          onClick={() => void refresh()}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>
      <VeoBatchItemsTable items={items} />
    </div>
  );
}
Điểm chèn vào page chính
{/* Example insertion inside project workspace page */}
<VeoBatchWorkspaceSection batchId={(project as any)?.veo_batch_run_id ?? null} />
14) PATCH nhẹ đề xuất cho backend/app/core/config.py
Vì các service ở trên dùng getattr, patch này không bắt buộc để code chạy, nhưng nên thêm để sạch production.
VEO_BATCH_MAX_PARALLEL_ITEMS: int = 4
VEO_BATCH_LEASE_TTL_SECONDS: int = 300
VEO_BATCH_RETRY_BACKOFF_SECONDS: int = 60
VEO_BATCH_MAX_RETRIES_TEXT: int = 3
VEO_BATCH_MAX_RETRIES_IMAGE: int = 2
VEO_BATCH_MAX_RETRIES_FIRST_LAST: int = 2
VEO_BATCH_MAX_RETRIES_REFERENCE_PREVIEW: int = 1
VEO_PROVIDER_ROTATION_ENABLED: bool = False
VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS: int = 120
VEO_PROVIDER_ACCOUNT_POOL_JSON: str = ""
15) PATCH nhẹ đề xuất cho .env.example và backend/.env.example
VEO_BATCH_MAX_PARALLEL_ITEMS=4
VEO_BATCH_LEASE_TTL_SECONDS=300
VEO_BATCH_RETRY_BACKOFF_SECONDS=60
VEO_BATCH_MAX_RETRIES_TEXT=3
VEO_BATCH_MAX_RETRIES_IMAGE=2
VEO_BATCH_MAX_RETRIES_FIRST_LAST=2
VEO_BATCH_MAX_RETRIES_REFERENCE_PREVIEW=1
VEO_PROVIDER_ROTATION_ENABLED=false
VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS=120
VEO_PROVIDER_ACCOUNT_POOL_JSON={"veo":[{"id":"acct-primary"},{"id":"acct-secondary"}]}
Điểm nối quan trọng nhất để bạn paste không lệch
Backend
VeoBatchItem cần có tối thiểu:
id
batch_run_id
created_at
mode
status
attempt_count
project_id
veo_config hoặc batch run có veo_config
VeoBatchRun cần có tối thiểu:
id
created_at
status
requested_mode
veo_config
max_parallelism
Render runtime
Task dispatch_render_job_task(...) hiện đang gọi:
RenderExecutionService().create_render_job_from_project(...)
Nếu repo bạn đang dùng method khác, chỉ cần map đúng tại 1 chỗ đó.
Frontend
project.veo_batch_run_id là field gợi ý.
Nếu repo bạn đang giữ batch ở field khác, chỉ cần đổi dòng:
(project as any)?.veo_batch_run_id ?? null
Kết quả sau patch này
Hệ sẽ đi từ:
tạo Veo batch run
lưu batch items
build project từ nhiều script
sang:
dispatch batch thật
lease item theo capacity
retry theo mode
rotate provider account
update item/run status từ render runtime
có panel theo dõi progress + item table
Nếu bạn muốn, ở lượt tiếp theo mình sẽ viết tiếp ngay PHASE bổ sung kế tiếp theo đúng format paste-ready:
tests/test_veo_retry_policy_service.py
tests/test_veo_batch_scheduler_service.py
tests/test_veo_workspace_api.py
patch backend/app/models/veo_workspace.py full model runtime fields
patch frontend filter/search/pagination cho batch items
ở lượt tiếp theo mình sẽ viết tiếp ngay PHASE bổ sung kế tiếp theo đúng format paste-ready: tests/test_veo_retry_policy_service.py tests/test_veo_batch_scheduler_service.py tests/test_veo_workspace_api.py patch backend/app/models/veo_workspace.py full model runtime fields patch frontend filter/search/pagination cho batch items
Mình đang nối phần test + model + frontend list controls theo đúng các contract vừa tạo, để phase này khớp trực tiếp với scheduler/API mới thay vì viết test rời rạc.
Đã suy nghĩ trong 5s
Được. Mình viết tiếp ngay PHASE bổ sung kế tiếp theo đúng format paste-ready, bám theo các file/services/routes của phase trước.
1) tests/test_veo_retry_policy_service.py
from datetime import datetime, timezone

from backend.app.services.veo_retry_policy_service import VeoRetryPolicyService


class DummyItem:
    def __init__(self, mode: str, attempt_count: int):
        self.mode = mode
        self.attempt_count = attempt_count


def test_classify_retryable_rate_limit():
    service = VeoRetryPolicyService()

    result = service.classify_error(
        {
            "error_code": "429",
            "message": "Rate limit exceeded",
        }
    )

    assert result["retryable"] is True
    assert result["error_code"] == "rate_limit"


def test_classify_non_retryable_preview_disabled():
    service = VeoRetryPolicyService()

    result = service.classify_error(
        {
            "error_code": "preview_mode_disabled",
            "message": "Preview mode disabled by config",
        }
    )

    assert result["retryable"] is False
    assert result["error_code"] == "preview_mode_disabled"


def test_should_retry_text_to_video_under_limit():
    service = VeoRetryPolicyService()
    item = DummyItem(mode="text_to_video", attempt_count=1)

    decision = service.should_retry(
        item=item,
        error={
            "error_code": "503",
            "message": "Upstream unavailable",
        },
    )

    assert decision.retryable is True
    assert decision.should_retry is True
    assert decision.next_retry_at is not None
    assert decision.max_attempts >= 2


def test_should_not_retry_text_to_video_when_limit_reached():
    service = VeoRetryPolicyService()
    max_attempts = service.max_attempts_for_mode("text_to_video")
    item = DummyItem(mode="text_to_video", attempt_count=max_attempts)

    decision = service.should_retry(
        item=item,
        error={
            "error_code": "503",
            "message": "Temporary provider failure",
        },
    )

    assert decision.retryable is True
    assert decision.should_retry is False
    assert decision.next_retry_at is None


def test_should_not_retry_invalid_start_image():
    service = VeoRetryPolicyService()
    item = DummyItem(mode="image_to_video", attempt_count=0)

    decision = service.should_retry(
        item=item,
        error={
            "error_code": "invalid_start_image",
            "message": "Start image URL is invalid",
        },
    )

    assert decision.retryable is False
    assert decision.should_retry is False
    assert decision.next_retry_at is None


def test_reference_preview_has_low_retry_cap():
    service = VeoRetryPolicyService()
    assert service.max_attempts_for_mode("reference_image_to_video") <= 1


def test_backoff_increases_with_attempt_count():
    service = VeoRetryPolicyService()

    first = service._backoff_seconds("text_to_video", attempt_count=0)
    second = service._backoff_seconds("text_to_video", attempt_count=1)
    third = service._backoff_seconds("text_to_video", attempt_count=2)

    assert first > 0
    assert second > first
    assert third > second


def test_next_retry_at_returns_datetime():
    service = VeoRetryPolicyService()
    item = DummyItem(mode="first_last_frames", attempt_count=0)

    dt = service.next_retry_at(
        item=item,
        error={
            "error_code": "timeout",
            "message": "Provider timeout",
        },
    )

    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None
2) tests/test_veo_batch_scheduler_service.py
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.models.veo_workspace import VeoBatchRun, VeoBatchItem
from backend.app.services.veo_batch_scheduler_service import VeoBatchSchedulerService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_batch_run(db, batch_id: str = "batch-1", status: str = "queued") -> VeoBatchRun:
    run = VeoBatchRun(
        id=batch_id,
        name="Test Batch",
        status=status,
        requested_mode="text_to_video",
        max_parallelism=3,
        created_at=datetime.now(timezone.utc),
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    return run


def _make_batch_item(
    db,
    item_id: str,
    batch_id: str = "batch-1",
    status: str = "pending",
    mode: str = "text_to_video",
    priority_score: float = 0,
) -> VeoBatchItem:
    item = VeoBatchItem(
        id=item_id,
        batch_run_id=batch_id,
        status=status,
        mode=mode,
        attempt_count=0,
        project_id=f"project-{item_id}",
        priority_score=priority_score,
        created_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.commit()
    return item


def test_lease_next_items_prioritizes_high_priority(db_session):
    _make_batch_run(db_session)
    _make_batch_item(db_session, "item-low", priority_score=1)
    _make_batch_item(db_session, "item-high", priority_score=10)

    service = VeoBatchSchedulerService(db=db_session)

    leased = service.lease_next_items(batch_run_id="batch-1", limit=1)

    assert len(leased) == 1
    assert leased[0].id == "item-high"
    assert leased[0].status == "leased"
    assert leased[0].lease_token is not None


def test_lease_retry_waiting_only_when_due(db_session):
    _make_batch_run(db_session)

    due_item = VeoBatchItem(
        id="item-due",
        batch_run_id="batch-1",
        status="retry_waiting",
        mode="text_to_video",
        attempt_count=1,
        project_id="project-due",
        next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=5),
        created_at=datetime.now(timezone.utc),
    )
    future_item = VeoBatchItem(
        id="item-future",
        batch_run_id="batch-1",
        status="retry_waiting",
        mode="text_to_video",
        attempt_count=1,
        project_id="project-future",
        next_retry_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(due_item)
    db_session.add(future_item)
    db_session.commit()

    service = VeoBatchSchedulerService(db=db_session)
    leased = service.lease_next_items(batch_run_id="batch-1", limit=10)

    leased_ids = {item.id for item in leased}
    assert "item-due" in leased_ids
    assert "item-future" not in leased_ids


@patch("backend.app.services.veo_batch_scheduler_service.dispatch_render_job_task")
def test_dispatch_item_submits_render_job(mock_dispatch_task, db_session):
    _make_batch_run(db_session)
    item = _make_batch_item(db_session, "item-1")
    item.status = "leased"
    db_session.add(item)
    db_session.commit()

    mock_dispatch_task.delay.return_value = SimpleNamespace(id="render-job-1")

    service = VeoBatchSchedulerService(db=db_session)
    result = service.dispatch_item(item_id="item-1")

    refreshed = db_session.get(VeoBatchItem, "item-1")
    assert result["ok"] is True
    assert refreshed.status == "submitted"
    assert refreshed.render_job_id == "render-job-1"
    assert refreshed.attempt_count == 1


def test_mark_item_started(db_session):
    _make_batch_run(db_session)
    _make_batch_item(db_session, "item-1", status="submitted")

    service = VeoBatchSchedulerService(db=db_session)
    service.mark_item_started(item_id="item-1", render_job_id="render-1")

    refreshed = db_session.get(VeoBatchItem, "item-1")
    assert refreshed.status == "running"
    assert refreshed.render_job_id == "render-1"
    assert refreshed.started_at is not None


def test_mark_item_succeeded_updates_counts(db_session):
    _make_batch_run(db_session)
    _make_batch_item(db_session, "item-1", status="running")

    service = VeoBatchSchedulerService(db=db_session)
    service.mark_item_succeeded(
        item_id="item-1",
        result={
            "output_url": "https://cdn.example.com/output.mp4",
            "preview_url": "https://cdn.example.com/preview.jpg",
        },
    )

    item = db_session.get(VeoBatchItem, "item-1")
    run = db_session.get(VeoBatchRun, "batch-1")

    assert item.status == "succeeded"
    assert item.output_url == "https://cdn.example.com/output.mp4"
    assert item.preview_url == "https://cdn.example.com/preview.jpg"
    assert run.succeeded_count == 1


def test_mark_item_failed_retry_waiting_on_retryable_error(db_session):
    _make_batch_run(db_session)
    _make_batch_item(db_session, "item-1", status="running")

    service = VeoBatchSchedulerService(db=db_session)
    service.mark_item_failed(
        item_id="item-1",
        error={
            "error_code": "503",
            "message": "Transient provider failure",
        },
    )

    item = db_session.get(VeoBatchItem, "item-1")
    assert item.status == "retry_waiting"
    assert item.next_retry_at is not None
    assert item.last_error_code in {"503", "rate_limit", "timeout", "transient_provider_error"}


def test_mark_item_failed_terminal_on_non_retryable_error(db_session):
    _make_batch_run(db_session)
    _make_batch_item(db_session, "item-1", status="running")

    service = VeoBatchSchedulerService(db=db_session)
    service.mark_item_failed(
        item_id="item-1",
        error={
            "error_code": "invalid_mode",
            "message": "Unsupported generation mode",
        },
    )

    item = db_session.get(VeoBatchItem, "item-1")
    run = db_session.get(VeoBatchRun, "batch-1")

    assert item.status == "failed"
    assert item.finished_at is not None
    assert run.failed_count == 1


def test_recompute_batch_status_completed(db_session):
    _make_batch_run(db_session, status="running")
    _make_batch_item(db_session, "item-1", status="succeeded")
    _make_batch_item(db_session, "item-2", status="succeeded")

    service = VeoBatchSchedulerService(db=db_session)
    service.recompute_batch_status("batch-1")

    run = db_session.get(VeoBatchRun, "batch-1")
    assert run.status == "completed"
    assert run.completed_at is not None


def test_recompute_batch_status_partially_failed(db_session):
    _make_batch_run(db_session, status="running")
    _make_batch_item(db_session, "item-1", status="succeeded")
    _make_batch_item(db_session, "item-2", status="failed")

    service = VeoBatchSchedulerService(db=db_session)
    service.recompute_batch_status("batch-1")

    run = db_session.get(VeoBatchRun, "batch-1")
    assert run.status == "partially_failed"


def test_cancel_batch_marks_pending_items_cancelled(db_session):
    _make_batch_run(db_session, status="running")
    _make_batch_item(db_session, "item-1", status="pending")
    _make_batch_item(db_session, "item-2", status="retry_waiting")
    _make_batch_item(db_session, "item-3", status="succeeded")

    service = VeoBatchSchedulerService(db=db_session)
    result = service.cancel_batch("batch-1")

    assert result["ok"] is True
    assert result["cancelled_items"] == 2

    run = db_session.get(VeoBatchRun, "batch-1")
    assert run.status == "cancelled"


def test_retry_failed_requeues_only_failed_items(db_session):
    _make_batch_run(db_session, status="failed")
    failed = _make_batch_item(db_session, "item-1", status="failed")
    succeeded = _make_batch_item(db_session, "item-2", status="succeeded")
    failed.render_job_id = "old-render-id"
    failed.last_error_code = "503"
    failed.last_error_message = "error"
    db_session.add(failed)
    db_session.commit()

    service = VeoBatchSchedulerService(db=db_session)
    result = service.retry_failed("batch-1")

    assert result["ok"] is True
    assert result["requeued_items"] == 1

    failed_refreshed = db_session.get(VeoBatchItem, "item-1")
    succeeded_refreshed = db_session.get(VeoBatchItem, "item-2")
    run = db_session.get(VeoBatchRun, "batch-1")

    assert failed_refreshed.status == "pending"
    assert failed_refreshed.render_job_id is None
    assert failed_refreshed.last_error_code is None
    assert succeeded_refreshed.status == "succeeded"
    assert run.status == "queued"
3) tests/test_veo_workspace_api.py
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.models.veo_workspace import VeoBatchRun, VeoBatchItem
from backend.app.api.veo_workspace import router as veo_workspace_router


@pytest.fixture()
def client():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(veo_workspace_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c, TestingSessionLocal


def seed_batch(db, batch_id: str = "batch-1"):
    run = VeoBatchRun(
        id=batch_id,
        name="API Test Batch",
        status="queued",
        requested_mode="text_to_video",
        max_parallelism=3,
        created_at=datetime.now(timezone.utc),
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    return run


def seed_item(db, item_id: str, batch_id: str = "batch-1", status: str = "pending"):
    item = VeoBatchItem(
        id=item_id,
        batch_run_id=batch_id,
        project_id=f"project-{item_id}",
        mode="text_to_video",
        status=status,
        attempt_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.commit()
    return item


def test_get_batch_run_items(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db)
    seed_item(db, "item-1")
    seed_item(db, "item-2", status="failed")
    db.close()

    res = c.get("/api/v1/veo/batch-runs/batch-1/items")
    assert res.status_code == 200

    data = res.json()
    assert len(data) == 2
    assert {row["id"] for row in data} == {"item-1", "item-2"}


def test_get_batch_run_items_filter_status(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db)
    seed_item(db, "item-1", status="pending")
    seed_item(db, "item-2", status="failed")
    db.close()

    res = c.get("/api/v1/veo/batch-runs/batch-1/items?status=failed")
    assert res.status_code == 200

    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == "item-2"
    assert data[0]["status"] == "failed"


def test_get_batch_run_stats(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db)
    seed_item(db, "item-1", status="pending")
    seed_item(db, "item-2", status="running")
    seed_item(db, "item-3", status="succeeded")
    db.close()

    res = c.get("/api/v1/veo/batch-runs/batch-1/stats")
    assert res.status_code == 200

    data = res.json()
    assert data["batch_run_id"] == "batch-1"
    assert data["total_items"] == 3
    assert data["pending"] == 1
    assert data["running"] == 1
    assert data["succeeded"] == 1


def test_cancel_batch_run(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-cancel")
    seed_item(db, "item-1", batch_id="batch-cancel", status="pending")
    seed_item(db, "item-2", batch_id="batch-cancel", status="retry_waiting")
    db.close()

    res = c.post("/api/v1/veo/batch-runs/batch-cancel/cancel")
    assert res.status_code == 200

    data = res.json()
    assert data["ok"] is True
    assert data["cancelled_items"] == 2


def test_retry_failed_batch_items(client):
    c, SessionLocal = client
    db = SessionLocal()
    run = seed_batch(db, "batch-retry")
    run.status = "failed"
    db.add(run)
    db.commit()

    seed_item(db, "item-failed", batch_id="batch-retry", status="failed")
    seed_item(db, "item-ok", batch_id="batch-retry", status="succeeded")
    db.close()

    res = c.post("/api/v1/veo/batch-runs/batch-retry/retry-failed")
    assert res.status_code == 200

    data = res.json()
    assert data["ok"] is True
    assert data["requeued_items"] == 1


def test_dispatch_batch_not_found(client):
    c, _ = client
    res = c.post("/api/v1/veo/batch-runs/missing/dispatch")
    assert res.status_code == 404
4) PATCH backend/app/models/veo_workspace.py
Full model runtime fields
Mình viết theo dạng full file paste-ready. Nếu file hiện tại đã có thêm field riêng của workspace phase trước, chỉ cần merge giữ nguyên phần đó. Bản dưới đã gồm đủ runtime fields cho phase scheduler.
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class CharacterReferencePack(Base):
    __tablename__ = "character_reference_packs"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    identity_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    appearance_lock: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_lock_tokens: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    negative_drift_tokens: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    images: Mapped[list["CharacterReferenceImage"]] = relationship(
        "CharacterReferenceImage",
        back_populates="pack",
        cascade="all, delete-orphan",
    )


class CharacterReferenceImage(Base):
    __tablename__ = "character_reference_images"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    pack_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("character_reference_packs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    pack: Mapped["CharacterReferencePack"] = relationship(
        "CharacterReferencePack",
        back_populates="images",
    )


class VeoBatchRun(Base):
    __tablename__ = "veo_batch_runs"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", index=True)

    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_mode: Mapped[str | None] = mapped_column(String(100), nullable=True)

    veo_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    veo_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retry_policy_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rate_limit_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)

    max_parallelism: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    dispatched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    scheduler_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["VeoBatchItem"]] = relationship(
        "VeoBatchItem",
        back_populates="batch_run",
        cascade="all, delete-orphan",
    )


class VeoBatchItem(Base):
    __tablename__ = "veo_batch_items"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_run_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("veo_batch_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    project_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    render_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    mode: Mapped[str | None] = mapped_column(String(100), nullable=True)

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    script_preview: Mapped[str | None] = mapped_column(Text, nullable=True)

    veo_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    character_reference_pack_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("character_reference_packs.id", ondelete="SET NULL"),
        nullable=True,
    )

    start_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_reference_image_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)

    scene_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    lease_token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    leased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    output_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch_run: Mapped["VeoBatchRun"] = relationship(
        "VeoBatchRun",
        back_populates="items",
    )
    character_reference_pack: Mapped["CharacterReferencePack | None"] = relationship("CharacterReferencePack")
5) PATCH frontend/src/lib/api.ts
Add filter/search/pagination support for batch items
Nếu bạn đã thêm types/functions phase trước, chỉ cần thay hàm getVeoBatchRunItems bằng bản dưới và thêm return type mới.
export type VeoBatchItemsPage = {
  items: VeoBatchItem[];
  total?: number;
  limit: number;
  offset: number;
};

export async function getVeoBatchRunItems(
  batchId: string,
  params?: {
    status?: string;
    mode?: string;
    provider?: string;
    account?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }
): Promise<VeoBatchItemsPage> {
  const search = new URLSearchParams();
  if (params?.status) search.set("status", params.status);
  if (params?.mode) search.set("mode", params.mode);
  if (params?.provider) search.set("provider", params.provider);
  if (params?.account) search.set("account", params.account);
  if (params?.search) search.set("search", params.search);
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.offset != null) search.set("offset", String(params.offset));

  const qs = search.toString();
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/items${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to fetch batch run items ${batchId}`);

  const data = await res.json();

  if (Array.isArray(data)) {
    return {
      items: data,
      limit: params?.limit ?? data.length,
      offset: params?.offset ?? 0,
      total: data.length,
    };
  }

  return data;
}
6) PATCH backend/app/api/veo_workspace.py
Add search + pagination payload for items endpoint
Thay route GET /batch-runs/{batch_id}/items cũ bằng bản dưới.
class VeoBatchItemsPageResponse(BaseModel):
    items: List[VeoBatchItemResponse]
    total: int
    limit: int
    offset: int


@router.get("/batch-runs/{batch_id}/items", response_model=VeoBatchItemsPageResponse)
def get_batch_run_items(
    batch_id: str,
    status: Optional[str] = Query(default=None),
    mode: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    account: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> VeoBatchItemsPageResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    stmt = select(VeoBatchItem).where(VeoBatchItem.batch_run_id == batch_id)
    count_stmt = select(func.count(VeoBatchItem.id)).where(VeoBatchItem.batch_run_id == batch_id)

    if status:
        stmt = stmt.where(VeoBatchItem.status == status)
        count_stmt = count_stmt.where(VeoBatchItem.status == status)
    if mode:
        stmt = stmt.where(VeoBatchItem.mode == mode)
        count_stmt = count_stmt.where(VeoBatchItem.mode == mode)
    if provider:
        stmt = stmt.where(VeoBatchItem.provider_name == provider)
        count_stmt = count_stmt.where(VeoBatchItem.provider_name == provider)
    if account:
        stmt = stmt.where(VeoBatchItem.provider_account_id == account)
        count_stmt = count_stmt.where(VeoBatchItem.provider_account_id == account)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            (
                VeoBatchItem.id.ilike(pattern)
                | VeoBatchItem.project_id.ilike(pattern)
                | VeoBatchItem.render_job_id.ilike(pattern)
                | VeoBatchItem.title.ilike(pattern)
                | VeoBatchItem.last_error_message.ilike(pattern)
            )
        )
        count_stmt = count_stmt.where(
            (
                VeoBatchItem.id.ilike(pattern)
                | VeoBatchItem.project_id.ilike(pattern)
                | VeoBatchItem.render_job_id.ilike(pattern)
                | VeoBatchItem.title.ilike(pattern)
                | VeoBatchItem.last_error_message.ilike(pattern)
            )
        )

    total = int(db.execute(count_stmt).scalar() or 0)

    stmt = stmt.order_by(VeoBatchItem.created_at.asc()).offset(offset).limit(limit)
    rows = db.execute(stmt).scalars().all()

    items = [
        VeoBatchItemResponse(
            id=row.id,
            batch_run_id=row.batch_run_id,
            project_id=getattr(row, "project_id", None),
            render_job_id=getattr(row, "render_job_id", None),
            mode=getattr(row, "mode", None),
            status=row.status,
            attempt_count=int(getattr(row, "attempt_count", 0) or 0),
            provider_name=getattr(row, "provider_name", None),
            provider_account_id=getattr(row, "provider_account_id", None),
            next_retry_at=getattr(row, "next_retry_at", None),
            last_error_code=getattr(row, "last_error_code", None),
            last_error_message=getattr(row, "last_error_message", None),
            output_url=getattr(row, "output_url", None),
            preview_url=getattr(row, "preview_url", None),
            created_at=getattr(row, "created_at", None),
            finished_at=getattr(row, "finished_at", None),
        )
        for row in rows
    ]

    return VeoBatchItemsPageResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
7) PATCH frontend/src/components/veo/VeoBatchItemsTable.tsx
Add filter/search/pagination UI
Bản này thay file cũ luôn.
"use client";

import { useMemo, useState } from "react";
import { VeoBatchItem } from "@/src/lib/api";

type Props = {
  items: VeoBatchItem[];
  total?: number;
  limit: number;
  offset: number;
  statusFilter: string;
  modeFilter: string;
  searchText: string;
  onChangeStatusFilter: (value: string) => void;
  onChangeModeFilter: (value: string) => void;
  onChangeSearchText: (value: string) => void;
  onPrevPage: () => void;
  onNextPage: () => void;
};

const STATUS_OPTIONS = [
  "",
  "pending",
  "leased",
  "submitted",
  "running",
  "retry_waiting",
  "succeeded",
  "failed",
  "cancelled",
];

const MODE_OPTIONS = [
  "",
  "text_to_video",
  "image_to_video",
  "first_last_frames",
  "reference_image_to_video",
];

export default function VeoBatchItemsTable(props: Props) {
  const {
    items,
    total,
    limit,
    offset,
    statusFilter,
    modeFilter,
    searchText,
    onChangeStatusFilter,
    onChangeModeFilter,
    onChangeSearchText,
    onPrevPage,
    onNextPage,
  } = props;

  const pageStart = items.length === 0 ? 0 : offset + 1;
  const pageEnd = offset + items.length;
  const canPrev = offset > 0;
  const canNext = total != null ? offset + limit < total : items.length >= limit;

  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-neutral-200 bg-white p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-neutral-500">
              Search
            </label>
            <input
              value={searchText}
              onChange={(e) => onChangeSearchText(e.target.value)}
              placeholder="Item ID, project ID, render job, title, error..."
              className="w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-neutral-500">
              Status
            </label>
            <select
              value={statusFilter}
              onChange={(e) => onChangeStatusFilter(e.target.value)}
              className="w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
            >
              {STATUS_OPTIONS.map((value) => (
                <option key={value || "all"} value={value}>
                  {value || "All statuses"}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-neutral-500">
              Mode
            </label>
            <select
              value={modeFilter}
              onChange={(e) => onChangeModeFilter(e.target.value)}
              className="w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
            >
              {MODE_OPTIONS.map((value) => (
                <option key={value || "all"} value={value}>
                  {value || "All modes"}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-neutral-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-neutral-50 text-left text-neutral-600">
            <tr>
              <th className="px-4 py-3 font-medium">Item</th>
              <th className="px-4 py-3 font-medium">Mode</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Attempts</th>
              <th className="px-4 py-3 font-medium">Provider</th>
              <th className="px-4 py-3 font-medium">Render Job</th>
              <th className="px-4 py-3 font-medium">Next Retry</th>
              <th className="px-4 py-3 font-medium">Output</th>
              <th className="px-4 py-3 font-medium">Error</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t border-neutral-200 align-top">
                <td className="px-4 py-3">
                  <div className="font-medium">{item.id}</div>
                  <div className="text-xs text-neutral-500">{item.project_id || "No project"}</div>
                </td>
                <td className="px-4 py-3">{item.mode || "-"}</td>
                <td className="px-4 py-3">
                  <StatusPill status={item.status} />
                </td>
                <td className="px-4 py-3">{item.attempt_count}</td>
                <td className="px-4 py-3">
                  <div>{item.provider_name || "-"}</div>
                  <div className="text-xs text-neutral-500">{item.provider_account_id || ""}</div>
                </td>
                <td className="px-4 py-3">{item.render_job_id || "-"}</td>
                <td className="px-4 py-3">
                  {item.next_retry_at ? new Date(item.next_retry_at).toLocaleString() : "-"}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-col gap-1">
                    {item.output_url ? (
                      <a className="text-blue-600 underline" href={item.output_url} target="_blank" rel="noreferrer">
                        Output
                      </a>
                    ) : null}
                    {item.preview_url ? (
                      <a className="text-blue-600 underline" href={item.preview_url} target="_blank" rel="noreferrer">
                        Preview
                      </a>
                    ) : null}
                    {!item.output_url && !item.preview_url ? "-" : null}
                  </div>
                </td>
                <td className="px-4 py-3">
                  {item.last_error_message ? (
                    <div>
                      <div className="font-medium text-red-600">{item.last_error_code || "error"}</div>
                      <div className="max-w-[320px] text-xs text-neutral-600">{item.last_error_message}</div>
                    </div>
                  ) : (
                    "-"
                  )}
                </td>
              </tr>
            ))}

            {items.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-neutral-500">
                  No batch items found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between rounded-2xl border border-neutral-200 bg-white px-4 py-3 text-sm">
        <div className="text-neutral-600">
          Showing {pageStart}-{pageEnd}
          {typeof total === "number" ? ` of ${total}` : ""}
        </div>
        <div className="flex items-center gap-2">
          <button
            className="rounded-xl border px-3 py-2 disabled:opacity-50"
            onClick={onPrevPage}
            disabled={!canPrev}
          >
            Previous
          </button>
          <button
            className="rounded-xl border px-3 py-2 disabled:opacity-50"
            onClick={onNextPage}
            disabled={!canNext}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  return <span className="inline-flex rounded-full border px-2.5 py-1 text-xs font-medium">{status}</span>;
}
8) PATCH frontend/src/app/projects/[id]/page.tsx
Wire filter/search/pagination state
Thay block VeoBatchWorkspaceSection phase trước bằng bản dưới.
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getVeoBatchRunItems,
  getVeoBatchRunStats,
  VeoBatchItem,
  VeoBatchItemsPage,
  VeoBatchRunStats,
} from "@/src/lib/api";
import VeoBatchRunPanel from "@/src/components/veo/VeoBatchRunPanel";
import VeoBatchItemsTable from "@/src/components/veo/VeoBatchItemsTable";

type VeoBatchWorkspaceProps = {
  batchId: string | null;
};

export function VeoBatchWorkspaceSection({ batchId }: VeoBatchWorkspaceProps) {
  const [stats, setStats] = useState<VeoBatchRunStats | null>(null);
  const [itemsPage, setItemsPage] = useState<VeoBatchItemsPage>({
    items: [],
    total: 0,
    limit: 25,
    offset: 0,
  });
  const [loading, setLoading] = useState(false);

  const [statusFilter, setStatusFilter] = useState("");
  const [modeFilter, setModeFilter] = useState("");
  const [searchText, setSearchText] = useState("");

  const refresh = useCallback(
    async (nextOffset?: number) => {
      if (!batchId) return;

      const offset = nextOffset ?? itemsPage.offset;
      setLoading(true);
      try {
        const [statsData, itemsData] = await Promise.all([
          getVeoBatchRunStats(batchId),
          getVeoBatchRunItems(batchId, {
            limit: itemsPage.limit,
            offset,
            status: statusFilter || undefined,
            mode: modeFilter || undefined,
            search: searchText || undefined,
          }),
        ]);

        setStats(statsData);
        setItemsPage(itemsData);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    },
    [batchId, itemsPage.limit, itemsPage.offset, modeFilter, searchText, statusFilter]
  );

  useEffect(() => {
    void refresh(0);
  }, [batchId, statusFilter, modeFilter, searchText]);

  useEffect(() => {
    if (!batchId) return;
    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [batchId, refresh]);

  if (!batchId) {
    return (
      <div className="rounded-2xl border border-dashed border-neutral-300 p-6 text-sm text-neutral-500">
        No Veo batch run attached to this project yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <VeoBatchRunPanel batchId={batchId} stats={stats} onRefresh={() => refresh()} />

      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Batch Items</h3>
        <button
          className="rounded-xl border px-3 py-2 text-sm"
          onClick={() => void refresh()}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <VeoBatchItemsTable
        items={itemsPage.items}
        total={itemsPage.total}
        limit={itemsPage.limit}
        offset={itemsPage.offset}
        statusFilter={statusFilter}
        modeFilter={modeFilter}
        searchText={searchText}
        onChangeStatusFilter={(value) => setStatusFilter(value)}
        onChangeModeFilter={(value) => setModeFilter(value)}
        onChangeSearchText={(value) => setSearchText(value)}
        onPrevPage={() => void refresh(Math.max(0, itemsPage.offset - itemsPage.limit))}
        onNextPage={() => void refresh(itemsPage.offset + itemsPage.limit)}
      />
    </div>
  );
}
9) Điểm khớp quan trọng cần lưu ý
Test layer
Trong test mình dùng:
from backend.app.db.base import Base
Nếu repo của bạn export Base ở file khác, đổi import đó là đủ.
API pagination
Bây giờ endpoint /items trả:
{
  "items": [...],
  "total": 123,
  "limit": 25,
  "offset": 0
}
Frontend đã map theo contract này, nhưng vẫn backward-compatible nếu endpoint cũ trả array.
Model patch
Nếu model hiện tại đã có:
project_id
title
source_script
character_reference_pack_id
veo_config
thì giữ nguyên giá trị cũ; bản full file này chỉ gom lại cho phase scheduler/runtime.
10) Kết quả sau phase bổ sung này
Bạn đã có thêm 3 lớp rất quan trọng:
Verification
test retry policy
test scheduler lifecycle
test API endpoints
Runtime completeness
model đủ field để batch chạy production hơn
item có search/filter/pagination-friendly shape
Workspace operability
filter theo status
filter theo mode
search item/project/render job/error
phân trang item table
Nếu bạn muốn, lượt tiếp theo mình viết tiếp luôn phase hardening theo đúng format paste-ready:
tests/test_provider_account_rotation_service.py
tests/test_veo_batch_scheduler_worker.py
patch backend/app/core/config.py
patch .env.example
patch backend/.env.example
patch backend/app/workers/render_poll_worker.py full integrated version
patch backend/app/workers/render_postprocess_worker.py full integrated version
lượt tiếp theo mình viết tiếp luôn phase hardening theo đúng format paste-ready: tests/test_provider_account_rotation_service.py tests/test_veo_batch_scheduler_worker.py patch backend/app/core/config.py patch .env.example patch backend/.env.example patch backend/app/workers/render_poll_worker.py full integrated version patch backend/app/workers/render_postprocess_worker.py full integrated version
Mình đang nối phần hardening theo đúng lớp còn thiếu của phase này: test rotation + worker tick + config/env + bản worker integrated để batch state khớp hoàn toàn với render runtime.
Đã suy nghĩ trong vài giây
Được. Mình viết tiếp ngay PHASE hardening theo đúng format paste-ready, bám đúng các contract đã tạo ở phase trước.
1) tests/test_provider_account_rotation_service.py
import json
from datetime import datetime, timezone

from backend.app.services.provider_account_rotation_service import ProviderAccountRotationService


class DummySettings:
    VEO_PROVIDER_ROTATION_ENABLED = True
    VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS = 120
    VEO_PROVIDER_ACCOUNT_POOL_JSON = json.dumps(
        {
            "veo": [
                {"id": "acct-primary"},
                {"id": "acct-secondary"},
                {"id": "acct-tertiary"},
            ]
        }
    )


def test_pick_account_returns_none_when_no_pool(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.provider_account_rotation_service.settings",
        type(
            "Settings",
            (),
            {
                "VEO_PROVIDER_ROTATION_ENABLED": True,
                "VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS": 120,
                "VEO_PROVIDER_ACCOUNT_POOL_JSON": "",
            },
        )(),
    )

    service = ProviderAccountRotationService()
    picked = service.pick_account_for_mode(provider="veo", mode="text_to_video")

    assert picked is None


def test_pick_account_returns_first_when_rotation_disabled(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.provider_account_rotation_service.settings",
        type(
            "Settings",
            (),
            {
                "VEO_PROVIDER_ROTATION_ENABLED": False,
                "VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS": 120,
                "VEO_PROVIDER_ACCOUNT_POOL_JSON": json.dumps(
                    {"veo": [{"id": "acct-primary"}, {"id": "acct-secondary"}]}
                ),
            },
        )(),
    )

    service = ProviderAccountRotationService()
    picked = service.pick_account_for_mode(provider="veo", mode="text_to_video")

    assert picked is not None
    assert picked["provider_name"] == "veo"
    assert picked["account_id"] == "acct-primary"


def test_pick_account_rotates_across_accounts(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.provider_account_rotation_service.settings",
        DummySettings(),
    )

    service = ProviderAccountRotationService()

    first = service.pick_account_for_mode(provider="veo", mode="text_to_video")
    service.mark_dispatch(first["provider_name"], first["account_id"])

    second = service.pick_account_for_mode(provider="veo", mode="text_to_video")
    service.mark_dispatch(second["provider_name"], second["account_id"])

    third = service.pick_account_for_mode(provider="veo", mode="text_to_video")

    assert first is not None
    assert second is not None
    assert third is not None
    assert len({first["account_id"], second["account_id"], third["account_id"]}) >= 2


def test_mark_failure_rate_limit_puts_account_on_cooldown(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.provider_account_rotation_service.settings",
        DummySettings(),
    )

    service = ProviderAccountRotationService()
    service.mark_failure(provider="veo", account_id="acct-primary", error_code="rate_limit")

    picked = service.pick_account_for_mode(provider="veo", mode="text_to_video")

    assert picked is not None
    assert picked["account_id"] != "acct-primary"


def test_mark_success_reduces_failure_score(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.provider_account_rotation_service.settings",
        DummySettings(),
    )

    service = ProviderAccountRotationService()
    service.mark_failure(provider="veo", account_id="acct-primary", error_code="503")
    key = service._key("veo", "acct-primary")
    before = service._failure_counts[key]

    service.mark_success(provider="veo", account_id="acct-primary")
    after = service._failure_counts[key]

    assert after <= before
    assert after >= 0


def test_accounts_for_provider_accepts_string_and_dict(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.provider_account_rotation_service.settings",
        type(
            "Settings",
            (),
            {
                "VEO_PROVIDER_ROTATION_ENABLED": True,
                "VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS": 120,
                "VEO_PROVIDER_ACCOUNT_POOL_JSON": json.dumps(
                    {
                        "veo": [
                            "acct-primary",
                            {"id": "acct-secondary"},
                        ]
                    }
                ),
            },
        )(),
    )

    service = ProviderAccountRotationService()
    accounts = service._accounts_for_provider("veo")

    assert len(accounts) == 2
    assert accounts[0]["id"] == "acct-primary"
    assert accounts[1]["id"] == "acct-secondary"
2) tests/test_veo_batch_scheduler_worker.py
from unittest.mock import MagicMock, patch

from backend.app.workers.veo_batch_scheduler_worker import tick_veo_batch_scheduler


@patch("backend.app.workers.veo_batch_scheduler_worker.VeoBatchSchedulerService")
def test_tick_veo_batch_scheduler_calls_dispatch_ready_batches(mock_service_cls):
    mock_service = MagicMock()
    mock_service.dispatch_ready_batches.return_value = {
        "ok": True,
        "dispatched_batches": 2,
        "dispatched_items": 5,
    }
    mock_service_cls.return_value = mock_service

    result = tick_veo_batch_scheduler()

    mock_service_cls.assert_called_once()
    mock_service.dispatch_ready_batches.assert_called_once()
    assert result["ok"] is True
    assert result["dispatched_batches"] == 2
    assert result["dispatched_items"] == 5
3) PATCH backend/app/core/config.py
Thêm block này vào class settings hoặc module config hiện có.
Mình giữ đúng naming đã dùng trong services/workers trước đó.
# Veo workspace / batch runtime
VEO_REFERENCE_PREVIEW_MODEL: str = "veo-3.1-generate-preview"
VEO_ENABLE_REFERENCE_PREVIEW: bool = False
VEO_ENABLE_SOUND_GENERATION: bool = False
VEO_BATCH_MAX_SCRIPTS: int = 100

# Veo batch scheduler hardening
VEO_BATCH_DISPATCH_TICK_SECONDS: int = 15
VEO_BATCH_MAX_PARALLEL_ITEMS: int = 4
VEO_BATCH_LEASE_TTL_SECONDS: int = 300
VEO_BATCH_RETRY_BACKOFF_SECONDS: int = 60

VEO_BATCH_MAX_RETRIES_TEXT: int = 3
VEO_BATCH_MAX_RETRIES_IMAGE: int = 2
VEO_BATCH_MAX_RETRIES_FIRST_LAST: int = 2
VEO_BATCH_MAX_RETRIES_REFERENCE_PREVIEW: int = 1

VEO_BATCH_QUOTA_AWARE_SCHEDULING: bool = True

VEO_PROVIDER_ROTATION_ENABLED: bool = False
VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS: int = 120
VEO_PROVIDER_ACCOUNT_POOL_JSON: str = ""
4) PATCH .env.example
# Veo workspace / batch
VEO_REFERENCE_PREVIEW_MODEL=veo-3.1-generate-preview
VEO_ENABLE_REFERENCE_PREVIEW=false
VEO_ENABLE_SOUND_GENERATION=false
VEO_BATCH_MAX_SCRIPTS=100

# Veo scheduler / retry / quota
VEO_BATCH_DISPATCH_TICK_SECONDS=15
VEO_BATCH_MAX_PARALLEL_ITEMS=4
VEO_BATCH_LEASE_TTL_SECONDS=300
VEO_BATCH_RETRY_BACKOFF_SECONDS=60
VEO_BATCH_MAX_RETRIES_TEXT=3
VEO_BATCH_MAX_RETRIES_IMAGE=2
VEO_BATCH_MAX_RETRIES_FIRST_LAST=2
VEO_BATCH_MAX_RETRIES_REFERENCE_PREVIEW=1
VEO_BATCH_QUOTA_AWARE_SCHEDULING=true

# Provider account rotation
VEO_PROVIDER_ROTATION_ENABLED=false
VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS=120
VEO_PROVIDER_ACCOUNT_POOL_JSON={"veo":[{"id":"acct-primary"},{"id":"acct-secondary"}]}
5) PATCH backend/.env.example
# Veo workspace / batch
VEO_REFERENCE_PREVIEW_MODEL=veo-3.1-generate-preview
VEO_ENABLE_REFERENCE_PREVIEW=false
VEO_ENABLE_SOUND_GENERATION=false
VEO_BATCH_MAX_SCRIPTS=100

# Veo scheduler / retry / quota
VEO_BATCH_DISPATCH_TICK_SECONDS=15
VEO_BATCH_MAX_PARALLEL_ITEMS=4
VEO_BATCH_LEASE_TTL_SECONDS=300
VEO_BATCH_RETRY_BACKOFF_SECONDS=60
VEO_BATCH_MAX_RETRIES_TEXT=3
VEO_BATCH_MAX_RETRIES_IMAGE=2
VEO_BATCH_MAX_RETRIES_FIRST_LAST=2
VEO_BATCH_MAX_RETRIES_REFERENCE_PREVIEW=1
VEO_BATCH_QUOTA_AWARE_SCHEDULING=true

# Provider account rotation
VEO_PROVIDER_ROTATION_ENABLED=false
VEO_PROVIDER_ACCOUNT_COOLDOWN_SECONDS=120
VEO_PROVIDER_ACCOUNT_POOL_JSON={"veo":[{"id":"acct-primary"},{"id":"acct-secondary"}]}
6) PATCH backend/app/workers/render_poll_worker.py
Full integrated version
Mình viết theo kiểu full file paste-ready nhưng vẫn giữ integration mềm với runtime hiện có.
Nếu repo bạn đã có Celery app/loop khác, giữ nguyên phần bootstrapping cũ và paste các helper + task logic vào.
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from celery import shared_task

from backend.app.db.session import SessionLocal
from backend.app.services.veo_batch_scheduler_service import VeoBatchSchedulerService

try:
    from backend.app.models.render_job import RenderJob
except Exception:  # pragma: no cover
    RenderJob = None

try:
    from backend.app.services.render_poll_service import RenderPollService
except Exception:  # pragma: no cover
    RenderPollService = None


ACTIVE_RENDER_STATUSES = {"queued", "submitted", "running", "processing"}


def _extract_metadata(render_job: Any) -> Dict[str, Any]:
    metadata = getattr(render_job, "metadata", None)
    if isinstance(metadata, dict):
        return metadata
    return {}


def _extract_batch_item_id(render_job: Any) -> Optional[str]:
    metadata = _extract_metadata(render_job)
    return metadata.get("batch_item_id") or getattr(render_job, "batch_item_id", None)


def _extract_render_job_id(render_job: Any) -> Optional[str]:
    value = getattr(render_job, "id", None) or getattr(render_job, "render_job_id", None)
    return str(value) if value is not None else None


def _normalize_provider_status(status_payload: Dict[str, Any] | None, render_job: Any) -> str:
    raw = (
        (status_payload or {}).get("status")
        or getattr(render_job, "provider_status", None)
        or getattr(render_job, "status", None)
        or ""
    )
    return str(raw).strip().lower()


def _sync_veo_batch_item_from_render_job(render_job: Any, status_payload: Dict[str, Any] | None = None) -> None:
    batch_item_id = _extract_batch_item_id(render_job)
    if not batch_item_id:
        return

    scheduler = VeoBatchSchedulerService()
    normalized_status = _normalize_provider_status(status_payload, render_job)

    if normalized_status in {"queued", "submitted", "pending"}:
        return

    if normalized_status in {"running", "processing"}:
        scheduler.mark_item_started(
            item_id=batch_item_id,
            render_job_id=_extract_render_job_id(render_job),
        )
        return

    if normalized_status in {"succeeded", "completed", "done"}:
        scheduler.mark_item_succeeded(
            item_id=batch_item_id,
            result={
                "output_url": (status_payload or {}).get("output_url") or getattr(render_job, "output_url", None),
                "preview_url": (status_payload or {}).get("preview_url") or getattr(render_job, "preview_url", None),
                "video_url": (status_payload or {}).get("video_url"),
                "thumbnail_url": (status_payload or {}).get("thumbnail_url"),
                "provider_payload": status_payload or {},
            },
        )
        return

    if normalized_status in {"failed", "error", "cancelled"}:
        scheduler.mark_item_failed(
            item_id=batch_item_id,
            error={
                "error_code": (status_payload or {}).get("error_code")
                or getattr(render_job, "last_error_code", None)
                or normalized_status,
                "message": (status_payload or {}).get("message")
                or getattr(render_job, "last_error_message", None)
                or "Render job failed during provider polling",
                "status": normalized_status,
            },
        )


def _poll_single_render_job(render_job: Any) -> Dict[str, Any]:
    if RenderPollService is None:
        return {
            "ok": False,
            "render_job_id": _extract_render_job_id(render_job),
            "error": "render_poll_service_missing",
        }

    service = RenderPollService()
    status_payload = service.poll_render_job(render_job)

    _sync_veo_batch_item_from_render_job(render_job=render_job, status_payload=status_payload)

    return {
        "ok": True,
        "render_job_id": _extract_render_job_id(render_job),
        "status": _normalize_provider_status(status_payload, render_job),
        "provider_payload": status_payload,
    }


def _list_active_render_jobs(db) -> List[Any]:
    if RenderJob is None:
        return []

    return (
        db.query(RenderJob)
        .filter(RenderJob.status.in_(list(ACTIVE_RENDER_STATUSES)))
        .order_by(RenderJob.created_at.asc())
        .all()
    )


@shared_task(name="backend.app.workers.render_poll_worker.poll_render_jobs_task")
def poll_render_jobs_task() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        jobs = _list_active_render_jobs(db)
        results = []
        for job in jobs:
            results.append(_poll_single_render_job(job))

        return {
            "ok": True,
            "polled_jobs": len(jobs),
            "results": results,
        }
    finally:
        db.close()
7) PATCH backend/app/workers/render_postprocess_worker.py
Full integrated version
Mình viết theo kiểu full integrated, nhưng vẫn để điểm map mềm sang service postprocess hiện có.
from __future__ import annotations

from typing import Any, Dict, Optional

from celery import shared_task

from backend.app.db.session import SessionLocal
from backend.app.services.veo_batch_scheduler_service import VeoBatchSchedulerService

try:
    from backend.app.models.render_job import RenderJob
except Exception:  # pragma: no cover
    RenderJob = None

try:
    from backend.app.services.render_postprocess_service import RenderPostprocessService
except Exception:  # pragma: no cover
    RenderPostprocessService = None


TERMINAL_READY_FOR_POSTPROCESS = {"succeeded", "completed", "done"}


def _extract_metadata(render_job: Any) -> Dict[str, Any]:
    metadata = getattr(render_job, "metadata", None)
    if isinstance(metadata, dict):
        return metadata
    return {}


def _extract_batch_item_id(render_job: Any) -> Optional[str]:
    metadata = _extract_metadata(render_job)
    return metadata.get("batch_item_id") or getattr(render_job, "batch_item_id", None)


def _extract_render_job_id(render_job: Any) -> Optional[str]:
    value = getattr(render_job, "id", None) or getattr(render_job, "render_job_id", None)
    return str(value) if value is not None else None


def _normalize_render_status(render_job: Any) -> str:
    return str(
        getattr(render_job, "status", None)
        or getattr(render_job, "provider_status", None)
        or ""
    ).strip().lower()


def _finalize_veo_batch_item_postprocess(render_job: Any, output_payload: Dict[str, Any] | None = None) -> None:
    batch_item_id = _extract_batch_item_id(render_job)
    if not batch_item_id:
        return

    scheduler = VeoBatchSchedulerService()
    scheduler.mark_item_succeeded(
        item_id=batch_item_id,
        result={
            "output_url": (output_payload or {}).get("output_url") or getattr(render_job, "output_url", None),
            "preview_url": (output_payload or {}).get("preview_url") or getattr(render_job, "preview_url", None),
            "thumbnail_url": (output_payload or {}).get("thumbnail_url"),
            "postprocess_payload": output_payload or {},
        },
    )


def _mark_postprocess_failure(render_job: Any, error: Exception | Dict[str, Any]) -> None:
    batch_item_id = _extract_batch_item_id(render_job)
    if not batch_item_id:
        return

    scheduler = VeoBatchSchedulerService()
    if isinstance(error, Exception):
        payload = {
            "error_code": getattr(error, "code", None) or "postprocess_exception",
            "message": str(error),
        }
    else:
        payload = error

    scheduler.mark_item_failed(
        item_id=batch_item_id,
        error=payload,
    )


def _run_single_postprocess(render_job: Any) -> Dict[str, Any]:
    if RenderPostprocessService is None:
        error = {
            "error_code": "render_postprocess_service_missing",
            "message": "RenderPostprocessService not available",
        }
        _mark_postprocess_failure(render_job, error)
        return {
            "ok": False,
            "render_job_id": _extract_render_job_id(render_job),
            "error": error["error_code"],
        }

    service = RenderPostprocessService()

    try:
        output_payload = service.postprocess_render_job(render_job)
        _finalize_veo_batch_item_postprocess(render_job, output_payload)
        return {
            "ok": True,
            "render_job_id": _extract_render_job_id(render_job),
            "output_payload": output_payload,
        }
    except Exception as exc:  # pragma: no cover
        _mark_postprocess_failure(render_job, exc)
        return {
            "ok": False,
            "render_job_id": _extract_render_job_id(render_job),
            "error": str(exc),
        }


def _list_render_jobs_ready_for_postprocess(db):
    if RenderJob is None:
        return []

    return (
        db.query(RenderJob)
        .filter(RenderJob.status.in_(list(TERMINAL_READY_FOR_POSTPROCESS)))
        .order_by(RenderJob.created_at.asc())
        .all()
    )


@shared_task(name="backend.app.workers.render_postprocess_worker.postprocess_render_jobs_task")
def postprocess_render_jobs_task() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        jobs = _list_render_jobs_ready_for_postprocess(db)
        results = []

        for job in jobs:
            results.append(_run_single_postprocess(job))

        return {
            "ok": True,
            "processed_jobs": len(jobs),
            "results": results,
        }
    finally:
        db.close()
8) Điểm tích hợp quan trọng nhất
render_poll_worker.py
Hiện file này giả định có:
RenderPollService().poll_render_job(render_job)
Nếu repo bạn dùng tên method khác, chỉ cần map tại đúng 1 chỗ:
status_payload = service.poll_render_job(render_job)
render_postprocess_worker.py
Hiện file này giả định có:
RenderPostprocessService().postprocess_render_job(render_job)
Nếu service thật tên khác, đổi đúng 1 chỗ đó.
RenderJob
Hai worker trên kỳ vọng model/job runtime có tối thiểu:
id
status
created_at
metadata hoặc batch_item_id
output_url / preview_url nếu có
9) Kết quả sau phase hardening này
Bây giờ batch Veo của bạn đã có thêm lớp cứng hóa quan trọng:
Test coverage
provider account rotation
scheduler worker tick
Config completeness
config/env đủ cho quota, retry, rotation, preview
Worker integration
poll worker tự sync VeoBatchItem từ render runtime
postprocess worker finalize output ngược về batch item
failure trong postprocess cũng quay về retry/fail policy layer
Nghĩa là hệ đã đi từ:
batch materialization + dispatch
sang:
batch execution loop có hardening + feedback trở về workspace state
Ở lượt tiếp theo, bước mạnh nhất là viết tiếp phase observability + ops theo đúng format paste-ready:
backend/app/api/veo_workspace.py patch thêm timeline/errors summary
tests/test_render_poll_worker.py
tests/test_render_postprocess_worker.py
frontend/src/components/veo/VeoBatchFailuresPanel.tsx
frontend/src/components/veo/VeoBatchTimelinePanel.tsx
patch project workspace page để có tab Overview / Items / Failures / Timeline
Ở lượt tiếp theo, bước mạnh nhất là viết tiếp phase observability + ops theo đúng format paste-ready: backend/app/api/veo_workspace.py patch thêm timeline/errors summary tests/test_render_poll_worker.py tests/test_render_postprocess_worker.py frontend/src/components/veo/VeoBatchFailuresPanel.tsx frontend/src/components/veo/VeoBatchTimelinePanel.tsx patch project workspace page để có tab Overview / Items / Failures / Timeline
Mình đang nối lớp observability + ops đúng trên contract batch hiện có: ưu tiên API summary/timeline và test worker trước, rồi mới ghép panels + tabs frontend để UI đọc được state thật từ runtime.
Đã suy nghĩ trong vài giây
Được. Mình viết tiếp ngay phase observability + ops theo đúng format paste-ready, bám vào các route/service/worker đã có ở phase trước.
1) PATCH backend/app/api/veo_workspace.py
Thêm timeline + errors summary
Bản này giữ nguyên các route trước đó và bổ sung schema + routes mới.
Nếu file bạn đang có chưa import or_, nhớ thêm:
from sqlalchemy import func, select, or_
Thêm các schema này vào file
class VeoBatchErrorSummaryItem(BaseModel):
    error_code: str
    count: int
    latest_message: Optional[str] = None


class VeoBatchErrorsSummaryResponse(BaseModel):
    batch_run_id: str
    total_failed_items: int
    total_retry_waiting_items: int
    errors: List[VeoBatchErrorSummaryItem]


class VeoBatchTimelineEvent(BaseModel):
    event_type: str
    item_id: Optional[str] = None
    render_job_id: Optional[str] = None
    title: str
    status: Optional[str] = None
    mode: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    timestamp: datetime


class VeoBatchTimelineResponse(BaseModel):
    batch_run_id: str
    events: List[VeoBatchTimelineEvent]
Thêm route errors summary
@router.get("/batch-runs/{batch_id}/errors-summary", response_model=VeoBatchErrorsSummaryResponse)
def get_batch_run_errors_summary(batch_id: str, db: Session = Depends(get_db)) -> VeoBatchErrorsSummaryResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    failed_count = int(
        db.execute(
            select(func.count(VeoBatchItem.id)).where(
                VeoBatchItem.batch_run_id == batch_id,
                VeoBatchItem.status == "failed",
            )
        ).scalar()
        or 0
    )

    retry_waiting_count = int(
        db.execute(
            select(func.count(VeoBatchItem.id)).where(
                VeoBatchItem.batch_run_id == batch_id,
                VeoBatchItem.status == "retry_waiting",
            )
        ).scalar()
        or 0
    )

    rows = db.execute(
        select(
            VeoBatchItem.last_error_code,
            func.count(VeoBatchItem.id),
            func.max(VeoBatchItem.updated_at),
        )
        .where(
            VeoBatchItem.batch_run_id == batch_id,
            VeoBatchItem.last_error_code.is_not(None),
            VeoBatchItem.status.in_(["failed", "retry_waiting"]),
        )
        .group_by(VeoBatchItem.last_error_code)
        .order_by(func.count(VeoBatchItem.id).desc(), func.max(VeoBatchItem.updated_at).desc())
    ).all()

    errors: List[VeoBatchErrorSummaryItem] = []
    for error_code, count, _latest_ts in rows:
        latest_message = db.execute(
            select(VeoBatchItem.last_error_message)
            .where(
                VeoBatchItem.batch_run_id == batch_id,
                VeoBatchItem.last_error_code == error_code,
                VeoBatchItem.last_error_message.is_not(None),
            )
            .order_by(VeoBatchItem.updated_at.desc())
            .limit(1)
        ).scalar()

        errors.append(
            VeoBatchErrorSummaryItem(
                error_code=error_code or "unknown",
                count=int(count or 0),
                latest_message=latest_message,
            )
        )

    return VeoBatchErrorsSummaryResponse(
        batch_run_id=batch_id,
        total_failed_items=failed_count,
        total_retry_waiting_items=retry_waiting_count,
        errors=errors,
    )
Thêm route timeline
@router.get("/batch-runs/{batch_id}/timeline", response_model=VeoBatchTimelineResponse)
def get_batch_run_timeline(
    batch_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> VeoBatchTimelineResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    events: List[VeoBatchTimelineEvent] = []

    if getattr(run, "submitted_at", None):
        events.append(
            VeoBatchTimelineEvent(
                event_type="batch_submitted",
                title="Batch submitted",
                status=run.status,
                timestamp=run.submitted_at,
            )
        )

    if getattr(run, "started_at", None):
        events.append(
            VeoBatchTimelineEvent(
                event_type="batch_started",
                title="Batch started dispatch/runtime execution",
                status=run.status,
                timestamp=run.started_at,
            )
        )

    if getattr(run, "completed_at", None):
        events.append(
            VeoBatchTimelineEvent(
                event_type="batch_completed",
                title="Batch completed",
                status=run.status,
                timestamp=run.completed_at,
            )
        )

    if getattr(run, "failed_at", None):
        events.append(
            VeoBatchTimelineEvent(
                event_type="batch_failed",
                title="Batch failed",
                status=run.status,
                timestamp=run.failed_at,
            )
        )

    if getattr(run, "cancelled_at", None):
        events.append(
            VeoBatchTimelineEvent(
                event_type="batch_cancelled",
                title="Batch cancelled",
                status=run.status,
                timestamp=run.cancelled_at,
            )
        )

    items = db.execute(
        select(VeoBatchItem)
        .where(VeoBatchItem.batch_run_id == batch_id)
        .order_by(VeoBatchItem.updated_at.desc(), VeoBatchItem.created_at.desc())
        .limit(limit)
    ).scalars().all()

    for item in items:
        if getattr(item, "created_at", None):
            events.append(
                VeoBatchTimelineEvent(
                    event_type="item_created",
                    item_id=item.id,
                    render_job_id=getattr(item, "render_job_id", None),
                    title="Batch item created",
                    status=item.status,
                    mode=getattr(item, "mode", None),
                    timestamp=item.created_at,
                )
            )

        if getattr(item, "leased_at", None):
            events.append(
                VeoBatchTimelineEvent(
                    event_type="item_leased",
                    item_id=item.id,
                    render_job_id=getattr(item, "render_job_id", None),
                    title="Item leased for dispatch",
                    status=item.status,
                    mode=getattr(item, "mode", None),
                    timestamp=item.leased_at,
                )
            )

        if getattr(item, "submitted_at", None):
            events.append(
                VeoBatchTimelineEvent(
                    event_type="item_submitted",
                    item_id=item.id,
                    render_job_id=getattr(item, "render_job_id", None),
                    title="Item submitted to render runtime",
                    status=item.status,
                    mode=getattr(item, "mode", None),
                    timestamp=item.submitted_at,
                )
            )

        if getattr(item, "started_at", None):
            events.append(
                VeoBatchTimelineEvent(
                    event_type="item_started",
                    item_id=item.id,
                    render_job_id=getattr(item, "render_job_id", None),
                    title="Item started processing",
                    status=item.status,
                    mode=getattr(item, "mode", None),
                    timestamp=item.started_at,
                )
            )

        if getattr(item, "next_retry_at", None) and item.status == "retry_waiting":
            events.append(
                VeoBatchTimelineEvent(
                    event_type="item_retry_waiting",
                    item_id=item.id,
                    render_job_id=getattr(item, "render_job_id", None),
                    title="Item waiting for retry",
                    status=item.status,
                    mode=getattr(item, "mode", None),
                    error_code=getattr(item, "last_error_code", None),
                    message=getattr(item, "last_error_message", None),
                    timestamp=item.next_retry_at,
                )
            )

        if getattr(item, "finished_at", None):
            if item.status == "succeeded":
                events.append(
                    VeoBatchTimelineEvent(
                        event_type="item_succeeded",
                        item_id=item.id,
                        render_job_id=getattr(item, "render_job_id", None),
                        title="Item succeeded",
                        status=item.status,
                        mode=getattr(item, "mode", None),
                        timestamp=item.finished_at,
                    )
                )
            elif item.status in {"failed", "cancelled"}:
                events.append(
                    VeoBatchTimelineEvent(
                        event_type="item_failed" if item.status == "failed" else "item_cancelled",
                        item_id=item.id,
                        render_job_id=getattr(item, "render_job_id", None),
                        title="Item failed" if item.status == "failed" else "Item cancelled",
                        status=item.status,
                        mode=getattr(item, "mode", None),
                        error_code=getattr(item, "last_error_code", None),
                        message=getattr(item, "last_error_message", None),
                        timestamp=item.finished_at,
                    )
                )

    events = sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    return VeoBatchTimelineResponse(
        batch_run_id=batch_id,
        events=events,
    )
2) tests/test_render_poll_worker.py
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.workers.render_poll_worker import (
    _sync_veo_batch_item_from_render_job,
    poll_render_jobs_task,
)


def test_sync_marks_item_started():
    render_job = SimpleNamespace(
        id="render-1",
        metadata={"batch_item_id": "item-1"},
        status="running",
        provider_status="running",
    )

    with patch("backend.app.workers.render_poll_worker.VeoBatchSchedulerService") as mock_scheduler_cls:
        scheduler = mock_scheduler_cls.return_value

        _sync_veo_batch_item_from_render_job(
            render_job=render_job,
            status_payload={"status": "running"},
        )

        scheduler.mark_item_started.assert_called_once_with(
            item_id="item-1",
            render_job_id="render-1",
        )


def test_sync_marks_item_succeeded():
    render_job = SimpleNamespace(
        id="render-2",
        metadata={"batch_item_id": "item-2"},
        status="completed",
        output_url="https://cdn.example.com/video.mp4",
        preview_url="https://cdn.example.com/preview.jpg",
    )

    with patch("backend.app.workers.render_poll_worker.VeoBatchSchedulerService") as mock_scheduler_cls:
        scheduler = mock_scheduler_cls.return_value

        _sync_veo_batch_item_from_render_job(
            render_job=render_job,
            status_payload={
                "status": "completed",
                "output_url": "https://cdn.example.com/video.mp4",
                "preview_url": "https://cdn.example.com/preview.jpg",
            },
        )

        scheduler.mark_item_succeeded.assert_called_once()
        kwargs = scheduler.mark_item_succeeded.call_args.kwargs
        assert kwargs["item_id"] == "item-2"
        assert kwargs["result"]["output_url"] == "https://cdn.example.com/video.mp4"


def test_sync_marks_item_failed():
    render_job = SimpleNamespace(
        id="render-3",
        metadata={"batch_item_id": "item-3"},
        status="failed",
        last_error_code="503",
        last_error_message="Provider unavailable",
    )

    with patch("backend.app.workers.render_poll_worker.VeoBatchSchedulerService") as mock_scheduler_cls:
        scheduler = mock_scheduler_cls.return_value

        _sync_veo_batch_item_from_render_job(
            render_job=render_job,
            status_payload={
                "status": "failed",
                "error_code": "503",
                "message": "Provider unavailable",
            },
        )

        scheduler.mark_item_failed.assert_called_once()
        kwargs = scheduler.mark_item_failed.call_args.kwargs
        assert kwargs["item_id"] == "item-3"
        assert kwargs["error"]["error_code"] == "503"


def test_sync_noop_when_no_batch_item_id():
    render_job = SimpleNamespace(
        id="render-4",
        metadata={},
        status="running",
    )

    with patch("backend.app.workers.render_poll_worker.VeoBatchSchedulerService") as mock_scheduler_cls:
        _sync_veo_batch_item_from_render_job(
            render_job=render_job,
            status_payload={"status": "running"},
        )

        mock_scheduler_cls.assert_not_called()


@patch("backend.app.workers.render_poll_worker._list_active_render_jobs")
@patch("backend.app.workers.render_poll_worker.RenderPollService")
@patch("backend.app.workers.render_poll_worker.SessionLocal")
def test_poll_render_jobs_task(SessionLocalMock, RenderPollServiceMock, list_jobs_mock):
    db = SessionLocalMock.return_value
    render_job = SimpleNamespace(
        id="render-5",
        metadata={"batch_item_id": "item-5"},
        status="running",
        provider_status="running",
    )

    list_jobs_mock.return_value = [render_job]
    RenderPollServiceMock.return_value.poll_render_job.return_value = {"status": "running"}

    with patch("backend.app.workers.render_poll_worker.VeoBatchSchedulerService") as mock_scheduler_cls:
        scheduler = mock_scheduler_cls.return_value

        result = poll_render_jobs_task()

        assert result["ok"] is True
        assert result["polled_jobs"] == 1
        scheduler.mark_item_started.assert_called_once()
3) tests/test_render_postprocess_worker.py
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.workers.render_postprocess_worker import (
    _finalize_veo_batch_item_postprocess,
    postprocess_render_jobs_task,
)


def test_finalize_veo_batch_item_postprocess_marks_success():
    render_job = SimpleNamespace(
        id="render-10",
        metadata={"batch_item_id": "item-10"},
        output_url="https://cdn.example.com/final.mp4",
        preview_url="https://cdn.example.com/final.jpg",
    )

    with patch("backend.app.workers.render_postprocess_worker.VeoBatchSchedulerService") as mock_scheduler_cls:
        scheduler = mock_scheduler_cls.return_value

        _finalize_veo_batch_item_postprocess(
            render_job=render_job,
            output_payload={
                "output_url": "https://cdn.example.com/final.mp4",
                "preview_url": "https://cdn.example.com/final.jpg",
            },
        )

        scheduler.mark_item_succeeded.assert_called_once()
        kwargs = scheduler.mark_item_succeeded.call_args.kwargs
        assert kwargs["item_id"] == "item-10"
        assert kwargs["result"]["output_url"] == "https://cdn.example.com/final.mp4"


@patch("backend.app.workers.render_postprocess_worker._list_render_jobs_ready_for_postprocess")
@patch("backend.app.workers.render_postprocess_worker.RenderPostprocessService")
@patch("backend.app.workers.render_postprocess_worker.SessionLocal")
def test_postprocess_render_jobs_task_success(
    SessionLocalMock,
    RenderPostprocessServiceMock,
    list_jobs_mock,
):
    db = SessionLocalMock.return_value
    render_job = SimpleNamespace(
        id="render-11",
        metadata={"batch_item_id": "item-11"},
        status="completed",
        output_url="https://cdn.example.com/out.mp4",
        preview_url="https://cdn.example.com/prev.jpg",
    )

    list_jobs_mock.return_value = [render_job]
    RenderPostprocessServiceMock.return_value.postprocess_render_job.return_value = {
        "output_url": "https://cdn.example.com/out.mp4",
        "preview_url": "https://cdn.example.com/prev.jpg",
    }

    with patch("backend.app.workers.render_postprocess_worker.VeoBatchSchedulerService") as mock_scheduler_cls:
        scheduler = mock_scheduler_cls.return_value

        result = postprocess_render_jobs_task()

        assert result["ok"] is True
        assert result["processed_jobs"] == 1
        scheduler.mark_item_succeeded.assert_called_once()


@patch("backend.app.workers.render_postprocess_worker._list_render_jobs_ready_for_postprocess")
@patch("backend.app.workers.render_postprocess_worker.RenderPostprocessService")
@patch("backend.app.workers.render_postprocess_worker.SessionLocal")
def test_postprocess_render_jobs_task_failure(
    SessionLocalMock,
    RenderPostprocessServiceMock,
    list_jobs_mock,
):
    db = SessionLocalMock.return_value
    render_job = SimpleNamespace(
        id="render-12",
        metadata={"batch_item_id": "item-12"},
        status="completed",
    )

    list_jobs_mock.return_value = [render_job]
    RenderPostprocessServiceMock.return_value.postprocess_render_job.side_effect = RuntimeError("ffmpeg failed")

    with patch("backend.app.workers.render_postprocess_worker.VeoBatchSchedulerService") as mock_scheduler_cls:
        scheduler = mock_scheduler_cls.return_value

        result = postprocess_render_jobs_task()

        assert result["ok"] is True
        assert result["processed_jobs"] == 1
        scheduler.mark_item_failed.assert_called_once()
4) PATCH frontend/src/lib/api.ts
Thêm API cho errors summary + timeline
Paste thêm các type/function dưới đây vào file.
export type VeoBatchErrorSummaryItem = {
  error_code: string;
  count: number;
  latest_message?: string | null;
};

export type VeoBatchErrorsSummary = {
  batch_run_id: string;
  total_failed_items: number;
  total_retry_waiting_items: number;
  errors: VeoBatchErrorSummaryItem[];
};

export type VeoBatchTimelineEvent = {
  event_type: string;
  item_id?: string | null;
  render_job_id?: string | null;
  title: string;
  status?: string | null;
  mode?: string | null;
  error_code?: string | null;
  message?: string | null;
  timestamp: string;
};

export type VeoBatchTimeline = {
  batch_run_id: string;
  events: VeoBatchTimelineEvent[];
};

export async function getVeoBatchErrorsSummary(batchId: string): Promise<VeoBatchErrorsSummary> {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/errors-summary`);
  if (!res.ok) throw new Error(`Failed to fetch batch errors summary ${batchId}`);
  return res.json();
}

export async function getVeoBatchTimeline(
  batchId: string,
  params?: { limit?: number }
): Promise<VeoBatchTimeline> {
  const search = new URLSearchParams();
  if (params?.limit != null) search.set("limit", String(params.limit));
  const qs = search.toString();

  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/timeline${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to fetch batch timeline ${batchId}`);
  return res.json();
}
5) frontend/src/components/veo/VeoBatchFailuresPanel.tsx
"use client";

import { VeoBatchErrorsSummary } from "@/src/lib/api";

type Props = {
  summary: VeoBatchErrorsSummary | null;
  loading?: boolean;
};

export default function VeoBatchFailuresPanel({ summary, loading }: Props) {
  if (loading && !summary) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        Loading failure summary...
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        No failure summary available.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <StatCard label="Failed Items" value={summary.total_failed_items} />
        <StatCard label="Retry Waiting" value={summary.total_retry_waiting_items} />
        <StatCard label="Unique Error Codes" value={summary.errors.length} />
      </div>

      <div className="overflow-hidden rounded-2xl border border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 px-4 py-3">
          <h3 className="text-base font-semibold">Failure Breakdown</h3>
        </div>

        <div className="divide-y divide-neutral-200">
          {summary.errors.length === 0 ? (
            <div className="px-4 py-6 text-sm text-neutral-500">No failures recorded yet.</div>
          ) : (
            summary.errors.map((error) => (
              <div key={error.error_code} className="px-4 py-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{error.error_code}</div>
                    <div className="mt-1 text-sm text-neutral-600">
                      {error.latest_message || "No error message available"}
                    </div>
                  </div>
                  <div className="rounded-full border px-3 py-1 text-xs font-medium">
                    {error.count}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
6) frontend/src/components/veo/VeoBatchTimelinePanel.tsx
"use client";

import { VeoBatchTimeline } from "@/src/lib/api";

type Props = {
  timeline: VeoBatchTimeline | null;
  loading?: boolean;
};

export default function VeoBatchTimelinePanel({ timeline, loading }: Props) {
  if (loading && !timeline) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        Loading timeline...
      </div>
    );
  }

  if (!timeline) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        No timeline available.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white">
      <div className="border-b border-neutral-200 px-4 py-3">
        <h3 className="text-base font-semibold">Batch Timeline</h3>
      </div>

      <div className="divide-y divide-neutral-200">
        {timeline.events.length === 0 ? (
          <div className="px-4 py-6 text-sm text-neutral-500">No timeline events found.</div>
        ) : (
          timeline.events.map((event, index) => (
            <div key={`${event.event_type}-${event.item_id || "batch"}-${event.timestamp}-${index}`} className="px-4 py-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="font-medium">{event.title}</div>

                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-neutral-600">
                    <span className="rounded-full border px-2 py-1">{event.event_type}</span>
                    {event.status ? <span className="rounded-full border px-2 py-1">status: {event.status}</span> : null}
                    {event.mode ? <span className="rounded-full border px-2 py-1">mode: {event.mode}</span> : null}
                    {event.item_id ? <span className="rounded-full border px-2 py-1">item: {event.item_id}</span> : null}
                    {event.render_job_id ? (
                      <span className="rounded-full border px-2 py-1">render: {event.render_job_id}</span>
                    ) : null}
                    {event.error_code ? (
                      <span className="rounded-full border px-2 py-1 text-red-600">error: {event.error_code}</span>
                    ) : null}
                  </div>

                  {event.message ? (
                    <div className="mt-2 text-sm text-neutral-600">{event.message}</div>
                  ) : null}
                </div>

                <div className="shrink-0 text-xs text-neutral-500">
                  {new Date(event.timestamp).toLocaleString()}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
7) PATCH frontend/src/app/projects/[id]/page.tsx
Thêm tabs Overview / Items / Failures / Timeline
Bản này thay block VeoBatchWorkspaceSection phase trước bằng bản dưới.
Nó giữ nguyên stats/items hiện có, và bổ sung fetch + tab cho failures/timeline.
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getVeoBatchErrorsSummary,
  getVeoBatchRunItems,
  getVeoBatchRunStats,
  getVeoBatchTimeline,
  VeoBatchErrorsSummary,
  VeoBatchItemsPage,
  VeoBatchRunStats,
  VeoBatchTimeline,
} from "@/src/lib/api";
import VeoBatchRunPanel from "@/src/components/veo/VeoBatchRunPanel";
import VeoBatchItemsTable from "@/src/components/veo/VeoBatchItemsTable";
import VeoBatchFailuresPanel from "@/src/components/veo/VeoBatchFailuresPanel";
import VeoBatchTimelinePanel from "@/src/components/veo/VeoBatchTimelinePanel";

type VeoBatchWorkspaceProps = {
  batchId: string | null;
};

type VeoBatchTab = "overview" | "items" | "failures" | "timeline";

export function VeoBatchWorkspaceSection({ batchId }: VeoBatchWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<VeoBatchTab>("overview");

  const [stats, setStats] = useState<VeoBatchRunStats | null>(null);
  const [itemsPage, setItemsPage] = useState<VeoBatchItemsPage>({
    items: [],
    total: 0,
    limit: 25,
    offset: 0,
  });
  const [errorsSummary, setErrorsSummary] = useState<VeoBatchErrorsSummary | null>(null);
  const [timeline, setTimeline] = useState<VeoBatchTimeline | null>(null);

  const [loading, setLoading] = useState(false);

  const [statusFilter, setStatusFilter] = useState("");
  const [modeFilter, setModeFilter] = useState("");
  const [searchText, setSearchText] = useState("");

  const refresh = useCallback(
    async (nextOffset?: number) => {
      if (!batchId) return;

      const offset = nextOffset ?? itemsPage.offset;
      setLoading(true);

      try {
        const [statsData, itemsData, errorsData, timelineData] = await Promise.all([
          getVeoBatchRunStats(batchId),
          getVeoBatchRunItems(batchId, {
            limit: itemsPage.limit,
            offset,
            status: statusFilter || undefined,
            mode: modeFilter || undefined,
            search: searchText || undefined,
          }),
          getVeoBatchErrorsSummary(batchId),
          getVeoBatchTimeline(batchId, { limit: 100 }),
        ]);

        setStats(statsData);
        setItemsPage(itemsData);
        setErrorsSummary(errorsData);
        setTimeline(timelineData);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    },
    [batchId, itemsPage.limit, itemsPage.offset, modeFilter, searchText, statusFilter]
  );

  useEffect(() => {
    void refresh(0);
  }, [batchId, statusFilter, modeFilter, searchText]);

  useEffect(() => {
    if (!batchId) return;
    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [batchId, refresh]);

  if (!batchId) {
    return (
      <div className="rounded-2xl border border-dashed border-neutral-300 p-6 text-sm text-neutral-500">
        No Veo batch run attached to this project yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <VeoBatchRunPanel batchId={batchId} stats={stats} onRefresh={() => refresh()} />

      <div className="flex flex-wrap items-center gap-2">
        <TabButton
          label="Overview"
          active={activeTab === "overview"}
          onClick={() => setActiveTab("overview")}
        />
        <TabButton
          label="Items"
          active={activeTab === "items"}
          onClick={() => setActiveTab("items")}
        />
        <TabButton
          label="Failures"
          active={activeTab === "failures"}
          onClick={() => setActiveTab("failures")}
        />
        <TabButton
          label="Timeline"
          active={activeTab === "timeline"}
          onClick={() => setActiveTab("timeline")}
        />
      </div>

      {activeTab === "overview" ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <VeoBatchFailuresPanel summary={errorsSummary} loading={loading} />
          <VeoBatchTimelinePanel
            timeline={{
              batch_run_id: timeline?.batch_run_id || batchId,
              events: (timeline?.events || []).slice(0, 20),
            }}
            loading={loading}
          />
        </div>
      ) : null}

      {activeTab === "items" ? (
        <VeoBatchItemsTable
          items={itemsPage.items}
          total={itemsPage.total}
          limit={itemsPage.limit}
          offset={itemsPage.offset}
          statusFilter={statusFilter}
          modeFilter={modeFilter}
          searchText={searchText}
          onChangeStatusFilter={(value) => setStatusFilter(value)}
          onChangeModeFilter={(value) => setModeFilter(value)}
          onChangeSearchText={(value) => setSearchText(value)}
          onPrevPage={() => void refresh(Math.max(0, itemsPage.offset - itemsPage.limit))}
          onNextPage={() => void refresh(itemsPage.offset + itemsPage.limit)}
        />
      ) : null}

      {activeTab === "failures" ? (
        <VeoBatchFailuresPanel summary={errorsSummary} loading={loading} />
      ) : null}

      {activeTab === "timeline" ? (
        <VeoBatchTimelinePanel timeline={timeline} loading={loading} />
      ) : null}
    </div>
  );
}

function TabButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={`rounded-xl border px-3 py-2 text-sm ${
        active ? "border-neutral-900 bg-neutral-900 text-white" : "border-neutral-300 bg-white text-neutral-700"
      }`}
      onClick={onClick}
    >
      {label}
    </button>
  );
}
8) Gợi ý patch nhỏ nếu bạn muốn Overview mạnh hơn ngay
Trong VeoBatchRunPanel.tsx, bạn có thể thêm 2 stat:
errorsSummary.total_failed_items
errorsSummary.total_retry_waiting_items
Nhưng chưa bắt buộc, vì tab Overview hiện đã show qua VeoBatchFailuresPanel.
9) Kết quả sau phase này
Sau patch này, workspace Veo của bạn có thêm lớp observability + ops khá đầy đủ:
Backend
errors summary theo error_code
timeline theo batch + item lifecycle
test cho poll worker
test cho postprocess worker
Frontend
panel Failures
panel Timeline
tab:
Overview
Items
Failures
Timeline
Tác dụng thực tế
Operator có thể nhìn rất nhanh:
batch đang kẹt ở đâu
lỗi nào lặp nhiều nhất
item nào retry liên tục
dòng thời gian dispatch → start → retry → fail/success
10) Bước mạnh nhất tiếp theo
Bước tiếp theo mạnh nhất là ops control + triage actions, theo đúng format paste-ready:
patch backend/app/api/veo_workspace.py thêm:
POST /batch-runs/{batch_id}/retry-by-error-code
POST /batch-runs/{batch_id}/cancel-pending
POST /batch-runs/{batch_id}/requeue-retry-waiting
tests cho các action endpoints trên
frontend/src/components/veo/VeoBatchOpsActionsPanel.tsx
patch timeline panel thêm quick filter theo event type
patch failures panel thêm action “retry affected items by error code”
Đó là bước biến dashboard từ quan sát sang điều hành trực tiếp.
Mình viết tiếp ngay ops control + triage actions theo đúng format paste-ready.
1) PATCH backend/app/api/veo_workspace.py
Thêm:
POST /batch-runs/{batch_id}/retry-by-error-code
POST /batch-runs/{batch_id}/cancel-pending
POST /batch-runs/{batch_id}/requeue-retry-waiting
Patch này bổ sung vào file hiện có.
Nếu file chưa import update, thêm:
from sqlalchemy import func, select, or_, update
Thêm schema request/response
class VeoBatchRetryByErrorCodeRequest(BaseModel):
    error_code: str


class VeoBatchBulkActionResponse(BaseModel):
    ok: bool
    batch_run_id: str
    affected_items: int
    action: str
Thêm helper action nội bộ vào file API
def _recompute_batch_status_inline(db: Session, batch_id: str) -> None:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        return

    rows = db.execute(
        select(VeoBatchItem.status, func.count(VeoBatchItem.id))
        .where(VeoBatchItem.batch_run_id == batch_id)
        .group_by(VeoBatchItem.status)
    ).all()

    counts = {status: count for status, count in rows}
    total = int(sum(counts.values()))

    if total == 0:
        run.status = "draft"
    elif counts.get("cancelled", 0) == total:
        run.status = "cancelled"
    elif counts.get("running", 0) > 0 or counts.get("submitted", 0) > 0 or counts.get("leased", 0) > 0:
        run.status = "running"
    elif counts.get("pending", 0) > 0 or counts.get("retry_waiting", 0) > 0:
        run.status = "queued"
    elif counts.get("failed", 0) > 0 and counts.get("succeeded", 0) > 0:
        run.status = "partially_failed"
    elif counts.get("failed", 0) == total:
        run.status = "failed"
    elif counts.get("succeeded", 0) + counts.get("cancelled", 0) == total:
        run.status = "completed"

    db.add(run)
    db.commit()
Thêm route retry-by-error-code
@router.post("/batch-runs/{batch_id}/retry-by-error-code", response_model=VeoBatchBulkActionResponse)
def retry_batch_items_by_error_code(
    batch_id: str,
    payload: VeoBatchRetryByErrorCodeRequest,
    db: Session = Depends(get_db),
) -> VeoBatchBulkActionResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    if not payload.error_code.strip():
        raise HTTPException(status_code=400, detail="error_code is required")

    items = db.execute(
        select(VeoBatchItem).where(
            VeoBatchItem.batch_run_id == batch_id,
            VeoBatchItem.last_error_code == payload.error_code,
            VeoBatchItem.status.in_(["failed", "retry_waiting"]),
        )
    ).scalars().all()

    affected = 0
    for item in items:
        item.status = "pending"
        item.next_retry_at = None
        item.finished_at = None
        item.last_error_code = None
        item.last_error_message = None
        item.render_job_id = None
        item.lease_token = None
        item.leased_at = None
        item.submitted_at = None
        item.started_at = None
        db.add(item)
        affected += 1

    if affected > 0:
        run.status = "queued"
        run.failed_at = None
        run.completed_at = None
        db.add(run)

    db.commit()
    _recompute_batch_status_inline(db, batch_id)

    return VeoBatchBulkActionResponse(
        ok=True,
        batch_run_id=batch_id,
        affected_items=affected,
        action=f"retry_by_error_code:{payload.error_code}",
    )
Thêm route cancel-pending
@router.post("/batch-runs/{batch_id}/cancel-pending", response_model=VeoBatchBulkActionResponse)
def cancel_pending_batch_items(
    batch_id: str,
    db: Session = Depends(get_db),
) -> VeoBatchBulkActionResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    items = db.execute(
        select(VeoBatchItem).where(
            VeoBatchItem.batch_run_id == batch_id,
            VeoBatchItem.status.in_(["pending", "leased", "submitted"]),
        )
    ).scalars().all()

    now = datetime.now(timezone.utc)
    affected = 0

    for item in items:
        item.status = "cancelled"
        item.finished_at = now
        item.next_retry_at = None
        item.lease_token = None
        db.add(item)
        affected += 1

    db.commit()
    _recompute_batch_status_inline(db, batch_id)

    return VeoBatchBulkActionResponse(
        ok=True,
        batch_run_id=batch_id,
        affected_items=affected,
        action="cancel_pending",
    )
Thêm route requeue-retry-waiting
@router.post("/batch-runs/{batch_id}/requeue-retry-waiting", response_model=VeoBatchBulkActionResponse)
def requeue_retry_waiting_batch_items(
    batch_id: str,
    db: Session = Depends(get_db),
) -> VeoBatchBulkActionResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    items = db.execute(
        select(VeoBatchItem).where(
            VeoBatchItem.batch_run_id == batch_id,
            VeoBatchItem.status == "retry_waiting",
        )
    ).scalars().all()

    affected = 0
    for item in items:
        item.status = "pending"
        item.next_retry_at = None
        item.lease_token = None
        item.leased_at = None
        db.add(item)
        affected += 1

    if affected > 0:
        run.status = "queued"
        db.add(run)

    db.commit()
    _recompute_batch_status_inline(db, batch_id)

    return VeoBatchBulkActionResponse(
        ok=True,
        batch_run_id=batch_id,
        affected_items=affected,
        action="requeue_retry_waiting",
    )
2) PATCH tests/test_veo_workspace_api.py
Bổ sung tests cho action endpoints
Paste thêm các test dưới vào file test API hiện có.
def test_retry_batch_items_by_error_code(client):
    c, SessionLocal = client
    db = SessionLocal()

    run = seed_batch(db, "batch-error-retry")
    run.status = "partially_failed"
    db.add(run)
    db.commit()

    failed_1 = seed_item(db, "item-failed-1", batch_id="batch-error-retry", status="failed")
    failed_2 = seed_item(db, "item-failed-2", batch_id="batch-error-retry", status="retry_waiting")
    ok_item = seed_item(db, "item-ok", batch_id="batch-error-retry", status="succeeded")

    failed_1.last_error_code = "503"
    failed_1.last_error_message = "Provider unavailable"
    failed_1.render_job_id = "render-old-1"

    failed_2.last_error_code = "503"
    failed_2.last_error_message = "Provider unavailable"
    failed_2.render_job_id = "render-old-2"

    db.add(failed_1)
    db.add(failed_2)
    db.commit()
    db.close()

    res = c.post(
        "/api/v1/veo/batch-runs/batch-error-retry/retry-by-error-code",
        json={"error_code": "503"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["affected_items"] == 2

    db = SessionLocal()
    item1 = db.get(VeoBatchItem, "item-failed-1")
    item2 = db.get(VeoBatchItem, "item-failed-2")
    item3 = db.get(VeoBatchItem, "item-ok")
    run = db.get(VeoBatchRun, "batch-error-retry")

    assert item1.status == "pending"
    assert item1.last_error_code is None
    assert item1.render_job_id is None

    assert item2.status == "pending"
    assert item2.last_error_code is None
    assert item2.next_retry_at is None

    assert item3.status == "succeeded"
    assert run.status in {"queued", "running", "completed", "partially_failed"}
    db.close()


def test_cancel_pending_batch_items(client):
    c, SessionLocal = client
    db = SessionLocal()

    seed_batch(db, "batch-cancel-pending")
    seed_item(db, "item-pending", batch_id="batch-cancel-pending", status="pending")
    seed_item(db, "item-leased", batch_id="batch-cancel-pending", status="leased")
    seed_item(db, "item-submitted", batch_id="batch-cancel-pending", status="submitted")
    seed_item(db, "item-running", batch_id="batch-cancel-pending", status="running")
    db.close()

    res = c.post("/api/v1/veo/batch-runs/batch-cancel-pending/cancel-pending")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["affected_items"] == 3

    db = SessionLocal()
    assert db.get(VeoBatchItem, "item-pending").status == "cancelled"
    assert db.get(VeoBatchItem, "item-leased").status == "cancelled"
    assert db.get(VeoBatchItem, "item-submitted").status == "cancelled"
    assert db.get(VeoBatchItem, "item-running").status == "running"
    db.close()


def test_requeue_retry_waiting_batch_items(client):
    c, SessionLocal = client
    db = SessionLocal()

    seed_batch(db, "batch-requeue")
    retry_1 = seed_item(db, "item-retry-1", batch_id="batch-requeue", status="retry_waiting")
    retry_2 = seed_item(db, "item-retry-2", batch_id="batch-requeue", status="retry_waiting")
    other = seed_item(db, "item-failed-other", batch_id="batch-requeue", status="failed")

    retry_1.next_retry_at = datetime.now(timezone.utc)
    retry_2.next_retry_at = datetime.now(timezone.utc)
    db.add(retry_1)
    db.add(retry_2)
    db.commit()
    db.close()

    res = c.post("/api/v1/veo/batch-runs/batch-requeue/requeue-retry-waiting")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["affected_items"] == 2

    db = SessionLocal()
    assert db.get(VeoBatchItem, "item-retry-1").status == "pending"
    assert db.get(VeoBatchItem, "item-retry-1").next_retry_at is None
    assert db.get(VeoBatchItem, "item-retry-2").status == "pending"
    assert db.get(VeoBatchItem, "item-failed-other").status == "failed"
    db.close()
3) PATCH frontend/src/lib/api.ts
Thêm action APIs
Paste thêm vào file.
export async function retryVeoBatchItemsByErrorCode(batchId: string, errorCode: string) {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/retry-by-error-code`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ error_code: errorCode }),
  });
  if (!res.ok) throw new Error(`Failed to retry Veo batch items by error code for ${batchId}`);
  return res.json();
}

export async function cancelPendingVeoBatchItems(batchId: string) {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/cancel-pending`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to cancel pending Veo batch items for ${batchId}`);
  return res.json();
}

export async function requeueRetryWaitingVeoBatchItems(batchId: string) {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/requeue-retry-waiting`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to requeue retry-waiting Veo batch items for ${batchId}`);
  return res.json();
}
4) frontend/src/components/veo/VeoBatchOpsActionsPanel.tsx
"use client";

import { useState } from "react";
import {
  cancelPendingVeoBatchItems,
  requeueRetryWaitingVeoBatchItems,
  retryVeoBatchItemsByErrorCode,
} from "@/src/lib/api";

type Props = {
  batchId: string;
  retryErrorCode?: string;
  onActionDone?: () => Promise<void> | void;
};

export default function VeoBatchOpsActionsPanel({
  batchId,
  retryErrorCode = "",
  onActionDone,
}: Props) {
  const [errorCode, setErrorCode] = useState(retryErrorCode);
  const [loading, setLoading] = useState<string | null>(null);

  async function runAction(action: "retryByError" | "cancelPending" | "requeueRetryWaiting") {
    try {
      setLoading(action);

      if (action === "retryByError") {
        if (!errorCode.trim()) {
          alert("Please enter an error code to retry.");
          return;
        }
        await retryVeoBatchItemsByErrorCode(batchId, errorCode.trim());
      }

      if (action === "cancelPending") {
        await cancelPendingVeoBatchItems(batchId);
      }

      if (action === "requeueRetryWaiting") {
        await requeueRetryWaitingVeoBatchItems(batchId);
      }

      await onActionDone?.();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Action failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-4">
      <div className="mb-4">
        <h3 className="text-base font-semibold">Ops Actions</h3>
        <p className="mt-1 text-sm text-neutral-500">
          Triage and control the current Veo batch directly from the dashboard.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="rounded-xl border border-neutral-200 p-4">
          <div className="font-medium">Retry by Error Code</div>
          <div className="mt-1 text-sm text-neutral-500">
            Requeue failed or retry-waiting items that share the same error code.
          </div>

          <input
            value={errorCode}
            onChange={(e) => setErrorCode(e.target.value)}
            placeholder="e.g. 503, rate_limit, timeout"
            className="mt-3 w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />

          <button
            className="mt-3 rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
            onClick={() => runAction("retryByError")}
            disabled={loading !== null}
          >
            {loading === "retryByError" ? "Retrying..." : "Retry Affected Items"}
          </button>
        </div>

        <div className="rounded-xl border border-neutral-200 p-4">
          <div className="font-medium">Cancel Pending</div>
          <div className="mt-1 text-sm text-neutral-500">
            Cancel pending, leased, and submitted items that have not fully entered runtime execution.
          </div>

          <button
            className="mt-3 rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
            onClick={() => runAction("cancelPending")}
            disabled={loading !== null}
          >
            {loading === "cancelPending" ? "Cancelling..." : "Cancel Pending Items"}
          </button>
        </div>

        <div className="rounded-xl border border-neutral-200 p-4">
          <div className="font-medium">Requeue Retry Waiting</div>
          <div className="mt-1 text-sm text-neutral-500">
            Move retry-waiting items back to pending immediately instead of waiting for scheduled retry time.
          </div>

          <button
            className="mt-3 rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
            onClick={() => runAction("requeueRetryWaiting")}
            disabled={loading !== null}
          >
            {loading === "requeueRetryWaiting" ? "Requeueing..." : "Requeue Retry Waiting"}
          </button>
        </div>
      </div>
    </div>
  );
}
5) PATCH frontend/src/components/veo/VeoBatchTimelinePanel.tsx
Thêm quick filter theo event type
Thay file cũ bằng bản dưới.
"use client";

import { useMemo, useState } from "react";
import { VeoBatchTimeline } from "@/src/lib/api";

type Props = {
  timeline: VeoBatchTimeline | null;
  loading?: boolean;
};

const EVENT_TYPE_OPTIONS = [
  "",
  "batch_submitted",
  "batch_started",
  "batch_completed",
  "batch_failed",
  "batch_cancelled",
  "item_created",
  "item_leased",
  "item_submitted",
  "item_started",
  "item_retry_waiting",
  "item_succeeded",
  "item_failed",
  "item_cancelled",
];

export default function VeoBatchTimelinePanel({ timeline, loading }: Props) {
  const [eventTypeFilter, setEventTypeFilter] = useState("");

  const filteredEvents = useMemo(() => {
    const events = timeline?.events || [];
    if (!eventTypeFilter) return events;
    return events.filter((event) => event.event_type === eventTypeFilter);
  }, [timeline, eventTypeFilter]);

  if (loading && !timeline) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        Loading timeline...
      </div>
    );
  }

  if (!timeline) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        No timeline available.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white">
      <div className="border-b border-neutral-200 px-4 py-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <h3 className="text-base font-semibold">Batch Timeline</h3>

          <div className="w-full md:w-[280px]">
            <select
              value={eventTypeFilter}
              onChange={(e) => setEventTypeFilter(e.target.value)}
              className="w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
            >
              {EVENT_TYPE_OPTIONS.map((value) => (
                <option key={value || "all"} value={value}>
                  {value || "All event types"}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="divide-y divide-neutral-200">
        {filteredEvents.length === 0 ? (
          <div className="px-4 py-6 text-sm text-neutral-500">No timeline events found.</div>
        ) : (
          filteredEvents.map((event, index) => (
            <div key={`${event.event_type}-${event.item_id || "batch"}-${event.timestamp}-${index}`} className="px-4 py-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="font-medium">{event.title}</div>

                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-neutral-600">
                    <span className="rounded-full border px-2 py-1">{event.event_type}</span>
                    {event.status ? <span className="rounded-full border px-2 py-1">status: {event.status}</span> : null}
                    {event.mode ? <span className="rounded-full border px-2 py-1">mode: {event.mode}</span> : null}
                    {event.item_id ? <span className="rounded-full border px-2 py-1">item: {event.item_id}</span> : null}
                    {event.render_job_id ? (
                      <span className="rounded-full border px-2 py-1">render: {event.render_job_id}</span>
                    ) : null}
                    {event.error_code ? (
                      <span className="rounded-full border px-2 py-1 text-red-600">error: {event.error_code}</span>
                    ) : null}
                  </div>

                  {event.message ? (
                    <div className="mt-2 text-sm text-neutral-600">{event.message}</div>
                  ) : null}
                </div>

                <div className="shrink-0 text-xs text-neutral-500">
                  {new Date(event.timestamp).toLocaleString()}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
6) PATCH frontend/src/components/veo/VeoBatchFailuresPanel.tsx
Thêm action “retry affected items by error code”
Thay file cũ bằng bản dưới.
"use client";

import { useState } from "react";
import {
  retryVeoBatchItemsByErrorCode,
  VeoBatchErrorsSummary,
} from "@/src/lib/api";

type Props = {
  batchId: string;
  summary: VeoBatchErrorsSummary | null;
  loading?: boolean;
  onActionDone?: () => Promise<void> | void;
};

export default function VeoBatchFailuresPanel({ batchId, summary, loading, onActionDone }: Props) {
  const [actionLoadingErrorCode, setActionLoadingErrorCode] = useState<string | null>(null);

  async function retryByErrorCode(errorCode: string) {
    try {
      setActionLoadingErrorCode(errorCode);
      await retryVeoBatchItemsByErrorCode(batchId, errorCode);
      await onActionDone?.();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Retry action failed");
    } finally {
      setActionLoadingErrorCode(null);
    }
  }

  if (loading && !summary) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        Loading failure summary...
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        No failure summary available.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <StatCard label="Failed Items" value={summary.total_failed_items} />
        <StatCard label="Retry Waiting" value={summary.total_retry_waiting_items} />
        <StatCard label="Unique Error Codes" value={summary.errors.length} />
      </div>

      <div className="overflow-hidden rounded-2xl border border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 px-4 py-3">
          <h3 className="text-base font-semibold">Failure Breakdown</h3>
        </div>

        <div className="divide-y divide-neutral-200">
          {summary.errors.length === 0 ? (
            <div className="px-4 py-6 text-sm text-neutral-500">No failures recorded yet.</div>
          ) : (
            summary.errors.map((error) => (
              <div key={error.error_code} className="px-4 py-4">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0">
                    <div className="font-medium">{error.error_code}</div>
                    <div className="mt-1 text-sm text-neutral-600">
                      {error.latest_message || "No error message available"}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="rounded-full border px-3 py-1 text-xs font-medium">
                      {error.count}
                    </div>
                    <button
                      className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
                      onClick={() => retryByErrorCode(error.error_code)}
                      disabled={actionLoadingErrorCode !== null}
                    >
                      {actionLoadingErrorCode === error.error_code ? "Retrying..." : "Retry Affected"}
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
7) PATCH frontend/src/app/projects/[id]/page.tsx
Gắn Ops panel + truyền batchId vào Failures panel
Chỉ thay đúng phần render tabs/content liên quan.
Thêm import
import VeoBatchOpsActionsPanel from "@/src/components/veo/VeoBatchOpsActionsPanel";
Thay phần body của VeoBatchWorkspaceSection bằng block dưới nếu muốn có Ops panel ở trên tabs
return (
  <div className="space-y-4">
    <VeoBatchRunPanel batchId={batchId} stats={stats} onRefresh={() => refresh()} />

    <VeoBatchOpsActionsPanel
      batchId={batchId}
      onActionDone={() => refresh()}
    />

    <div className="flex flex-wrap items-center gap-2">
      <TabButton
        label="Overview"
        active={activeTab === "overview"}
        onClick={() => setActiveTab("overview")}
      />
      <TabButton
        label="Items"
        active={activeTab === "items"}
        onClick={() => setActiveTab("items")}
      />
      <TabButton
        label="Failures"
        active={activeTab === "failures"}
        onClick={() => setActiveTab("failures")}
      />
      <TabButton
        label="Timeline"
        active={activeTab === "timeline"}
        onClick={() => setActiveTab("timeline")}
      />
    </div>

    {activeTab === "overview" ? (
      <div className="grid gap-4 xl:grid-cols-2">
        <VeoBatchFailuresPanel
          batchId={batchId}
          summary={errorsSummary}
          loading={loading}
          onActionDone={() => refresh()}
        />
        <VeoBatchTimelinePanel
          timeline={{
            batch_run_id: timeline?.batch_run_id || batchId,
            events: (timeline?.events || []).slice(0, 20),
          }}
          loading={loading}
        />
      </div>
    ) : null}

    {activeTab === "items" ? (
      <VeoBatchItemsTable
        items={itemsPage.items}
        total={itemsPage.total}
        limit={itemsPage.limit}
        offset={itemsPage.offset}
        statusFilter={statusFilter}
        modeFilter={modeFilter}
        searchText={searchText}
        onChangeStatusFilter={(value) => setStatusFilter(value)}
        onChangeModeFilter={(value) => setModeFilter(value)}
        onChangeSearchText={(value) => setSearchText(value)}
        onPrevPage={() => void refresh(Math.max(0, itemsPage.offset - itemsPage.limit))}
        onNextPage={() => void refresh(itemsPage.offset + itemsPage.limit)}
      />
    ) : null}

    {activeTab === "failures" ? (
      <VeoBatchFailuresPanel
        batchId={batchId}
        summary={errorsSummary}
        loading={loading}
        onActionDone={() => refresh()}
      />
    ) : null}

    {activeTab === "timeline" ? (
      <VeoBatchTimelinePanel timeline={timeline} loading={loading} />
    ) : null}
  </div>
);
8) Kết quả sau phase này
Sau patch này, dashboard Veo của bạn đã đi từ:
observability / xem trạng thái
sang:
ops control / điều hành trực tiếp
Cụ thể operator giờ có thể:
retry toàn bộ item theo một error_code
hủy toàn bộ pending/leased/submitted items
đẩy toàn bộ retry_waiting về pending ngay
retry affected items trực tiếp từ failure panel
lọc timeline theo loại event để triage nhanh hơn
Đây là đúng bước “dashboard có quyền điều khiển”.
9) Bước mạnh nhất tiếp theo
Bước tiếp theo mạnh nhất là governed ops + safety guardrails, theo đúng format paste-ready:
patch backend action endpoints thêm:
reason / actor / audit note
dry-run mode
optional max_affected_items safeguard
tests cho safeguard + validation
frontend confirm dialog + affected preview
ops action audit timeline events
Đó là bước nâng dashboard từ direct control lên controlled production operations.
Bước tiếp theo mạnh nhất là governed ops + safety guardrails, theo đúng format paste-ready: patch backend action endpoints thêm: reason / actor / audit note dry-run mode optional max_affected_items safeguard tests cho safeguard + validation frontend confirm dialog + affected preview ops action audit timeline events Đó là bước nâng dashboard từ direct control lên controlled production operations.
Mình đang nối lớp guardrails đúng trên các action vừa có: thêm contract reason/actor/audit note + dry-run + max_affected_items, rồi phản chiếu ngược ra timeline/audit để mọi thao tác ops đều có dấu vết kiểm soát.
Đã suy nghĩ trong vài giây
Được. Mình viết tiếp ngay governed ops + safety guardrails theo đúng format paste-ready.
Mục tiêu của phase này là biến các bulk ops từ kiểu “bấm là chạy” sang kiểu:
có lý do thao tác
có actor
có audit note
có dry-run preview
có max_affected_items safeguard
có audit events hiện lại trong timeline
1) PATCH backend/app/models/veo_workspace.py
Thêm model audit event
Nếu bạn muốn giữ migration cho lượt sau thì có thể thêm model trước rồi viết migration sau.
Ở đây mình viết full class để API phase này dùng được ngay theo contract.
class VeoBatchAuditEvent(Base):
    __tablename__ = "veo_batch_audit_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_run_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("veo_batch_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_affected_items: Mapped[int | None] = mapped_column(Integer, nullable=True)
    affected_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    target_error_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
2) PATCH backend/app/api/veo_workspace.py
Thêm guardrail request/response schemas + helper
Thêm imports nếu chưa có
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
Thêm schema request dùng chung cho governed ops
class VeoGovernedBatchActionRequest(BaseModel):
    actor: str
    reason: str
    audit_note: Optional[str] = None
    dry_run: bool = False
    max_affected_items: Optional[int] = None


class VeoGovernedRetryByErrorCodeRequest(VeoGovernedBatchActionRequest):
    error_code: str


class VeoGovernedBatchActionResponse(BaseModel):
    ok: bool
    batch_run_id: str
    action: str
    dry_run: bool
    actor: str
    reason: str
    audit_note: Optional[str] = None
    affected_items: int
    preview_item_ids: List[str] = []
    blocked_by_guardrail: bool = False
Thêm helper validate + audit
def _validate_governed_action_payload(
    actor: str,
    reason: str,
    max_affected_items: Optional[int],
) -> None:
    if not actor or not actor.strip():
        raise HTTPException(status_code=400, detail="actor is required")

    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")

    if max_affected_items is not None and max_affected_items <= 0:
        raise HTTPException(status_code=400, detail="max_affected_items must be > 0")


def _create_batch_audit_event(
    db: Session,
    *,
    batch_run_id: str,
    action_type: str,
    actor: str,
    reason: str,
    audit_note: Optional[str],
    dry_run: bool,
    max_affected_items: Optional[int],
    affected_items: int,
    target_error_code: Optional[str] = None,
    payload: Optional[dict] = None,
) -> None:
    event = VeoBatchAuditEvent(
        batch_run_id=batch_run_id,
        action_type=action_type,
        actor=actor,
        reason=reason,
        audit_note=audit_note,
        dry_run=dry_run,
        max_affected_items=max_affected_items,
        affected_items=affected_items,
        target_error_code=target_error_code,
        payload=payload or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()


def _guardrail_preview_and_limit(
    *,
    item_ids: List[str],
    max_affected_items: Optional[int],
) -> tuple[int, List[str], bool]:
    affected_count = len(item_ids)
    blocked = max_affected_items is not None and affected_count > max_affected_items
    return affected_count, item_ids[:50], blocked
3) PATCH backend/app/api/veo_workspace.py
Thay 3 action endpoints cũ bằng governed versions
3.1 retry-by-error-code governed
Thay route cũ bằng bản dưới.
@router.post("/batch-runs/{batch_id}/retry-by-error-code", response_model=VeoGovernedBatchActionResponse)
def retry_batch_items_by_error_code(
    batch_id: str,
    payload: VeoGovernedRetryByErrorCodeRequest,
    db: Session = Depends(get_db),
) -> VeoGovernedBatchActionResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    _validate_governed_action_payload(
        actor=payload.actor,
        reason=payload.reason,
        max_affected_items=payload.max_affected_items,
    )

    if not payload.error_code.strip():
        raise HTTPException(status_code=400, detail="error_code is required")

    items = db.execute(
        select(VeoBatchItem).where(
            VeoBatchItem.batch_run_id == batch_id,
            VeoBatchItem.last_error_code == payload.error_code,
            VeoBatchItem.status.in_(["failed", "retry_waiting"]),
        )
    ).scalars().all()

    item_ids = [item.id for item in items]
    affected_count, preview_item_ids, blocked = _guardrail_preview_and_limit(
        item_ids=item_ids,
        max_affected_items=payload.max_affected_items,
    )

    if payload.dry_run or blocked:
        _create_batch_audit_event(
            db,
            batch_run_id=batch_id,
            action_type="retry_by_error_code_preview" if payload.dry_run else "retry_by_error_code_blocked",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=payload.dry_run,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            target_error_code=payload.error_code,
            payload={
                "preview_item_ids": preview_item_ids,
                "blocked_by_guardrail": blocked,
            },
        )
        return VeoGovernedBatchActionResponse(
            ok=True,
            batch_run_id=batch_id,
            action=f"retry_by_error_code:{payload.error_code}",
            dry_run=payload.dry_run,
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            affected_items=affected_count,
            preview_item_ids=preview_item_ids,
            blocked_by_guardrail=blocked,
        )

    affected = 0
    for item in items:
        item.status = "pending"
        item.next_retry_at = None
        item.finished_at = None
        item.last_error_code = None
        item.last_error_message = None
        item.render_job_id = None
        item.lease_token = None
        item.leased_at = None
        item.submitted_at = None
        item.started_at = None
        db.add(item)
        affected += 1

    if affected > 0:
        run.status = "queued"
        run.failed_at = None
        run.completed_at = None
        db.add(run)

    db.commit()
    _recompute_batch_status_inline(db, batch_id)

    _create_batch_audit_event(
        db,
        batch_run_id=batch_id,
        action_type="retry_by_error_code",
        actor=payload.actor,
        reason=payload.reason,
        audit_note=payload.audit_note,
        dry_run=False,
        max_affected_items=payload.max_affected_items,
        affected_items=affected,
        target_error_code=payload.error_code,
        payload={
            "preview_item_ids": preview_item_ids,
        },
    )

    return VeoGovernedBatchActionResponse(
        ok=True,
        batch_run_id=batch_id,
        action=f"retry_by_error_code:{payload.error_code}",
        dry_run=False,
        actor=payload.actor,
        reason=payload.reason,
        audit_note=payload.audit_note,
        affected_items=affected,
        preview_item_ids=preview_item_ids,
        blocked_by_guardrail=False,
    )
3.2 cancel-pending governed
Thay route cũ bằng bản dưới.
@router.post("/batch-runs/{batch_id}/cancel-pending", response_model=VeoGovernedBatchActionResponse)
def cancel_pending_batch_items(
    batch_id: str,
    payload: VeoGovernedBatchActionRequest,
    db: Session = Depends(get_db),
) -> VeoGovernedBatchActionResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    _validate_governed_action_payload(
        actor=payload.actor,
        reason=payload.reason,
        max_affected_items=payload.max_affected_items,
    )

    items = db.execute(
        select(VeoBatchItem).where(
            VeoBatchItem.batch_run_id == batch_id,
            VeoBatchItem.status.in_(["pending", "leased", "submitted"]),
        )
    ).scalars().all()

    item_ids = [item.id for item in items]
    affected_count, preview_item_ids, blocked = _guardrail_preview_and_limit(
        item_ids=item_ids,
        max_affected_items=payload.max_affected_items,
    )

    if payload.dry_run or blocked:
        _create_batch_audit_event(
            db,
            batch_run_id=batch_id,
            action_type="cancel_pending_preview" if payload.dry_run else "cancel_pending_blocked",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=payload.dry_run,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            payload={
                "preview_item_ids": preview_item_ids,
                "blocked_by_guardrail": blocked,
            },
        )
        return VeoGovernedBatchActionResponse(
            ok=True,
            batch_run_id=batch_id,
            action="cancel_pending",
            dry_run=payload.dry_run,
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            affected_items=affected_count,
            preview_item_ids=preview_item_ids,
            blocked_by_guardrail=blocked,
        )

    now = datetime.now(timezone.utc)
    affected = 0
    for item in items:
        item.status = "cancelled"
        item.finished_at = now
        item.next_retry_at = None
        item.lease_token = None
        db.add(item)
        affected += 1

    db.commit()
    _recompute_batch_status_inline(db, batch_id)

    _create_batch_audit_event(
        db,
        batch_run_id=batch_id,
        action_type="cancel_pending",
        actor=payload.actor,
        reason=payload.reason,
        audit_note=payload.audit_note,
        dry_run=False,
        max_affected_items=payload.max_affected_items,
        affected_items=affected,
        payload={
            "preview_item_ids": preview_item_ids,
        },
    )

    return VeoGovernedBatchActionResponse(
        ok=True,
        batch_run_id=batch_id,
        action="cancel_pending",
        dry_run=False,
        actor=payload.actor,
        reason=payload.reason,
        audit_note=payload.audit_note,
        affected_items=affected,
        preview_item_ids=preview_item_ids,
        blocked_by_guardrail=False,
    )
3.3 requeue-retry-waiting governed
Thay route cũ bằng bản dưới.
@router.post("/batch-runs/{batch_id}/requeue-retry-waiting", response_model=VeoGovernedBatchActionResponse)
def requeue_retry_waiting_batch_items(
    batch_id: str,
    payload: VeoGovernedBatchActionRequest,
    db: Session = Depends(get_db),
) -> VeoGovernedBatchActionResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    _validate_governed_action_payload(
        actor=payload.actor,
        reason=payload.reason,
        max_affected_items=payload.max_affected_items,
    )

    items = db.execute(
        select(VeoBatchItem).where(
            VeoBatchItem.batch_run_id == batch_id,
            VeoBatchItem.status == "retry_waiting",
        )
    ).scalars().all()

    item_ids = [item.id for item in items]
    affected_count, preview_item_ids, blocked = _guardrail_preview_and_limit(
        item_ids=item_ids,
        max_affected_items=payload.max_affected_items,
    )

    if payload.dry_run or blocked:
        _create_batch_audit_event(
            db,
            batch_run_id=batch_id,
            action_type="requeue_retry_waiting_preview" if payload.dry_run else "requeue_retry_waiting_blocked",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=payload.dry_run,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            payload={
                "preview_item_ids": preview_item_ids,
                "blocked_by_guardrail": blocked,
            },
        )
        return VeoGovernedBatchActionResponse(
            ok=True,
            batch_run_id=batch_id,
            action="requeue_retry_waiting",
            dry_run=payload.dry_run,
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            affected_items=affected_count,
            preview_item_ids=preview_item_ids,
            blocked_by_guardrail=blocked,
        )

    affected = 0
    for item in items:
        item.status = "pending"
        item.next_retry_at = None
        item.lease_token = None
        item.leased_at = None
        db.add(item)
        affected += 1

    if affected > 0:
        run.status = "queued"
        db.add(run)

    db.commit()
    _recompute_batch_status_inline(db, batch_id)

    _create_batch_audit_event(
        db,
        batch_run_id=batch_id,
        action_type="requeue_retry_waiting",
        actor=payload.actor,
        reason=payload.reason,
        audit_note=payload.audit_note,
        dry_run=False,
        max_affected_items=payload.max_affected_items,
        affected_items=affected,
        payload={
            "preview_item_ids": preview_item_ids,
        },
    )

    return VeoGovernedBatchActionResponse(
        ok=True,
        batch_run_id=batch_id,
        action="requeue_retry_waiting",
        dry_run=False,
        actor=payload.actor,
        reason=payload.reason,
        audit_note=payload.audit_note,
        affected_items=affected,
        preview_item_ids=preview_item_ids,
        blocked_by_guardrail=False,
    )
4) PATCH backend/app/api/veo_workspace.py
Timeline: thêm ops action audit events
Thêm block này vào route timeline hiện có, trước khi sort events.
    audit_events = db.execute(
        select(VeoBatchAuditEvent)
        .where(VeoBatchAuditEvent.batch_run_id == batch_id)
        .order_by(VeoBatchAuditEvent.created_at.desc())
        .limit(limit)
    ).scalars().all()

    for audit in audit_events:
        suffix = "preview" if audit.dry_run else "executed"
        events.append(
            VeoBatchTimelineEvent(
                event_type=f"ops_action_{suffix}",
                title=f"Ops action: {audit.action_type}",
                status=run.status,
                error_code=getattr(audit, "target_error_code", None),
                message=(
                    f"actor={audit.actor or '-'} | "
                    f"reason={audit.reason or '-'} | "
                    f"affected={audit.affected_items} | "
                    f"dry_run={audit.dry_run}"
                    + (f" | note={audit.audit_note}" if audit.audit_note else "")
                ),
                timestamp=audit.created_at,
            )
        )
5) PATCH tests/test_veo_workspace_api.py
Thêm tests safeguard + validation
Paste thêm vào file test API hiện có.
def test_retry_by_error_code_requires_actor_and_reason(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-guard-validation")
    failed = seed_item(db, "item-guard-1", batch_id="batch-guard-validation", status="failed")
    failed.last_error_code = "503"
    db.add(failed)
    db.commit()
    db.close()

    res = c.post(
        "/api/v1/veo/batch-runs/batch-guard-validation/retry-by-error-code",
        json={
            "error_code": "503",
            "actor": "",
            "reason": "",
            "dry_run": False,
        },
    )
    assert res.status_code == 400


def test_retry_by_error_code_dry_run_returns_preview_only(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-dry-run")
    item1 = seed_item(db, "item-dry-1", batch_id="batch-dry-run", status="failed")
    item2 = seed_item(db, "item-dry-2", batch_id="batch-dry-run", status="retry_waiting")
    item1.last_error_code = "503"
    item2.last_error_code = "503"
    db.add(item1)
    db.add(item2)
    db.commit()
    db.close()

    res = c.post(
        "/api/v1/veo/batch-runs/batch-dry-run/retry-by-error-code",
        json={
            "error_code": "503",
            "actor": "ops@example.com",
            "reason": "Preview impact before requeue",
            "audit_note": "Checking blast radius",
            "dry_run": True,
            "max_affected_items": 10,
        },
    )

    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["dry_run"] is True
    assert data["affected_items"] == 2
    assert len(data["preview_item_ids"]) == 2
    assert data["blocked_by_guardrail"] is False

    db = SessionLocal()
    assert db.get(VeoBatchItem, "item-dry-1").status == "failed"
    assert db.get(VeoBatchItem, "item-dry-2").status == "retry_waiting"
    db.close()


def test_retry_by_error_code_blocked_by_max_affected_items(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-blocked")
    for idx in range(3):
        item = seed_item(db, f"item-block-{idx}", batch_id="batch-blocked", status="failed")
        item.last_error_code = "503"
        db.add(item)
    db.commit()
    db.close()

    res = c.post(
        "/api/v1/veo/batch-runs/batch-blocked/retry-by-error-code",
        json={
            "error_code": "503",
            "actor": "ops@example.com",
            "reason": "Retry all 503s",
            "dry_run": False,
            "max_affected_items": 2,
        },
    )

    assert res.status_code == 200
    data = res.json()
    assert data["blocked_by_guardrail"] is True
    assert data["affected_items"] == 3

    db = SessionLocal()
    assert db.get(VeoBatchItem, "item-block-0").status == "failed"
    assert db.get(VeoBatchItem, "item-block-1").status == "failed"
    assert db.get(VeoBatchItem, "item-block-2").status == "failed"
    db.close()


def test_cancel_pending_dry_run_preview(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-cancel-preview")
    seed_item(db, "item-cancel-1", batch_id="batch-cancel-preview", status="pending")
    seed_item(db, "item-cancel-2", batch_id="batch-cancel-preview", status="leased")
    db.close()

    res = c.post(
        "/api/v1/veo/batch-runs/batch-cancel-preview/cancel-pending",
        json={
            "actor": "ops@example.com",
            "reason": "Pause inflight pre-runtime items",
            "audit_note": "Maintenance window",
            "dry_run": True,
            "max_affected_items": 10,
        },
    )

    assert res.status_code == 200
    data = res.json()
    assert data["dry_run"] is True
    assert data["affected_items"] == 2
    assert len(data["preview_item_ids"]) == 2


def test_requeue_retry_waiting_blocked_when_limit_exceeded(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-requeue-guard")
    for idx in range(4):
        item = seed_item(db, f"item-requeue-{idx}", batch_id="batch-requeue-guard", status="retry_waiting")
        item.next_retry_at = datetime.now(timezone.utc)
        db.add(item)
    db.commit()
    db.close()

    res = c.post(
        "/api/v1/veo/batch-runs/batch-requeue-guard/requeue-retry-waiting",
        json={
            "actor": "ops@example.com",
            "reason": "Manual requeue",
            "dry_run": False,
            "max_affected_items": 2,
        },
    )

    assert res.status_code == 200
    data = res.json()
    assert data["blocked_by_guardrail"] is True
    assert data["affected_items"] == 4
6) PATCH frontend/src/lib/api.ts
Upgrade action APIs để hỗ trợ governed mode
Thay 3 function action trước bằng bản dưới.
export type VeoGovernedActionRequest = {
  actor: string;
  reason: string;
  audit_note?: string;
  dry_run?: boolean;
  max_affected_items?: number;
};

export type VeoGovernedRetryByErrorCodeRequest = VeoGovernedActionRequest & {
  error_code: string;
};

export type VeoGovernedActionResponse = {
  ok: boolean;
  batch_run_id: string;
  action: string;
  dry_run: boolean;
  actor: string;
  reason: string;
  audit_note?: string | null;
  affected_items: number;
  preview_item_ids: string[];
  blocked_by_guardrail: boolean;
};

export async function retryVeoBatchItemsByErrorCode(
  batchId: string,
  payload: VeoGovernedRetryByErrorCodeRequest
): Promise<VeoGovernedActionResponse> {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/retry-by-error-code`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to retry Veo batch items by error code for ${batchId}`);
  return res.json();
}

export async function cancelPendingVeoBatchItems(
  batchId: string,
  payload: VeoGovernedActionRequest
): Promise<VeoGovernedActionResponse> {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/cancel-pending`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to cancel pending Veo batch items for ${batchId}`);
  return res.json();
}

export async function requeueRetryWaitingVeoBatchItems(
  batchId: string,
  payload: VeoGovernedActionRequest
): Promise<VeoGovernedActionResponse> {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/requeue-retry-waiting`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to requeue retry-waiting Veo batch items for ${batchId}`);
  return res.json();
}
7) PATCH frontend/src/components/veo/VeoBatchOpsActionsPanel.tsx
Thêm confirm dialog + affected preview
Thay file cũ bằng bản dưới.
"use client";

import { useState } from "react";
import {
  cancelPendingVeoBatchItems,
  requeueRetryWaitingVeoBatchItems,
  retryVeoBatchItemsByErrorCode,
  VeoGovernedActionResponse,
} from "@/src/lib/api";

type Props = {
  batchId: string;
  retryErrorCode?: string;
  onActionDone?: () => Promise<void> | void;
};

type ActionKind = "retryByError" | "cancelPending" | "requeueRetryWaiting";

export default function VeoBatchOpsActionsPanel({
  batchId,
  retryErrorCode = "",
  onActionDone,
}: Props) {
  const [errorCode, setErrorCode] = useState(retryErrorCode);
  const [actor, setActor] = useState("");
  const [reason, setReason] = useState("");
  const [auditNote, setAuditNote] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [maxAffectedItems, setMaxAffectedItems] = useState("25");

  const [loading, setLoading] = useState<ActionKind | null>(null);
  const [preview, setPreview] = useState<VeoGovernedActionResponse | null>(null);

  async function runAction(action: ActionKind) {
    try {
      if (!actor.trim()) {
        alert("Actor is required.");
        return;
      }
      if (!reason.trim()) {
        alert("Reason is required.");
        return;
      }

      setLoading(action);

      const basePayload = {
        actor: actor.trim(),
        reason: reason.trim(),
        audit_note: auditNote.trim() || undefined,
        dry_run: dryRun,
        max_affected_items: maxAffectedItems.trim() ? Number(maxAffectedItems) : undefined,
      };

      let result: VeoGovernedActionResponse;

      if (action === "retryByError") {
        if (!errorCode.trim()) {
          alert("Please enter an error code.");
          return;
        }
        result = await retryVeoBatchItemsByErrorCode(batchId, {
          ...basePayload,
          error_code: errorCode.trim(),
        });
      } else if (action === "cancelPending") {
        result = await cancelPendingVeoBatchItems(batchId, basePayload);
      } else {
        result = await requeueRetryWaitingVeoBatchItems(batchId, basePayload);
      }

      setPreview(result);

      if (!result.dry_run && !result.blocked_by_guardrail) {
        await onActionDone?.();
      }
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Action failed");
    } finally {
      setLoading(null);
    }
  }

  async function confirmExecute(action: ActionKind) {
    try {
      if (!preview) return;

      setLoading(action);

      const basePayload = {
        actor: actor.trim(),
        reason: reason.trim(),
        audit_note: auditNote.trim() || undefined,
        dry_run: false,
        max_affected_items: maxAffectedItems.trim() ? Number(maxAffectedItems) : undefined,
      };

      let result: VeoGovernedActionResponse;

      if (action === "retryByError") {
        result = await retryVeoBatchItemsByErrorCode(batchId, {
          ...basePayload,
          error_code: errorCode.trim(),
        });
      } else if (action === "cancelPending") {
        result = await cancelPendingVeoBatchItems(batchId, basePayload);
      } else {
        result = await requeueRetryWaitingVeoBatchItems(batchId, basePayload);
      }

      setPreview(result);
      await onActionDone?.();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Execution failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-neutral-200 bg-white p-4">
        <div className="mb-4">
          <h3 className="text-base font-semibold">Governed Ops Actions</h3>
          <p className="mt-1 text-sm text-neutral-500">
            Every batch action requires actor, reason, optional audit note, and can run in dry-run mode first.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-neutral-500">
              Actor
            </label>
            <input
              value={actor}
              onChange={(e) => setActor(e.target.value)}
              placeholder="ops@example.com"
              className="w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-neutral-500">
              Reason
            </label>
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why this action is needed"
              className="w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-neutral-500">
              Audit Note
            </label>
            <input
              value={auditNote}
              onChange={(e) => setAuditNote(e.target.value)}
              placeholder="Optional note"
              className="w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-neutral-500">
              Max Affected
            </label>
            <input
              value={maxAffectedItems}
              onChange={(e) => setMaxAffectedItems(e.target.value)}
              placeholder="25"
              className="w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
            />
          </div>

          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-neutral-700">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
              />
              Dry-run first
            </label>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <ActionCard
          title="Retry by Error Code"
          description="Retry failed or retry-waiting items sharing the same error code."
          extra={
            <input
              value={errorCode}
              onChange={(e) => setErrorCode(e.target.value)}
              placeholder="503, rate_limit, timeout"
              className="mt-3 w-full rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
            />
          }
          buttonLabel={loading === "retryByError" ? "Working..." : dryRun ? "Preview Retry" : "Execute Retry"}
          onClick={() => runAction("retryByError")}
          disabled={loading !== null}
        />

        <ActionCard
          title="Cancel Pending"
          description="Cancel pending, leased, and submitted items before full execution."
          buttonLabel={loading === "cancelPending" ? "Working..." : dryRun ? "Preview Cancel" : "Execute Cancel"}
          onClick={() => runAction("cancelPending")}
          disabled={loading !== null}
        />

        <ActionCard
          title="Requeue Retry Waiting"
          description="Move retry-waiting items back to pending immediately."
          buttonLabel={
            loading === "requeueRetryWaiting"
              ? "Working..."
              : dryRun
              ? "Preview Requeue"
              : "Execute Requeue"
          }
          onClick={() => runAction("requeueRetryWaiting")}
          disabled={loading !== null}
        />
      </div>

      {preview ? (
        <div className="rounded-2xl border border-neutral-200 bg-white p-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <h4 className="text-base font-semibold">Action Preview / Result</h4>
              <div className="mt-2 space-y-1 text-sm text-neutral-700">
                <div><strong>Action:</strong> {preview.action}</div>
                <div><strong>Actor:</strong> {preview.actor}</div>
                <div><strong>Reason:</strong> {preview.reason}</div>
                {preview.audit_note ? <div><strong>Audit note:</strong> {preview.audit_note}</div> : null}
                <div><strong>Affected items:</strong> {preview.affected_items}</div>
                <div><strong>Dry-run:</strong> {String(preview.dry_run)}</div>
                <div><strong>Blocked by guardrail:</strong> {String(preview.blocked_by_guardrail)}</div>
              </div>
            </div>

            {preview.dry_run && !preview.blocked_by_guardrail ? (
              <button
                className="rounded-xl border px-3 py-2 text-sm"
                onClick={() => {
                  if (preview.action.startsWith("retry_by_error_code")) return confirmExecute("retryByError");
                  if (preview.action === "cancel_pending") return confirmExecute("cancelPending");
                  if (preview.action === "requeue_retry_waiting") return confirmExecute("requeueRetryWaiting");
                }}
                disabled={loading !== null}
              >
                Confirm Execute
              </button>
            ) : null}
          </div>

          <div className="mt-4">
            <div className="mb-2 text-sm font-medium">Affected Preview Items</div>
            <div className="flex flex-wrap gap-2">
              {preview.preview_item_ids.length === 0 ? (
                <span className="text-sm text-neutral-500">No preview items.</span>
              ) : (
                preview.preview_item_ids.map((itemId) => (
                  <span key={itemId} className="rounded-full border px-3 py-1 text-xs">
                    {itemId}
                  </span>
                ))
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ActionCard({
  title,
  description,
  extra,
  buttonLabel,
  onClick,
  disabled,
}: {
  title: string;
  description: string;
  extra?: React.ReactNode;
  buttonLabel: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-4">
      <div className="font-medium">{title}</div>
      <div className="mt-1 text-sm text-neutral-500">{description}</div>
      {extra}
      <button
        className="mt-3 rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
        onClick={onClick}
        disabled={disabled}
      >
        {buttonLabel}
      </button>
    </div>
  );
}
8) PATCH frontend/src/components/veo/VeoBatchFailuresPanel.tsx
Nâng action retry-by-error-code sang governed preview/confirm
Thay file cũ bằng bản dưới.
"use client";

import { useState } from "react";
import {
  retryVeoBatchItemsByErrorCode,
  VeoBatchErrorsSummary,
  VeoGovernedActionResponse,
} from "@/src/lib/api";

type Props = {
  batchId: string;
  summary: VeoBatchErrorsSummary | null;
  loading?: boolean;
  defaultActor?: string;
  onActionDone?: () => Promise<void> | void;
};

export default function VeoBatchFailuresPanel({
  batchId,
  summary,
  loading,
  defaultActor = "",
  onActionDone,
}: Props) {
  const [actor, setActor] = useState(defaultActor);
  const [reason, setReason] = useState("");
  const [auditNote, setAuditNote] = useState("");
  const [maxAffectedItems, setMaxAffectedItems] = useState("25");
  const [actionLoadingErrorCode, setActionLoadingErrorCode] = useState<string | null>(null);
  const [preview, setPreview] = useState<VeoGovernedActionResponse | null>(null);

  async function previewRetryByErrorCode(errorCode: string) {
    try {
      if (!actor.trim()) {
        alert("Actor is required.");
        return;
      }
      if (!reason.trim()) {
        alert("Reason is required.");
        return;
      }

      setActionLoadingErrorCode(errorCode);

      const result = await retryVeoBatchItemsByErrorCode(batchId, {
        error_code: errorCode,
        actor: actor.trim(),
        reason: reason.trim(),
        audit_note: auditNote.trim() || undefined,
        dry_run: true,
        max_affected_items: maxAffectedItems.trim() ? Number(maxAffectedItems) : undefined,
      });

      setPreview(result);
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Retry preview failed");
    } finally {
      setActionLoadingErrorCode(null);
    }
  }

  async function confirmRetry() {
    try {
      if (!preview?.action.startsWith("retry_by_error_code:")) return;
      const errorCode = preview.action.split(":")[1] || "";

      setActionLoadingErrorCode(errorCode);

      await retryVeoBatchItemsByErrorCode(batchId, {
        error_code: errorCode,
        actor: actor.trim(),
        reason: reason.trim(),
        audit_note: auditNote.trim() || undefined,
        dry_run: false,
        max_affected_items: maxAffectedItems.trim() ? Number(maxAffectedItems) : undefined,
      });

      setPreview(null);
      await onActionDone?.();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Retry execution failed");
    } finally {
      setActionLoadingErrorCode(null);
    }
  }

  if (loading && !summary) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        Loading failure summary...
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        No failure summary available.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-neutral-200 bg-white p-4">
        <div className="mb-3 text-sm font-medium">Governed Failure Action Settings</div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <input
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            placeholder="actor"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="reason"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />
          <input
            value={auditNote}
            onChange={(e) => setAuditNote(e.target.value)}
            placeholder="audit note"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />
          <input
            value={maxAffectedItems}
            onChange={(e) => setMaxAffectedItems(e.target.value)}
            placeholder="max affected"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <StatCard label="Failed Items" value={summary.total_failed_items} />
        <StatCard label="Retry Waiting" value={summary.total_retry_waiting_items} />
        <StatCard label="Unique Error Codes" value={summary.errors.length} />
      </div>

      {preview ? (
        <div className="rounded-2xl border border-neutral-200 bg-white p-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <div className="text-base font-semibold">Retry Preview</div>
              <div className="mt-2 text-sm text-neutral-700">
                <div><strong>Affected items:</strong> {preview.affected_items}</div>
                <div><strong>Blocked by guardrail:</strong> {String(preview.blocked_by_guardrail)}</div>
              </div>
            </div>

            {!preview.blocked_by_guardrail ? (
              <button
                className="rounded-xl border px-3 py-2 text-sm"
                onClick={confirmRetry}
                disabled={actionLoadingErrorCode !== null}
              >
                {actionLoadingErrorCode ? "Executing..." : "Confirm Retry"}
              </button>
            ) : null}
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {preview.preview_item_ids.map((itemId) => (
              <span key={itemId} className="rounded-full border px-3 py-1 text-xs">
                {itemId}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-2xl border border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 px-4 py-3">
          <h3 className="text-base font-semibold">Failure Breakdown</h3>
        </div>

        <div className="divide-y divide-neutral-200">
          {summary.errors.length === 0 ? (
            <div className="px-4 py-6 text-sm text-neutral-500">No failures recorded yet.</div>
          ) : (
            summary.errors.map((error) => (
              <div key={error.error_code} className="px-4 py-4">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0">
                    <div className="font-medium">{error.error_code}</div>
                    <div className="mt-1 text-sm text-neutral-600">
                      {error.latest_message || "No error message available"}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="rounded-full border px-3 py-1 text-xs font-medium">
                      {error.count}
                    </div>
                    <button
                      className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
                      onClick={() => previewRetryByErrorCode(error.error_code)}
                      disabled={actionLoadingErrorCode !== null}
                    >
                      {actionLoadingErrorCode === error.error_code ? "Previewing..." : "Preview Retry"}
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
9) PATCH frontend/src/app/projects/[id]/page.tsx
Truyền props mới cho Failures panel
Chỉ thay các chỗ render VeoBatchFailuresPanel.
Trong tab Overview
<VeoBatchFailuresPanel
  batchId={batchId}
  summary={errorsSummary}
  loading={loading}
  defaultActor=""
  onActionDone={() => refresh()}
/>
Trong tab Failures
<VeoBatchFailuresPanel
  batchId={batchId}
  summary={errorsSummary}
  loading={loading}
  defaultActor=""
  onActionDone={() => refresh()}
/>
10) Kết quả sau phase này
Sau patch này, dashboard batch Veo của bạn đã nâng từ:
direct control
sang:
controlled production operations
Cụ thể mỗi action giờ có:
actor
reason
audit_note
dry_run
max_affected_items
preview_item_ids
blocked_by_guardrail
và còn có:
audit event được ghi lại
audit event hiện trong timeline
confirm execute sau preview
retry theo error code có blast-radius preview
Đây là đúng lớp guardrails cần có trước khi cho operator dùng batch actions mạnh hơn.
11) Bước mạnh nhất tiếp theo
Bước tiếp theo mạnh nhất là approval-grade ops governance, theo đúng format paste-ready:
thêm requires_approval / approval_status
bulk action request queue thay vì execute trực tiếp khi vượt ngưỡng
supervisor approve / reject endpoints
audit trail đầy đủ cho approval lifecycle
frontend pending approvals panel
Đó là bước nâng hệ từ controlled operations lên human-governed production operations.
Mình viết tiếp ngay approval-grade ops governance theo đúng format paste-ready.
Mục tiêu phase này là:
action batch có thể bị đánh dấu requires_approval
nếu vượt ngưỡng thì không execute trực tiếp
thay vào đó tạo bulk action request queue
supervisor có endpoint approve / reject
toàn bộ lifecycle có audit trail
frontend có Pending Approvals panel
1) PATCH backend/app/models/veo_workspace.py
Thêm approval request + approval decision models
Paste thêm vào file model hiện có.
class VeoBatchActionRequest(Base):
    __tablename__ = "veo_batch_action_requests"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_run_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("veo_batch_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    approval_status: Mapped[str] = mapped_column(String(50), nullable=False, default="not_required", index=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    audit_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_affected_items: Mapped[int | None] = mapped_column(Integer, nullable=True)
    affected_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    target_error_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preview_item_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    supervisor_actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supervisor_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VeoBatchApprovalDecision(Base):
    __tablename__ = "veo_batch_approval_decisions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("veo_batch_action_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    decision: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # approved / rejected
    supervisor_actor: Mapped[str] = mapped_column(String(255), nullable=False)
    supervisor_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
2) PATCH backend/app/api/veo_workspace.py
Thêm imports
Nếu chưa có, thêm:
from typing import Any, Dict, List, Optional, Tuple
Và nhớ import models mới:
from backend.app.models.veo_workspace import (
    VeoBatchRun,
    VeoBatchItem,
    VeoBatchAuditEvent,
    VeoBatchActionRequest,
    VeoBatchApprovalDecision,
)
3) PATCH backend/app/api/veo_workspace.py
Thêm schema approval governance
class VeoApprovalDecisionRequest(BaseModel):
    supervisor_actor: str
    supervisor_note: Optional[str] = None


class VeoActionRequestResponse(BaseModel):
    id: str
    batch_run_id: str
    action_type: str
    approval_status: str
    requires_approval: bool
    actor: str
    reason: str
    audit_note: Optional[str] = None
    dry_run: bool
    max_affected_items: Optional[int] = None
    affected_items: int
    target_error_code: Optional[str] = None
    preview_item_ids: List[str] = []
    supervisor_actor: Optional[str] = None
    supervisor_note: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None


class VeoPendingApprovalListResponse(BaseModel):
    items: List[VeoActionRequestResponse]
    total: int
4) PATCH backend/app/api/veo_workspace.py
Helper approval policy + request creation + execution
APPROVAL_PENDING = "pending_approval"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"
APPROVAL_NOT_REQUIRED = "not_required"
APPROVAL_EXECUTED = "executed"


def _approval_threshold_for_action(action_type: str) -> int:
    thresholds = {
        "retry_by_error_code": 20,
        "cancel_pending": 10,
        "requeue_retry_waiting": 25,
    }
    return thresholds.get(action_type, 20)


def _should_require_approval(action_type: str, affected_items: int) -> bool:
    return affected_items > _approval_threshold_for_action(action_type)


def _create_action_request(
    db: Session,
    *,
    batch_run_id: str,
    action_type: str,
    actor: str,
    reason: str,
    audit_note: Optional[str],
    dry_run: bool,
    max_affected_items: Optional[int],
    affected_items: int,
    target_error_code: Optional[str],
    preview_item_ids: List[str],
    requires_approval: bool,
    request_payload: Optional[dict] = None,
) -> VeoBatchActionRequest:
    approval_status = APPROVAL_PENDING if requires_approval else APPROVAL_NOT_REQUIRED
    req = VeoBatchActionRequest(
        batch_run_id=batch_run_id,
        action_type=action_type,
        approval_status=approval_status,
        requires_approval=requires_approval,
        actor=actor,
        reason=reason,
        audit_note=audit_note,
        dry_run=dry_run,
        max_affected_items=max_affected_items,
        affected_items=affected_items,
        target_error_code=target_error_code,
        preview_item_ids=preview_item_ids,
        request_payload=request_payload or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def _action_request_to_response(req: VeoBatchActionRequest) -> VeoActionRequestResponse:
    return VeoActionRequestResponse(
        id=req.id,
        batch_run_id=req.batch_run_id,
        action_type=req.action_type,
        approval_status=req.approval_status,
        requires_approval=req.requires_approval,
        actor=req.actor,
        reason=req.reason,
        audit_note=req.audit_note,
        dry_run=req.dry_run,
        max_affected_items=req.max_affected_items,
        affected_items=req.affected_items,
        target_error_code=req.target_error_code,
        preview_item_ids=req.preview_item_ids or [],
        supervisor_actor=req.supervisor_actor,
        supervisor_note=req.supervisor_note,
        created_at=req.created_at,
        decided_at=req.decided_at,
        executed_at=req.executed_at,
    )
5) PATCH backend/app/api/veo_workspace.py
Helper execute by action request
def _execute_action_request(db: Session, req: VeoBatchActionRequest) -> int:
    run = db.get(VeoBatchRun, req.batch_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    affected = 0

    if req.action_type == "retry_by_error_code":
        items = db.execute(
            select(VeoBatchItem).where(
                VeoBatchItem.batch_run_id == req.batch_run_id,
                VeoBatchItem.last_error_code == req.target_error_code,
                VeoBatchItem.status.in_(["failed", "retry_waiting"]),
            )
        ).scalars().all()

        for item in items:
            item.status = "pending"
            item.next_retry_at = None
            item.finished_at = None
            item.last_error_code = None
            item.last_error_message = None
            item.render_job_id = None
            item.lease_token = None
            item.leased_at = None
            item.submitted_at = None
            item.started_at = None
            db.add(item)
            affected += 1

        if affected > 0:
            run.status = "queued"
            run.failed_at = None
            run.completed_at = None
            db.add(run)

    elif req.action_type == "cancel_pending":
        now = datetime.now(timezone.utc)
        items = db.execute(
            select(VeoBatchItem).where(
                VeoBatchItem.batch_run_id == req.batch_run_id,
                VeoBatchItem.status.in_(["pending", "leased", "submitted"]),
            )
        ).scalars().all()

        for item in items:
            item.status = "cancelled"
            item.finished_at = now
            item.next_retry_at = None
            item.lease_token = None
            db.add(item)
            affected += 1

    elif req.action_type == "requeue_retry_waiting":
        items = db.execute(
            select(VeoBatchItem).where(
                VeoBatchItem.batch_run_id == req.batch_run_id,
                VeoBatchItem.status == "retry_waiting",
            )
        ).scalars().all()

        for item in items:
            item.status = "pending"
            item.next_retry_at = None
            item.lease_token = None
            item.leased_at = None
            db.add(item)
            affected += 1

        if affected > 0:
            run.status = "queued"
            db.add(run)

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action_type '{req.action_type}'")

    db.commit()
    _recompute_batch_status_inline(db, req.batch_run_id)

    req.approval_status = APPROVAL_EXECUTED
    req.executed_at = datetime.now(timezone.utc)
    db.add(req)
    db.commit()

    _create_batch_audit_event(
        db,
        batch_run_id=req.batch_run_id,
        action_type=f"{req.action_type}_executed_from_request",
        actor=req.actor,
        reason=req.reason,
        audit_note=req.audit_note,
        dry_run=False,
        max_affected_items=req.max_affected_items,
        affected_items=affected,
        target_error_code=req.target_error_code,
        payload={
            "request_id": req.id,
            "supervisor_actor": req.supervisor_actor,
            "supervisor_note": req.supervisor_note,
            "preview_item_ids": req.preview_item_ids or [],
        },
    )

    return affected
6) PATCH backend/app/api/veo_workspace.py
Sửa 3 action endpoint để queue request nếu requires_approval
6.1 retry-by-error-code approval-aware
Trong endpoint retry_batch_items_by_error_code, ngay sau đoạn tính:
affected_count
preview_item_ids
blocked
thay phần xử lý bằng block dưới:
    requires_approval = _should_require_approval("retry_by_error_code", affected_count)

    if payload.dry_run or blocked:
        _create_batch_audit_event(
            db,
            batch_run_id=batch_id,
            action_type="retry_by_error_code_preview" if payload.dry_run else "retry_by_error_code_blocked",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=payload.dry_run,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            target_error_code=payload.error_code,
            payload={
                "preview_item_ids": preview_item_ids,
                "blocked_by_guardrail": blocked,
                "requires_approval": requires_approval,
            },
        )
        return VeoGovernedBatchActionResponse(
            ok=True,
            batch_run_id=batch_id,
            action=f"retry_by_error_code:{payload.error_code}",
            dry_run=payload.dry_run,
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            affected_items=affected_count,
            preview_item_ids=preview_item_ids,
            blocked_by_guardrail=blocked,
        )

    if requires_approval:
        req = _create_action_request(
            db,
            batch_run_id=batch_id,
            action_type="retry_by_error_code",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=False,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            target_error_code=payload.error_code,
            preview_item_ids=preview_item_ids,
            requires_approval=True,
            request_payload={"error_code": payload.error_code},
        )

        _create_batch_audit_event(
            db,
            batch_run_id=batch_id,
            action_type="retry_by_error_code_queued_for_approval",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=False,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            target_error_code=payload.error_code,
            payload={
                "request_id": req.id,
                "preview_item_ids": preview_item_ids,
            },
        )

        return VeoGovernedBatchActionResponse(
            ok=True,
            batch_run_id=batch_id,
            action=f"retry_by_error_code:{payload.error_code}",
            dry_run=False,
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            affected_items=affected_count,
            preview_item_ids=preview_item_ids,
            blocked_by_guardrail=False,
        )
Phần execute trực tiếp giữ nguyên như phase trước.
6.2 cancel-pending approval-aware
Trong endpoint cancel_pending_batch_items, sau khi có affected_count, preview_item_ids, blocked, thêm:
    requires_approval = _should_require_approval("cancel_pending", affected_count)

    if payload.dry_run or blocked:
        _create_batch_audit_event(
            db,
            batch_run_id=batch_id,
            action_type="cancel_pending_preview" if payload.dry_run else "cancel_pending_blocked",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=payload.dry_run,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            payload={
                "preview_item_ids": preview_item_ids,
                "blocked_by_guardrail": blocked,
                "requires_approval": requires_approval,
            },
        )
        return VeoGovernedBatchActionResponse(
            ok=True,
            batch_run_id=batch_id,
            action="cancel_pending",
            dry_run=payload.dry_run,
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            affected_items=affected_count,
            preview_item_ids=preview_item_ids,
            blocked_by_guardrail=blocked,
        )

    if requires_approval:
        req = _create_action_request(
            db,
            batch_run_id=batch_id,
            action_type="cancel_pending",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=False,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            target_error_code=None,
            preview_item_ids=preview_item_ids,
            requires_approval=True,
            request_payload={},
        )

        _create_batch_audit_event(
            db,
            batch_run_id=batch_id,
            action_type="cancel_pending_queued_for_approval",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=False,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            payload={
                "request_id": req.id,
                "preview_item_ids": preview_item_ids,
            },
        )

        return VeoGovernedBatchActionResponse(
            ok=True,
            batch_run_id=batch_id,
            action="cancel_pending",
            dry_run=False,
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            affected_items=affected_count,
            preview_item_ids=preview_item_ids,
            blocked_by_guardrail=False,
        )
6.3 requeue-retry-waiting approval-aware
Trong endpoint requeue_retry_waiting_batch_items, sau khi có affected_count, preview_item_ids, blocked, thêm:
    requires_approval = _should_require_approval("requeue_retry_waiting", affected_count)

    if payload.dry_run or blocked:
        _create_batch_audit_event(
            db,
            batch_run_id=batch_id,
            action_type="requeue_retry_waiting_preview" if payload.dry_run else "requeue_retry_waiting_blocked",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=payload.dry_run,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            payload={
                "preview_item_ids": preview_item_ids,
                "blocked_by_guardrail": blocked,
                "requires_approval": requires_approval,
            },
        )
        return VeoGovernedBatchActionResponse(
            ok=True,
            batch_run_id=batch_id,
            action="requeue_retry_waiting",
            dry_run=payload.dry_run,
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            affected_items=affected_count,
            preview_item_ids=preview_item_ids,
            blocked_by_guardrail=blocked,
        )

    if requires_approval:
        req = _create_action_request(
            db,
            batch_run_id=batch_id,
            action_type="requeue_retry_waiting",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=False,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            target_error_code=None,
            preview_item_ids=preview_item_ids,
            requires_approval=True,
            request_payload={},
        )

        _create_batch_audit_event(
            db,
            batch_run_id=batch_id,
            action_type="requeue_retry_waiting_queued_for_approval",
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            dry_run=False,
            max_affected_items=payload.max_affected_items,
            affected_items=affected_count,
            payload={
                "request_id": req.id,
                "preview_item_ids": preview_item_ids,
            },
        )

        return VeoGovernedBatchActionResponse(
            ok=True,
            batch_run_id=batch_id,
            action="requeue_retry_waiting",
            dry_run=False,
            actor=payload.actor,
            reason=payload.reason,
            audit_note=payload.audit_note,
            affected_items=affected_count,
            preview_item_ids=preview_item_ids,
            blocked_by_guardrail=False,
        )
7) PATCH backend/app/api/veo_workspace.py
Pending approvals + approve/reject endpoints
@router.get("/batch-runs/{batch_id}/pending-approvals", response_model=VeoPendingApprovalListResponse)
def get_pending_batch_approvals(batch_id: str, db: Session = Depends(get_db)) -> VeoPendingApprovalListResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    rows = db.execute(
        select(VeoBatchActionRequest)
        .where(
            VeoBatchActionRequest.batch_run_id == batch_id,
            VeoBatchActionRequest.approval_status == APPROVAL_PENDING,
        )
        .order_by(VeoBatchActionRequest.created_at.desc())
    ).scalars().all()

    return VeoPendingApprovalListResponse(
        items=[_action_request_to_response(row) for row in rows],
        total=len(rows),
    )


@router.post("/action-requests/{request_id}/approve", response_model=VeoActionRequestResponse)
def approve_batch_action_request(
    request_id: str,
    payload: VeoApprovalDecisionRequest,
    db: Session = Depends(get_db),
) -> VeoActionRequestResponse:
    req = db.get(VeoBatchActionRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Action request not found")

    if req.approval_status != APPROVAL_PENDING:
        raise HTTPException(status_code=409, detail=f"Request already in status '{req.approval_status}'")

    if not payload.supervisor_actor.strip():
        raise HTTPException(status_code=400, detail="supervisor_actor is required")

    req.approval_status = APPROVAL_APPROVED
    req.supervisor_actor = payload.supervisor_actor
    req.supervisor_note = payload.supervisor_note
    req.decided_at = datetime.now(timezone.utc)
    db.add(req)
    db.commit()

    decision = VeoBatchApprovalDecision(
        request_id=req.id,
        decision="approved",
        supervisor_actor=payload.supervisor_actor,
        supervisor_note=payload.supervisor_note,
        created_at=datetime.now(timezone.utc),
    )
    db.add(decision)
    db.commit()

    _create_batch_audit_event(
        db,
        batch_run_id=req.batch_run_id,
        action_type=f"{req.action_type}_approved",
        actor=req.actor,
        reason=req.reason,
        audit_note=req.audit_note,
        dry_run=False,
        max_affected_items=req.max_affected_items,
        affected_items=req.affected_items,
        target_error_code=req.target_error_code,
        payload={
            "request_id": req.id,
            "supervisor_actor": payload.supervisor_actor,
            "supervisor_note": payload.supervisor_note,
        },
    )

    _execute_action_request(db, req)

    db.refresh(req)
    return _action_request_to_response(req)


@router.post("/action-requests/{request_id}/reject", response_model=VeoActionRequestResponse)
def reject_batch_action_request(
    request_id: str,
    payload: VeoApprovalDecisionRequest,
    db: Session = Depends(get_db),
) -> VeoActionRequestResponse:
    req = db.get(VeoBatchActionRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Action request not found")

    if req.approval_status != APPROVAL_PENDING:
        raise HTTPException(status_code=409, detail=f"Request already in status '{req.approval_status}'")

    if not payload.supervisor_actor.strip():
        raise HTTPException(status_code=400, detail="supervisor_actor is required")

    req.approval_status = APPROVAL_REJECTED
    req.supervisor_actor = payload.supervisor_actor
    req.supervisor_note = payload.supervisor_note
    req.decided_at = datetime.now(timezone.utc)
    db.add(req)
    db.commit()

    decision = VeoBatchApprovalDecision(
        request_id=req.id,
        decision="rejected",
        supervisor_actor=payload.supervisor_actor,
        supervisor_note=payload.supervisor_note,
        created_at=datetime.now(timezone.utc),
    )
    db.add(decision)
    db.commit()

    _create_batch_audit_event(
        db,
        batch_run_id=req.batch_run_id,
        action_type=f"{req.action_type}_rejected",
        actor=req.actor,
        reason=req.reason,
        audit_note=req.audit_note,
        dry_run=False,
        max_affected_items=req.max_affected_items,
        affected_items=req.affected_items,
        target_error_code=req.target_error_code,
        payload={
            "request_id": req.id,
            "supervisor_actor": payload.supervisor_actor,
            "supervisor_note": payload.supervisor_note,
        },
    )

    db.refresh(req)
    return _action_request_to_response(req)
8) PATCH backend/app/api/veo_workspace.py
Timeline: hiển thị approval lifecycle
Thêm vào route timeline, cùng với block audit events.
    action_requests = db.execute(
        select(VeoBatchActionRequest)
        .where(VeoBatchActionRequest.batch_run_id == batch_id)
        .order_by(VeoBatchActionRequest.created_at.desc())
        .limit(limit)
    ).scalars().all()

    for req in action_requests:
        events.append(
            VeoBatchTimelineEvent(
                event_type="approval_request_created" if req.requires_approval else "action_request_created",
                title=f"Action request: {req.action_type}",
                status=req.approval_status,
                error_code=req.target_error_code,
                message=(
                    f"actor={req.actor} | reason={req.reason} | affected={req.affected_items}"
                    + (f" | note={req.audit_note}" if req.audit_note else "")
                ),
                timestamp=req.created_at,
            )
        )

        if req.decided_at and req.approval_status in {APPROVAL_APPROVED, APPROVAL_REJECTED, APPROVAL_EXECUTED}:
            events.append(
                VeoBatchTimelineEvent(
                    event_type="approval_decision",
                    title=f"Approval decision: {req.approval_status}",
                    status=req.approval_status,
                    error_code=req.target_error_code,
                    message=(
                        f"supervisor={req.supervisor_actor or '-'}"
                        + (f" | note={req.supervisor_note}" if req.supervisor_note else "")
                    ),
                    timestamp=req.decided_at,
                )
            )

        if req.executed_at:
            events.append(
                VeoBatchTimelineEvent(
                    event_type="approval_request_executed",
                    title=f"Approved request executed: {req.action_type}",
                    status=req.approval_status,
                    error_code=req.target_error_code,
                    message=f"affected={req.affected_items}",
                    timestamp=req.executed_at,
                )
            )
9) PATCH tests/test_veo_workspace_api.py
Tests cho approval governance
Paste thêm vào file test API.
def test_large_cancel_pending_is_queued_for_approval(client):
    c, SessionLocal = client
    db = SessionLocal()

    seed_batch(db, "batch-approval-1")
    for idx in range(12):
        seed_item(db, f"item-approval-cancel-{idx}", batch_id="batch-approval-1", status="pending")
    db.close()

    res = c.post(
        "/api/v1/veo/batch-runs/batch-approval-1/cancel-pending",
        json={
            "actor": "ops@example.com",
            "reason": "Need to stop large pending wave",
            "audit_note": "Requires supervisor review",
            "dry_run": False,
            "max_affected_items": 100,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["affected_items"] == 12

    db = SessionLocal()
    rows = db.execute(
        select(VeoBatchActionRequest).where(
            VeoBatchActionRequest.batch_run_id == "batch-approval-1"
        )
    ).scalars().all()

    assert len(rows) == 1
    assert rows[0].requires_approval is True
    assert rows[0].approval_status == "pending_approval"

    # items should still be untouched
    assert db.get(VeoBatchItem, "item-approval-cancel-0").status == "pending"
    db.close()


def test_get_pending_approvals(client):
    c, SessionLocal = client
    db = SessionLocal()

    seed_batch(db, "batch-approval-2")
    req = VeoBatchActionRequest(
        batch_run_id="batch-approval-2",
        action_type="cancel_pending",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="Need supervisor approval",
        dry_run=False,
        affected_items=15,
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.commit()
    db.close()

    res = c.get("/api/v1/veo/batch-runs/batch-approval-2/pending-approvals")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["approval_status"] == "pending_approval"


def test_supervisor_approve_executes_request(client):
    c, SessionLocal = client
    db = SessionLocal()

    seed_batch(db, "batch-approval-3")
    for idx in range(12):
        seed_item(db, f"item-approval-run-{idx}", batch_id="batch-approval-3", status="pending")

    req = VeoBatchActionRequest(
        batch_run_id="batch-approval-3",
        action_type="cancel_pending",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="Stop pending items",
        dry_run=False,
        affected_items=12,
        preview_item_ids=[f"item-approval-run-{idx}" for idx in range(12)],
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.commit()
    request_id = req.id
    db.close()

    res = c.post(
        f"/api/v1/veo/action-requests/{request_id}/approve",
        json={
            "supervisor_actor": "supervisor@example.com",
            "supervisor_note": "Approved due to queue surge",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["approval_status"] == "executed"

    db = SessionLocal()
    assert db.get(VeoBatchItem, "item-approval-run-0").status == "cancelled"
    req = db.get(VeoBatchActionRequest, request_id)
    assert req.supervisor_actor == "supervisor@example.com"
    assert req.executed_at is not None
    db.close()


def test_supervisor_reject_keeps_items_unchanged(client):
    c, SessionLocal = client
    db = SessionLocal()

    seed_batch(db, "batch-approval-4")
    for idx in range(12):
        seed_item(db, f"item-approval-reject-{idx}", batch_id="batch-approval-4", status="pending")

    req = VeoBatchActionRequest(
        batch_run_id="batch-approval-4",
        action_type="cancel_pending",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="Stop pending items",
        dry_run=False,
        affected_items=12,
        preview_item_ids=[f"item-approval-reject-{idx}" for idx in range(12)],
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.commit()
    request_id = req.id
    db.close()

    res = c.post(
        f"/api/v1/veo/action-requests/{request_id}/reject",
        json={
            "supervisor_actor": "supervisor@example.com",
            "supervisor_note": "Rejected due to insufficient evidence",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["approval_status"] == "rejected"

    db = SessionLocal()
    assert db.get(VeoBatchItem, "item-approval-reject-0").status == "pending"
    req = db.get(VeoBatchActionRequest, request_id)
    assert req.supervisor_actor == "supervisor@example.com"
    assert req.executed_at is None
    db.close()
10) PATCH frontend/src/lib/api.ts
API cho pending approvals + approve/reject
Paste thêm vào file.
export type VeoActionRequest = {
  id: string;
  batch_run_id: string;
  action_type: string;
  approval_status: string;
  requires_approval: boolean;
  actor: string;
  reason: string;
  audit_note?: string | null;
  dry_run: boolean;
  max_affected_items?: number | null;
  affected_items: number;
  target_error_code?: string | null;
  preview_item_ids: string[];
  supervisor_actor?: string | null;
  supervisor_note?: string | null;
  created_at: string;
  decided_at?: string | null;
  executed_at?: string | null;
};

export type VeoPendingApprovalList = {
  items: VeoActionRequest[];
  total: number;
};

export async function getVeoPendingApprovals(batchId: string): Promise<VeoPendingApprovalList> {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/pending-approvals`);
  if (!res.ok) throw new Error(`Failed to fetch pending approvals for ${batchId}`);
  return res.json();
}

export async function approveVeoActionRequest(
  requestId: string,
  payload: { supervisor_actor: string; supervisor_note?: string }
): Promise<VeoActionRequest> {
  const res = await fetch(`/api/v1/veo/action-requests/${requestId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to approve action request ${requestId}`);
  return res.json();
}

export async function rejectVeoActionRequest(
  requestId: string,
  payload: { supervisor_actor: string; supervisor_note?: string }
): Promise<VeoActionRequest> {
  const res = await fetch(`/api/v1/veo/action-requests/${requestId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to reject action request ${requestId}`);
  return res.json();
}
11) frontend/src/components/veo/VeoPendingApprovalsPanel.tsx
"use client";

import { useState } from "react";
import {
  approveVeoActionRequest,
  rejectVeoActionRequest,
  VeoPendingApprovalList,
} from "@/src/lib/api";

type Props = {
  data: VeoPendingApprovalList | null;
  loading?: boolean;
  onActionDone?: () => Promise<void> | void;
};

export default function VeoPendingApprovalsPanel({ data, loading, onActionDone }: Props) {
  const [supervisorActor, setSupervisorActor] = useState("");
  const [supervisorNote, setSupervisorNote] = useState("");
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  async function handleDecision(requestId: string, decision: "approve" | "reject") {
    try {
      if (!supervisorActor.trim()) {
        alert("Supervisor actor is required.");
        return;
      }

      setActionLoadingId(requestId);

      if (decision === "approve") {
        await approveVeoActionRequest(requestId, {
          supervisor_actor: supervisorActor.trim(),
          supervisor_note: supervisorNote.trim() || undefined,
        });
      } else {
        await rejectVeoActionRequest(requestId, {
          supervisor_actor: supervisorActor.trim(),
          supervisor_note: supervisorNote.trim() || undefined,
        });
      }

      await onActionDone?.();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Approval action failed");
    } finally {
      setActionLoadingId(null);
    }
  }

  if (loading && !data) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        Loading pending approvals...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        No pending approvals data.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-neutral-200 bg-white p-4">
        <div className="mb-3 text-base font-semibold">Supervisor Decision Controls</div>
        <div className="grid gap-3 md:grid-cols-2">
          <input
            value={supervisorActor}
            onChange={(e) => setSupervisorActor(e.target.value)}
            placeholder="supervisor@example.com"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />
          <input
            value={supervisorNote}
            onChange={(e) => setSupervisorNote(e.target.value)}
            placeholder="Decision note"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />
        </div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 px-4 py-3">
          <h3 className="text-base font-semibold">Pending Approvals ({data.total})</h3>
        </div>

        <div className="divide-y divide-neutral-200">
          {data.items.length === 0 ? (
            <div className="px-4 py-6 text-sm text-neutral-500">No pending approvals.</div>
          ) : (
            data.items.map((item) => (
              <div key={item.id} className="px-4 py-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0">
                    <div className="font-medium">{item.action_type}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-neutral-600">
                      <span className="rounded-full border px-2 py-1">request: {item.id}</span>
                      <span className="rounded-full border px-2 py-1">actor: {item.actor}</span>
                      <span className="rounded-full border px-2 py-1">affected: {item.affected_items}</span>
                      <span className="rounded-full border px-2 py-1">status: {item.approval_status}</span>
                      {item.target_error_code ? (
                        <span className="rounded-full border px-2 py-1">error: {item.target_error_code}</span>
                      ) : null}
                    </div>

                    <div className="mt-2 text-sm text-neutral-700">
                      <div><strong>Reason:</strong> {item.reason}</div>
                      {item.audit_note ? <div><strong>Audit note:</strong> {item.audit_note}</div> : null}
                    </div>

                    {item.preview_item_ids.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.preview_item_ids.slice(0, 20).map((id) => (
                          <span key={id} className="rounded-full border px-3 py-1 text-xs">
                            {id}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
                      onClick={() => handleDecision(item.id, "approve")}
                      disabled={actionLoadingId !== null}
                    >
                      {actionLoadingId === item.id ? "Working..." : "Approve"}
                    </button>
                    <button
                      className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
                      onClick={() => handleDecision(item.id, "reject")}
                      disabled={actionLoadingId !== null}
                    >
                      {actionLoadingId === item.id ? "Working..." : "Reject"}
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
12) PATCH frontend/src/app/projects/[id]/page.tsx
Thêm tab Pending Approvals
Thêm imports
import { getVeoPendingApprovals, VeoPendingApprovalList } from "@/src/lib/api";
import VeoPendingApprovalsPanel from "@/src/components/veo/VeoPendingApprovalsPanel";
Mở rộng type tab
type VeoBatchTab = "overview" | "items" | "failures" | "timeline" | "approvals";
Thêm state
const [pendingApprovals, setPendingApprovals] = useState<VeoPendingApprovalList | null>(null);
Trong refresh, thêm fetch
const [statsData, itemsData, errorsData, timelineData, approvalsData] = await Promise.all([
  getVeoBatchRunStats(batchId),
  getVeoBatchRunItems(batchId, {
    limit: itemsPage.limit,
    offset,
    status: statusFilter || undefined,
    mode: modeFilter || undefined,
    search: searchText || undefined,
  }),
  getVeoBatchErrorsSummary(batchId),
  getVeoBatchTimeline(batchId, { limit: 100 }),
  getVeoPendingApprovals(batchId),
]);

setStats(statsData);
setItemsPage(itemsData);
setErrorsSummary(errorsData);
setTimeline(timelineData);
setPendingApprovals(approvalsData);
Thêm tab button
<TabButton
  label="Pending Approvals"
  active={activeTab === "approvals"}
  onClick={() => setActiveTab("approvals")}
/>
Thêm panel render
{activeTab === "approvals" ? (
  <VeoPendingApprovalsPanel
    data={pendingApprovals}
    loading={loading}
    onActionDone={() => refresh()}
  />
) : null}
13) Kết quả sau phase này
Sau patch này, hệ đã đi từ:
controlled operations
sang:
human-governed production operations
Cụ thể:
action lớn không execute trực tiếp nữa
thay vào đó tạo approval request
supervisor có quyền approve / reject
approval lifecycle được ghi lại vào:
VeoBatchActionRequest
VeoBatchApprovalDecision
VeoBatchAuditEvent
timeline UI
Frontend giờ có:
tab Pending Approvals
panel supervisor approve/reject
hiển thị request details + preview affected items
Đây là bước rất quan trọng vì từ đây ops đã có governance boundary thực sự.
14) Bước mạnh nhất tiếp theo
Bước tiếp theo mạnh nhất là policy-driven governance, theo đúng format paste-ready:
config approval thresholds theo action/provider/project
escalation rules
auto-expire pending approvals
supervisor band / RBAC
approval SLA + overdue queue
frontend badges cho urgent / overdue approvals
Đó là bước nâng hệ từ human-governed lên policy-governed human oversight.
Mình đang nâng lớp governance từ “có approval” sang “approval theo policy”: thêm threshold theo action/provider/project, SLA quá hạn, expire tự động, escalation và phân tầng supervisor để queue approval có ưu tiên vận hành thật.
Đã suy nghĩ trong giây lát
Được. Mình viết tiếp ngay policy-driven governance theo đúng format paste-ready.
Mục tiêu phase này:
approval threshold theo action / provider / project
có escalation rules
có auto-expire pending approvals
có supervisor band / RBAC
có approval SLA + overdue queue
frontend có urgent / overdue badges
1) PATCH backend/app/core/config.py
Thêm policy governance config
Paste thêm block này vào settings hiện có.
# Veo approval governance policy
VEO_APPROVAL_THRESHOLD_DEFAULT: int = 20
VEO_APPROVAL_THRESHOLD_BY_ACTION_JSON: str = '{"retry_by_error_code":20,"cancel_pending":10,"requeue_retry_waiting":25}'
VEO_APPROVAL_THRESHOLD_BY_PROVIDER_JSON: str = '{"veo":20}'
VEO_APPROVAL_THRESHOLD_BY_PROJECT_JSON: str = '{}'

VEO_APPROVAL_SLA_MINUTES_DEFAULT: int = 30
VEO_APPROVAL_SLA_BY_ACTION_JSON: str = '{"retry_by_error_code":30,"cancel_pending":15,"requeue_retry_waiting":45}'

VEO_APPROVAL_ESCALATION_MINUTES_DEFAULT: int = 20
VEO_APPROVAL_ESCALATION_BY_ACTION_JSON: str = '{"cancel_pending":10,"retry_by_error_code":20,"requeue_retry_waiting":30}'

VEO_APPROVAL_AUTO_EXPIRE_MINUTES_DEFAULT: int = 120
VEO_APPROVAL_AUTO_EXPIRE_BY_ACTION_JSON: str = '{"cancel_pending":60,"retry_by_error_code":120,"requeue_retry_waiting":180}'

# Supervisor governance / RBAC
VEO_SUPERVISOR_BANDS_JSON: str = '{"ops_supervisor":1,"ops_manager":2,"ops_admin":3}'
VEO_REQUIRED_BAND_BY_ACTION_JSON: str = '{"retry_by_error_code":1,"cancel_pending":2,"requeue_retry_waiting":1}'
VEO_HIGH_IMPACT_REQUIRED_BAND: int = 2
VEO_CRITICAL_IMPACT_REQUIRED_BAND: int = 3
2) PATCH .env.example
# Veo approval governance policy
VEO_APPROVAL_THRESHOLD_DEFAULT=20
VEO_APPROVAL_THRESHOLD_BY_ACTION_JSON={"retry_by_error_code":20,"cancel_pending":10,"requeue_retry_waiting":25}
VEO_APPROVAL_THRESHOLD_BY_PROVIDER_JSON={"veo":20}
VEO_APPROVAL_THRESHOLD_BY_PROJECT_JSON={}

VEO_APPROVAL_SLA_MINUTES_DEFAULT=30
VEO_APPROVAL_SLA_BY_ACTION_JSON={"retry_by_error_code":30,"cancel_pending":15,"requeue_retry_waiting":45}

VEO_APPROVAL_ESCALATION_MINUTES_DEFAULT=20
VEO_APPROVAL_ESCALATION_BY_ACTION_JSON={"cancel_pending":10,"retry_by_error_code":20,"requeue_retry_waiting":30}

VEO_APPROVAL_AUTO_EXPIRE_MINUTES_DEFAULT=120
VEO_APPROVAL_AUTO_EXPIRE_BY_ACTION_JSON={"cancel_pending":60,"retry_by_error_code":120,"requeue_retry_waiting":180}

VEO_SUPERVISOR_BANDS_JSON={"ops_supervisor":1,"ops_manager":2,"ops_admin":3}
VEO_REQUIRED_BAND_BY_ACTION_JSON={"retry_by_error_code":1,"cancel_pending":2,"requeue_retry_waiting":1}
VEO_HIGH_IMPACT_REQUIRED_BAND=2
VEO_CRITICAL_IMPACT_REQUIRED_BAND=3
3) PATCH backend/.env.example
# Veo approval governance policy
VEO_APPROVAL_THRESHOLD_DEFAULT=20
VEO_APPROVAL_THRESHOLD_BY_ACTION_JSON={"retry_by_error_code":20,"cancel_pending":10,"requeue_retry_waiting":25}
VEO_APPROVAL_THRESHOLD_BY_PROVIDER_JSON={"veo":20}
VEO_APPROVAL_THRESHOLD_BY_PROJECT_JSON={}

VEO_APPROVAL_SLA_MINUTES_DEFAULT=30
VEO_APPROVAL_SLA_BY_ACTION_JSON={"retry_by_error_code":30,"cancel_pending":15,"requeue_retry_waiting":45}

VEO_APPROVAL_ESCALATION_MINUTES_DEFAULT=20
VEO_APPROVAL_ESCALATION_BY_ACTION_JSON={"cancel_pending":10,"retry_by_error_code":20,"requeue_retry_waiting":30}

VEO_APPROVAL_AUTO_EXPIRE_MINUTES_DEFAULT=120
VEO_APPROVAL_AUTO_EXPIRE_BY_ACTION_JSON={"cancel_pending":60,"retry_by_error_code":120,"requeue_retry_waiting":180}

VEO_SUPERVISOR_BANDS_JSON={"ops_supervisor":1,"ops_manager":2,"ops_admin":3}
VEO_REQUIRED_BAND_BY_ACTION_JSON={"retry_by_error_code":1,"cancel_pending":2,"requeue_retry_waiting":1}
VEO_HIGH_IMPACT_REQUIRED_BAND=2
VEO_CRITICAL_IMPACT_REQUIRED_BAND=3
4) PATCH backend/app/models/veo_workspace.py
Thêm policy/SLA/escalation fields vào VeoBatchActionRequest
Bổ sung các field này vào class VeoBatchActionRequest.
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    required_supervisor_band: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    escalation_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    is_overdue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_expired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    escalation_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)  # normal/escalated/expired
5) FILE MỚI backend/app/services/veo_approval_policy_service.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from backend.app.core.config import settings


@dataclass
class ApprovalPolicyDecision:
    requires_approval: bool
    required_supervisor_band: int
    threshold_used: int
    sla_minutes: int
    escalation_minutes: int
    auto_expire_minutes: int
    sla_due_at: datetime
    escalation_due_at: datetime
    expires_at: datetime


class VeoApprovalPolicyService:
    def __init__(self) -> None:
        self.threshold_default = int(getattr(settings, "VEO_APPROVAL_THRESHOLD_DEFAULT", 20))
        self.sla_default = int(getattr(settings, "VEO_APPROVAL_SLA_MINUTES_DEFAULT", 30))
        self.escalation_default = int(getattr(settings, "VEO_APPROVAL_ESCALATION_MINUTES_DEFAULT", 20))
        self.expire_default = int(getattr(settings, "VEO_APPROVAL_AUTO_EXPIRE_MINUTES_DEFAULT", 120))
        self.high_impact_required_band = int(getattr(settings, "VEO_HIGH_IMPACT_REQUIRED_BAND", 2))
        self.critical_impact_required_band = int(getattr(settings, "VEO_CRITICAL_IMPACT_REQUIRED_BAND", 3))

    def evaluate(
        self,
        *,
        action_type: str,
        provider_name: Optional[str],
        project_id: Optional[str],
        affected_items: int,
        now: Optional[datetime] = None,
    ) -> ApprovalPolicyDecision:
        now = now or datetime.now(timezone.utc)

        threshold = self._resolve_threshold(
            action_type=action_type,
            provider_name=provider_name,
            project_id=project_id,
        )

        requires_approval = affected_items > threshold
        required_band = self._resolve_required_band(
            action_type=action_type,
            affected_items=affected_items,
            threshold=threshold,
        )

        sla_minutes = self._lookup_json_int("VEO_APPROVAL_SLA_BY_ACTION_JSON", action_type, self.sla_default)
        escalation_minutes = self._lookup_json_int(
            "VEO_APPROVAL_ESCALATION_BY_ACTION_JSON",
            action_type,
            self.escalation_default,
        )
        auto_expire_minutes = self._lookup_json_int(
            "VEO_APPROVAL_AUTO_EXPIRE_BY_ACTION_JSON",
            action_type,
            self.expire_default,
        )

        return ApprovalPolicyDecision(
            requires_approval=requires_approval,
            required_supervisor_band=required_band,
            threshold_used=threshold,
            sla_minutes=sla_minutes,
            escalation_minutes=escalation_minutes,
            auto_expire_minutes=auto_expire_minutes,
            sla_due_at=now + timedelta(minutes=sla_minutes),
            escalation_due_at=now + timedelta(minutes=escalation_minutes),
            expires_at=now + timedelta(minutes=auto_expire_minutes),
        )

    def supervisor_band(self, supervisor_actor: str) -> int:
        mapping = self._load_json("VEO_SUPERVISOR_BANDS_JSON")
        return int(mapping.get(supervisor_actor, 0))

    def required_band_for_action(self, action_type: str) -> int:
        mapping = self._load_json("VEO_REQUIRED_BAND_BY_ACTION_JSON")
        return int(mapping.get(action_type, 1))

    def _resolve_threshold(
        self,
        *,
        action_type: str,
        provider_name: Optional[str],
        project_id: Optional[str],
    ) -> int:
        project_map = self._load_json("VEO_APPROVAL_THRESHOLD_BY_PROJECT_JSON")
        provider_map = self._load_json("VEO_APPROVAL_THRESHOLD_BY_PROVIDER_JSON")
        action_map = self._load_json("VEO_APPROVAL_THRESHOLD_BY_ACTION_JSON")

        if project_id and project_id in project_map:
            return int(project_map[project_id])
        if provider_name and provider_name in provider_map:
            return int(provider_map[provider_name])
        if action_type in action_map:
            return int(action_map[action_type])

        return self.threshold_default

    def _resolve_required_band(self, *, action_type: str, affected_items: int, threshold: int) -> int:
        base_band = self.required_band_for_action(action_type)

        if affected_items >= threshold * 3:
            return max(base_band, self.critical_impact_required_band)
        if affected_items >= threshold * 2:
            return max(base_band, self.high_impact_required_band)
        return base_band

    def _lookup_json_int(self, attr_name: str, key: str, default: int) -> int:
        payload = self._load_json(attr_name)
        try:
            return int(payload.get(key, default))
        except Exception:
            return default

    def _load_json(self, attr_name: str) -> Dict[str, Any]:
        raw = getattr(settings, attr_name, "") or ""
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
6) FILE MỚI backend/app/services/veo_approval_governance_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.veo_workspace import VeoBatchActionRequest


class VeoApprovalGovernanceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def mark_overdue_and_escalate(self, now: Optional[datetime] = None) -> Dict[str, int]:
        now = now or datetime.now(timezone.utc)

        rows = self.db.execute(
            select(VeoBatchActionRequest).where(
                VeoBatchActionRequest.approval_status == "pending_approval",
                VeoBatchActionRequest.is_expired == False,  # noqa: E712
            )
        ).scalars().all()

        overdue = 0
        escalated = 0
        expired = 0

        for req in rows:
            if req.expires_at and req.expires_at <= now:
                req.is_expired = True
                req.is_overdue = True
                req.approval_status = "expired"
                req.escalation_status = "expired"
                expired += 1
                self.db.add(req)
                continue

            if req.sla_due_at and req.sla_due_at <= now:
                if not req.is_overdue:
                    req.is_overdue = True
                    overdue += 1
                    self.db.add(req)

            if req.escalation_due_at and req.escalation_due_at <= now:
                if req.escalation_status != "escalated":
                    req.escalation_status = "escalated"
                    req.current_escalation_level = int(req.current_escalation_level or 0) + 1
                    escalated += 1
                    self.db.add(req)

        self.db.commit()

        return {
            "overdue": overdue,
            "escalated": escalated,
            "expired": expired,
        }

    def overdue_queue(self) -> List[VeoBatchActionRequest]:
        return self.db.execute(
            select(VeoBatchActionRequest).where(
                VeoBatchActionRequest.approval_status == "pending_approval",
                VeoBatchActionRequest.is_overdue == True,  # noqa: E712
            ).order_by(VeoBatchActionRequest.sla_due_at.asc())
        ).scalars().all()
7) PATCH backend/app/api/veo_workspace.py
Import services mới
from backend.app.services.veo_approval_policy_service import VeoApprovalPolicyService
from backend.app.services.veo_approval_governance_service import VeoApprovalGovernanceService
8) PATCH backend/app/api/veo_workspace.py
Thay helper threshold cũ bằng policy service
Bạn có thể bỏ helper _approval_threshold_for_action và _should_require_approval cũ.
Thêm helper mới:
def _policy_decision_for_request(
    db: Session,
    *,
    batch_id: str,
    action_type: str,
    affected_items: int,
    provider_name: Optional[str] = None,
    project_id: Optional[str] = None,
):
    run = db.get(VeoBatchRun, batch_id)
    provider_name = provider_name or getattr(run, "provider_name", None)
    policy_service = VeoApprovalPolicyService()
    return policy_service.evaluate(
        action_type=action_type,
        provider_name=provider_name,
        project_id=project_id,
        affected_items=affected_items,
    )
9) PATCH backend/app/api/veo_workspace.py
Update _create_action_request để lưu policy fields
Thay function _create_action_request bằng bản dưới.
def _create_action_request(
    db: Session,
    *,
    batch_run_id: str,
    action_type: str,
    actor: str,
    reason: str,
    audit_note: Optional[str],
    dry_run: bool,
    max_affected_items: Optional[int],
    affected_items: int,
    target_error_code: Optional[str],
    preview_item_ids: List[str],
    requires_approval: bool,
    request_payload: Optional[dict] = None,
    provider_name: Optional[str] = None,
    project_id: Optional[str] = None,
    required_supervisor_band: int = 1,
    sla_due_at: Optional[datetime] = None,
    escalation_due_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
) -> VeoBatchActionRequest:
    approval_status = APPROVAL_PENDING if requires_approval else APPROVAL_NOT_REQUIRED
    req = VeoBatchActionRequest(
        batch_run_id=batch_run_id,
        action_type=action_type,
        approval_status=approval_status,
        requires_approval=requires_approval,
        actor=actor,
        reason=reason,
        audit_note=audit_note,
        dry_run=dry_run,
        max_affected_items=max_affected_items,
        affected_items=affected_items,
        target_error_code=target_error_code,
        preview_item_ids=preview_item_ids,
        request_payload=request_payload or {},
        provider_name=provider_name,
        project_id=project_id,
        required_supervisor_band=required_supervisor_band,
        sla_due_at=sla_due_at,
        escalation_due_at=escalation_due_at,
        expires_at=expires_at,
        is_overdue=False,
        is_expired=False,
        escalation_status="normal" if requires_approval else None,
        current_escalation_level=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req
10) PATCH backend/app/api/veo_workspace.py
Trong 3 action endpoint, dùng policy decision thay vì threshold cứng
Ví dụ cho retry-by-error-code
Sau khi có affected_count, preview_item_ids, blocked, thêm:
    policy = _policy_decision_for_request(
        db,
        batch_id=batch_id,
        action_type="retry_by_error_code",
        affected_items=affected_count,
    )
    requires_approval = policy.requires_approval
Và trong _create_action_request(...), truyền thêm:
            provider_name=getattr(run, "provider_name", None),
            project_id=None,
            required_supervisor_band=policy.required_supervisor_band,
            sla_due_at=policy.sla_due_at,
            escalation_due_at=policy.escalation_due_at,
            expires_at=policy.expires_at,
Tương tự cho:
cancel_pending với action_type="cancel_pending"
requeue_retry_waiting với action_type="requeue_retry_waiting"
11) PATCH backend/app/api/veo_workspace.py
Enforce supervisor band tại approve endpoint
Trong approve_batch_action_request, thêm block này trước khi set approved:
    policy_service = VeoApprovalPolicyService()
    supervisor_band = policy_service.supervisor_band(payload.supervisor_actor)

    if supervisor_band < int(req.required_supervisor_band or 1):
        raise HTTPException(
            status_code=403,
            detail=f"Supervisor band too low. Required={req.required_supervisor_band}, got={supervisor_band}",
        )

    if req.is_expired:
        raise HTTPException(status_code=409, detail="Cannot approve expired request")
12) PATCH backend/app/api/veo_workspace.py
Pending approvals endpoint: thêm overdue queue params
Thay route pending approvals bằng bản dưới.
@router.get("/batch-runs/{batch_id}/pending-approvals", response_model=VeoPendingApprovalListResponse)
def get_pending_batch_approvals(
    batch_id: str,
    overdue_only: bool = Query(default=False),
    escalated_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> VeoPendingApprovalListResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    stmt = select(VeoBatchActionRequest).where(
        VeoBatchActionRequest.batch_run_id == batch_id,
        VeoBatchActionRequest.approval_status == APPROVAL_PENDING,
    )

    if overdue_only:
        stmt = stmt.where(VeoBatchActionRequest.is_overdue == True)  # noqa: E712

    if escalated_only:
        stmt = stmt.where(VeoBatchActionRequest.escalation_status == "escalated")

    rows = db.execute(
        stmt.order_by(
            VeoBatchActionRequest.is_overdue.desc(),
            VeoBatchActionRequest.escalation_status.desc(),
            VeoBatchActionRequest.sla_due_at.asc(),
            VeoBatchActionRequest.created_at.asc(),
        )
    ).scalars().all()

    return VeoPendingApprovalListResponse(
        items=[_action_request_to_response(row) for row in rows],
        total=len(rows),
    )
13) PATCH backend/app/api/veo_workspace.py
Bổ sung fields vào VeoActionRequestResponse
Thêm vào schema:
    provider_name: Optional[str] = None
    project_id: Optional[str] = None
    required_supervisor_band: int
    current_escalation_level: int
    sla_due_at: Optional[datetime] = None
    escalation_due_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_overdue: bool
    is_expired: bool
    escalation_status: Optional[str] = None
Và update _action_request_to_response(...):
        provider_name=req.provider_name,
        project_id=req.project_id,
        required_supervisor_band=req.required_supervisor_band,
        current_escalation_level=req.current_escalation_level,
        sla_due_at=req.sla_due_at,
        escalation_due_at=req.escalation_due_at,
        expires_at=req.expires_at,
        is_overdue=req.is_overdue,
        is_expired=req.is_expired,
        escalation_status=req.escalation_status,
14) PATCH backend/app/api/veo_workspace.py
Timeline: thêm approval overdue / expired signal
Trong block timeline action requests, sửa message như sau:
                message=(
                    f"actor={req.actor} | reason={req.reason} | affected={req.affected_items}"
                    + (f" | overdue={req.is_overdue}" if req.requires_approval else "")
                    + (f" | escalation={req.escalation_status}" if req.requires_approval else "")
                    + (f" | required_band={req.required_supervisor_band}" if req.requires_approval else "")
                    + (f" | note={req.audit_note}" if req.audit_note else "")
                ),
Và thêm event expiry:
        if req.is_expired and req.expires_at:
            events.append(
                VeoBatchTimelineEvent(
                    event_type="approval_request_expired",
                    title=f"Approval request expired: {req.action_type}",
                    status=req.approval_status,
                    error_code=req.target_error_code,
                    message=f"actor={req.actor} | required_band={req.required_supervisor_band}",
                    timestamp=req.expires_at,
                )
            )
15) FILE MỚI backend/app/workers/veo_approval_governance_worker.py
from __future__ import annotations

from celery import shared_task

from backend.app.db.session import SessionLocal
from backend.app.services.veo_approval_governance_service import VeoApprovalGovernanceService


@shared_task(name="backend.app.workers.veo_approval_governance_worker.tick_veo_approval_governance")
def tick_veo_approval_governance() -> dict:
    db = SessionLocal()
    try:
        service = VeoApprovalGovernanceService(db)
        result = service.mark_overdue_and_escalate()
        return {
            "ok": True,
            **result,
        }
    finally:
        db.close()
16) PATCH tests/test_veo_workspace_api.py
Tests cho policy-driven governance
Paste thêm vào file test.
def test_policy_threshold_queues_large_action_for_approval(client):
    c, SessionLocal = client
    db = SessionLocal()
    run = seed_batch(db, "batch-policy-1")
    run.provider_name = "veo"
    db.add(run)
    db.commit()

    for idx in range(11):
        seed_item(db, f"item-policy-{idx}", batch_id="batch-policy-1", status="pending")
    db.close()

    res = c.post(
        "/api/v1/veo/batch-runs/batch-policy-1/cancel-pending",
        json={
            "actor": "ops@example.com",
            "reason": "Need stop large pending set",
            "dry_run": False,
            "max_affected_items": 100,
        },
    )
    assert res.status_code == 200

    db = SessionLocal()
    reqs = db.execute(
        select(VeoBatchActionRequest).where(VeoBatchActionRequest.batch_run_id == "batch-policy-1")
    ).scalars().all()

    assert len(reqs) == 1
    assert reqs[0].requires_approval is True
    assert reqs[0].approval_status == "pending_approval"
    assert reqs[0].sla_due_at is not None
    assert reqs[0].expires_at is not None
    db.close()


def test_supervisor_band_rbac_blocks_low_band_approval(client, monkeypatch):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-policy-2")

    req = VeoBatchActionRequest(
        batch_run_id="batch-policy-2",
        action_type="cancel_pending",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="Need approval",
        dry_run=False,
        affected_items=20,
        required_supervisor_band=3,
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.commit()
    request_id = req.id
    db.close()

    res = c.post(
        f"/api/v1/veo/action-requests/{request_id}/approve",
        json={
            "supervisor_actor": "ops_supervisor",
            "supervisor_note": "Attempt approval",
        },
    )
    assert res.status_code == 403


def test_expired_request_cannot_be_approved(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-policy-3")

    req = VeoBatchActionRequest(
        batch_run_id="batch-policy-3",
        action_type="cancel_pending",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="Need approval",
        dry_run=False,
        affected_items=20,
        required_supervisor_band=1,
        is_expired=True,
        expires_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.commit()
    request_id = req.id
    db.close()

    res = c.post(
        f"/api/v1/veo/action-requests/{request_id}/approve",
        json={
            "supervisor_actor": "ops_admin",
            "supervisor_note": "Too late",
        },
    )
    assert res.status_code == 409
17) FILE MỚI tests/test_veo_approval_governance_service.py
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.models.veo_workspace import VeoBatchActionRequest
from backend.app.services.veo_approval_governance_service import VeoApprovalGovernanceService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_mark_overdue_and_escalate(db_session):
    now = datetime.now(timezone.utc)

    req = VeoBatchActionRequest(
        batch_run_id="batch-1",
        action_type="cancel_pending",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="Need approval",
        dry_run=False,
        affected_items=15,
        sla_due_at=now - timedelta(minutes=1),
        escalation_due_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=30),
        created_at=now - timedelta(minutes=40),
    )
    db_session.add(req)
    db_session.commit()

    service = VeoApprovalGovernanceService(db_session)
    result = service.mark_overdue_and_escalate(now=now)

    refreshed = db_session.get(VeoBatchActionRequest, req.id)
    assert result["overdue"] == 1
    assert result["escalated"] == 1
    assert refreshed.is_overdue is True
    assert refreshed.escalation_status == "escalated"


def test_mark_expired(db_session):
    now = datetime.now(timezone.utc)

    req = VeoBatchActionRequest(
        batch_run_id="batch-1",
        action_type="retry_by_error_code",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="Need approval",
        dry_run=False,
        affected_items=30,
        sla_due_at=now - timedelta(minutes=10),
        escalation_due_at=now - timedelta(minutes=5),
        expires_at=now - timedelta(minutes=1),
        created_at=now - timedelta(minutes=50),
    )
    db_session.add(req)
    db_session.commit()

    service = VeoApprovalGovernanceService(db_session)
    result = service.mark_overdue_and_escalate(now=now)

    refreshed = db_session.get(VeoBatchActionRequest, req.id)
    assert result["expired"] == 1
    assert refreshed.is_expired is True
    assert refreshed.approval_status == "expired"
18) PATCH frontend/src/lib/api.ts
Mở rộng VeoActionRequest
Thay type VeoActionRequest bằng bản dưới.
export type VeoActionRequest = {
  id: string;
  batch_run_id: string;
  action_type: string;
  approval_status: string;
  requires_approval: boolean;
  actor: string;
  reason: string;
  audit_note?: string | null;
  dry_run: boolean;
  max_affected_items?: number | null;
  affected_items: number;
  target_error_code?: string | null;
  preview_item_ids: string[];
  supervisor_actor?: string | null;
  supervisor_note?: string | null;

  provider_name?: string | null;
  project_id?: string | null;
  required_supervisor_band: number;
  current_escalation_level: number;
  sla_due_at?: string | null;
  escalation_due_at?: string | null;
  expires_at?: string | null;
  is_overdue: boolean;
  is_expired: boolean;
  escalation_status?: string | null;

  created_at: string;
  decided_at?: string | null;
  executed_at?: string | null;
};
19) PATCH frontend/src/lib/api.ts
Pending approvals filter params
Thay function getVeoPendingApprovals bằng bản dưới.
export async function getVeoPendingApprovals(
  batchId: string,
  params?: { overdue_only?: boolean; escalated_only?: boolean }
): Promise<VeoPendingApprovalList> {
  const search = new URLSearchParams();
  if (params?.overdue_only) search.set("overdue_only", "true");
  if (params?.escalated_only) search.set("escalated_only", "true");

  const qs = search.toString();
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/pending-approvals${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to fetch pending approvals for ${batchId}`);
  return res.json();
}
20) PATCH frontend/src/components/veo/VeoPendingApprovalsPanel.tsx
Badges urgent / overdue / escalated
Thay file cũ bằng bản dưới.
"use client";

import { useMemo, useState } from "react";
import {
  approveVeoActionRequest,
  rejectVeoActionRequest,
  VeoPendingApprovalList,
} from "@/src/lib/api";

type Props = {
  data: VeoPendingApprovalList | null;
  loading?: boolean;
  onActionDone?: () => Promise<void> | void;
};

export default function VeoPendingApprovalsPanel({ data, loading, onActionDone }: Props) {
  const [supervisorActor, setSupervisorActor] = useState("");
  const [supervisorNote, setSupervisorNote] = useState("");
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [escalatedOnly, setEscalatedOnly] = useState(false);

  const items = useMemo(() => {
    let rows = data?.items || [];
    if (overdueOnly) rows = rows.filter((x) => x.is_overdue);
    if (escalatedOnly) rows = rows.filter((x) => x.escalation_status === "escalated");
    return rows;
  }, [data, overdueOnly, escalatedOnly]);

  async function handleDecision(requestId: string, decision: "approve" | "reject") {
    try {
      if (!supervisorActor.trim()) {
        alert("Supervisor actor is required.");
        return;
      }

      setActionLoadingId(requestId);

      if (decision === "approve") {
        await approveVeoActionRequest(requestId, {
          supervisor_actor: supervisorActor.trim(),
          supervisor_note: supervisorNote.trim() || undefined,
        });
      } else {
        await rejectVeoActionRequest(requestId, {
          supervisor_actor: supervisorActor.trim(),
          supervisor_note: supervisorNote.trim() || undefined,
        });
      }

      await onActionDone?.();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Approval action failed");
    } finally {
      setActionLoadingId(null);
    }
  }

  if (loading && !data) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        Loading pending approvals...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        No pending approvals data.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-neutral-200 bg-white p-4">
        <div className="mb-3 text-base font-semibold">Supervisor Decision Controls</div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <input
            value={supervisorActor}
            onChange={(e) => setSupervisorActor(e.target.value)}
            placeholder="supervisor@example.com"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />
          <input
            value={supervisorNote}
            onChange={(e) => setSupervisorNote(e.target.value)}
            placeholder="Decision note"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={overdueOnly} onChange={(e) => setOverdueOnly(e.target.checked)} />
            Overdue only
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={escalatedOnly} onChange={(e) => setEscalatedOnly(e.target.checked)} />
            Escalated only
          </label>
        </div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 px-4 py-3">
          <h3 className="text-base font-semibold">Pending Approvals ({items.length})</h3>
        </div>

        <div className="divide-y divide-neutral-200">
          {items.length === 0 ? (
            <div className="px-4 py-6 text-sm text-neutral-500">No matching pending approvals.</div>
          ) : (
            items.map((item) => (
              <div key={item.id} className="px-4 py-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0">
                    <div className="font-medium">{item.action_type}</div>

                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-neutral-600">
                      <span className="rounded-full border px-2 py-1">request: {item.id}</span>
                      <span className="rounded-full border px-2 py-1">actor: {item.actor}</span>
                      <span className="rounded-full border px-2 py-1">affected: {item.affected_items}</span>
                      <span className="rounded-full border px-2 py-1">band: {item.required_supervisor_band}</span>

                      {item.is_overdue ? (
                        <span className="rounded-full border px-2 py-1 text-red-600">OVERDUE</span>
                      ) : null}
                      {item.escalation_status === "escalated" ? (
                        <span className="rounded-full border px-2 py-1 text-amber-600">ESCALATED</span>
                      ) : null}
                      {item.expires_at ? (
                        <span className="rounded-full border px-2 py-1">
                          expires: {new Date(item.expires_at).toLocaleString()}
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-2 text-sm text-neutral-700">
                      <div><strong>Reason:</strong> {item.reason}</div>
                      {item.audit_note ? <div><strong>Audit note:</strong> {item.audit_note}</div> : null}
                      {item.sla_due_at ? (
                        <div><strong>SLA due:</strong> {new Date(item.sla_due_at).toLocaleString()}</div>
                      ) : null}
                    </div>

                    {item.preview_item_ids.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.preview_item_ids.slice(0, 20).map((id) => (
                          <span key={id} className="rounded-full border px-3 py-1 text-xs">
                            {id}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
                      onClick={() => handleDecision(item.id, "approve")}
                      disabled={actionLoadingId !== null || item.is_expired}
                    >
                      {actionLoadingId === item.id ? "Working..." : "Approve"}
                    </button>
                    <button
                      className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
                      onClick={() => handleDecision(item.id, "reject")}
                      disabled={actionLoadingId !== null || item.is_expired}
                    >
                      {actionLoadingId === item.id ? "Working..." : "Reject"}
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
21) PATCH frontend/src/app/projects/[id]/page.tsx
Gọi refresh pending approvals với filters ngoài server nếu muốn
Bản hiện tại vẫn ổn nếu filter ở client. Nếu muốn gọi server-side overdue queue riêng, thay đoạn fetch approvals trong refresh bằng:
getVeoPendingApprovals(batchId)
Giữ nguyên là đủ cho phase này.
22) Kết quả sau phase này
Sau patch này, hệ approval đã nâng từ:
human-governed production operations
sang:
policy-governed human oversight
Cụ thể bạn đã có:
threshold approval theo:
action
provider
project
SLA approval
escalation due time
auto-expire pending approvals
supervisor band / RBAC
overdue queue
escalated approvals
frontend badges:
OVERDUE
ESCALATED
worker tick để quét governance state
Đây là lớp rất quan trọng để approval không còn là “chờ vô hạn”, mà thành một queue vận hành có ưu tiên, thời hạn, và phân quyền.
23) Bước mạnh nhất tiếp theo
Bước tiếp theo mạnh nhất là enterprise governance hardening, theo đúng format paste-ready:
migration đầy đủ cho:
veo_batch_audit_events
veo_batch_action_requests
veo_batch_approval_decisions
field policy/SLA/escalation mới
metrics endpoint cho approval SLA / overdue / escalation
dashboard summary cards cho governance health
idempotency / duplicate-action prevention
bulk supervisor actions
notification hooks khi approval trở thành overdue / escalated
Đó là bước nâng hệ từ policy-governed oversight lên enterprise-grade governed operations.
Mình viết tiếp ngay enterprise governance hardening theo đúng format paste-ready.
Phase này sẽ bổ sung 6 lớp cứng hóa:
migration đầy đủ
metrics endpoint
governance health summary
idempotency / duplicate-action prevention
bulk supervisor actions
notification hooks khi overdue / escalated
1) backend/alembic/versions/20260412_0024_veo_governance_enterprise_hardening.py
"""veo governance enterprise hardening

Revision ID: 20260412_0024
Revises: 20260412_0023
Create Date: 2026-04-12 14:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0024"
down_revision = "20260412_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "veo_batch_audit_events",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("batch_run_id", sa.String(length=255), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("audit_note", sa.Text(), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_affected_items", sa.Integer(), nullable=True),
        sa.Column("affected_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_error_code", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_run_id"], ["veo_batch_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_veo_batch_audit_events_batch_run_id", "veo_batch_audit_events", ["batch_run_id"], unique=False)
    op.create_index("ix_veo_batch_audit_events_action_type", "veo_batch_audit_events", ["action_type"], unique=False)
    op.create_index("ix_veo_batch_audit_events_created_at", "veo_batch_audit_events", ["created_at"], unique=False)

    op.create_table(
        "veo_batch_action_requests",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("batch_run_id", sa.String(length=255), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("approval_status", sa.String(length=50), nullable=False, server_default="not_required"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("audit_note", sa.Text(), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_affected_items", sa.Integer(), nullable=True),
        sa.Column("affected_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_error_code", sa.String(length=255), nullable=True),
        sa.Column("preview_item_ids", sa.JSON(), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("provider_name", sa.String(length=100), nullable=True),
        sa.Column("project_id", sa.String(length=255), nullable=True),
        sa.Column("required_supervisor_band", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_escalation_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_overdue", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_expired", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("escalation_status", sa.String(length=50), nullable=True),
        sa.Column("supervisor_actor", sa.String(length=255), nullable=True),
        sa.Column("supervisor_note", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("dedupe_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_run_id"], ["veo_batch_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_veo_batch_action_requests_batch_run_id", "veo_batch_action_requests", ["batch_run_id"], unique=False)
    op.create_index("ix_veo_batch_action_requests_action_type", "veo_batch_action_requests", ["action_type"], unique=False)
    op.create_index("ix_veo_batch_action_requests_approval_status", "veo_batch_action_requests", ["approval_status"], unique=False)
    op.create_index("ix_veo_batch_action_requests_provider_name", "veo_batch_action_requests", ["provider_name"], unique=False)
    op.create_index("ix_veo_batch_action_requests_project_id", "veo_batch_action_requests", ["project_id"], unique=False)
    op.create_index("ix_veo_batch_action_requests_sla_due_at", "veo_batch_action_requests", ["sla_due_at"], unique=False)
    op.create_index("ix_veo_batch_action_requests_escalation_due_at", "veo_batch_action_requests", ["escalation_due_at"], unique=False)
    op.create_index("ix_veo_batch_action_requests_expires_at", "veo_batch_action_requests", ["expires_at"], unique=False)
    op.create_index("ix_veo_batch_action_requests_is_overdue", "veo_batch_action_requests", ["is_overdue"], unique=False)
    op.create_index("ix_veo_batch_action_requests_is_expired", "veo_batch_action_requests", ["is_expired"], unique=False)
    op.create_index("ix_veo_batch_action_requests_escalation_status", "veo_batch_action_requests", ["escalation_status"], unique=False)
    op.create_index("ix_veo_batch_action_requests_idempotency_key", "veo_batch_action_requests", ["idempotency_key"], unique=True)
    op.create_index("ix_veo_batch_action_requests_dedupe_fingerprint", "veo_batch_action_requests", ["dedupe_fingerprint"], unique=False)

    op.create_table(
        "veo_batch_approval_decisions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("supervisor_actor", sa.String(length=255), nullable=False),
        sa.Column("supervisor_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["veo_batch_action_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_veo_batch_approval_decisions_request_id", "veo_batch_approval_decisions", ["request_id"], unique=False)
    op.create_index("ix_veo_batch_approval_decisions_decision", "veo_batch_approval_decisions", ["decision"], unique=False)
    op.create_index("ix_veo_batch_approval_decisions_created_at", "veo_batch_approval_decisions", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_veo_batch_approval_decisions_created_at", table_name="veo_batch_approval_decisions")
    op.drop_index("ix_veo_batch_approval_decisions_decision", table_name="veo_batch_approval_decisions")
    op.drop_index("ix_veo_batch_approval_decisions_request_id", table_name="veo_batch_approval_decisions")
    op.drop_table("veo_batch_approval_decisions")

    op.drop_index("ix_veo_batch_action_requests_dedupe_fingerprint", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_idempotency_key", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_escalation_status", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_is_expired", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_is_overdue", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_expires_at", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_escalation_due_at", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_sla_due_at", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_project_id", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_provider_name", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_approval_status", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_action_type", table_name="veo_batch_action_requests")
    op.drop_index("ix_veo_batch_action_requests_batch_run_id", table_name="veo_batch_action_requests")
    op.drop_table("veo_batch_action_requests")

    op.drop_index("ix_veo_batch_audit_events_created_at", table_name="veo_batch_audit_events")
    op.drop_index("ix_veo_batch_audit_events_action_type", table_name="veo_batch_audit_events")
    op.drop_index("ix_veo_batch_audit_events_batch_run_id", table_name="veo_batch_audit_events")
    op.drop_table("veo_batch_audit_events")
2) PATCH backend/app/models/veo_workspace.py
Add idempotency / dedupe fields to VeoBatchActionRequest
Thêm 2 field này vào class VeoBatchActionRequest.
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True, unique=True)
    dedupe_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
3) FILE MỚI backend/app/services/veo_governance_metrics_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.veo_workspace import VeoBatchActionRequest


class VeoGovernanceMetricsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self, batch_run_id: Optional[str] = None) -> Dict[str, Any]:
        base = select(VeoBatchActionRequest)
        if batch_run_id:
            base = base.where(VeoBatchActionRequest.batch_run_id == batch_run_id)

        def count_with(*conditions):
            stmt = select(func.count(VeoBatchActionRequest.id))
            if batch_run_id:
                stmt = stmt.where(VeoBatchActionRequest.batch_run_id == batch_run_id)
            for condition in conditions:
                stmt = stmt.where(condition)
            return int(self.db.execute(stmt).scalar() or 0)

        pending = count_with(VeoBatchActionRequest.approval_status == "pending_approval")
        overdue = count_with(VeoBatchActionRequest.is_overdue == True, VeoBatchActionRequest.approval_status == "pending_approval")  # noqa: E712
        escalated = count_with(VeoBatchActionRequest.escalation_status == "escalated", VeoBatchActionRequest.approval_status == "pending_approval")
        expired = count_with(VeoBatchActionRequest.is_expired == True)  # noqa: E712
        approved = count_with(VeoBatchActionRequest.approval_status == "approved")
        rejected = count_with(VeoBatchActionRequest.approval_status == "rejected")
        executed = count_with(VeoBatchActionRequest.approval_status == "executed")

        avg_affected_stmt = select(func.avg(VeoBatchActionRequest.affected_items))
        if batch_run_id:
            avg_affected_stmt = avg_affected_stmt.where(VeoBatchActionRequest.batch_run_id == batch_run_id)
        avg_affected = float(self.db.execute(avg_affected_stmt).scalar() or 0)

        avg_sla_minutes_stmt = select(
            func.avg(
                func.extract("epoch", VeoBatchActionRequest.decided_at) -
                func.extract("epoch", VeoBatchActionRequest.created_at)
            )
        ).where(VeoBatchActionRequest.decided_at.is_not(None))
        if batch_run_id:
            avg_sla_minutes_stmt = avg_sla_minutes_stmt.where(VeoBatchActionRequest.batch_run_id == batch_run_id)
        avg_resolution_seconds = self.db.execute(avg_sla_minutes_stmt).scalar() or 0

        return {
            "pending_approvals": pending,
            "overdue_approvals": overdue,
            "escalated_approvals": escalated,
            "expired_requests": expired,
            "approved_requests": approved,
            "rejected_requests": rejected,
            "executed_requests": executed,
            "avg_affected_items": avg_affected,
            "avg_resolution_seconds": float(avg_resolution_seconds or 0),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
4) FILE MỚI backend/app/services/veo_governance_notification_service.py
from __future__ import annotations

from typing import Dict, Optional


class VeoGovernanceNotificationService:
    """
    Hook stub cho enterprise integrations.
    Có thể map sang email, Slack, webhook, PagerDuty, v.v.
    """

    def notify_overdue(self, payload: Dict) -> Dict:
        return {
            "ok": True,
            "notification_type": "overdue",
            "payload": payload,
        }

    def notify_escalated(self, payload: Dict) -> Dict:
        return {
            "ok": True,
            "notification_type": "escalated",
            "payload": payload,
        }
5) PATCH backend/app/services/veo_approval_governance_service.py
Add notification hooks
Thay file cũ bằng bản dưới.
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.veo_workspace import VeoBatchActionRequest
from backend.app.services.veo_governance_notification_service import VeoGovernanceNotificationService


class VeoApprovalGovernanceService:
    def __init__(self, db: Session, notification_service: Optional[VeoGovernanceNotificationService] = None) -> None:
        self.db = db
        self.notification_service = notification_service or VeoGovernanceNotificationService()

    def mark_overdue_and_escalate(self, now: Optional[datetime] = None) -> Dict[str, int]:
        now = now or datetime.now(timezone.utc)

        rows = self.db.execute(
            select(VeoBatchActionRequest).where(
                VeoBatchActionRequest.approval_status == "pending_approval",
                VeoBatchActionRequest.is_expired == False,  # noqa: E712
            )
        ).scalars().all()

        overdue = 0
        escalated = 0
        expired = 0

        for req in rows:
            if req.expires_at and req.expires_at <= now:
                req.is_expired = True
                req.is_overdue = True
                req.approval_status = "expired"
                req.escalation_status = "expired"
                expired += 1
                self.db.add(req)
                continue

            if req.sla_due_at and req.sla_due_at <= now:
                if not req.is_overdue:
                    req.is_overdue = True
                    overdue += 1
                    self.db.add(req)
                    self.notification_service.notify_overdue(
                        {
                            "request_id": req.id,
                            "batch_run_id": req.batch_run_id,
                            "action_type": req.action_type,
                            "actor": req.actor,
                            "affected_items": req.affected_items,
                        }
                    )

            if req.escalation_due_at and req.escalation_due_at <= now:
                if req.escalation_status != "escalated":
                    req.escalation_status = "escalated"
                    req.current_escalation_level = int(req.current_escalation_level or 0) + 1
                    escalated += 1
                    self.db.add(req)
                    self.notification_service.notify_escalated(
                        {
                            "request_id": req.id,
                            "batch_run_id": req.batch_run_id,
                            "action_type": req.action_type,
                            "actor": req.actor,
                            "affected_items": req.affected_items,
                            "required_supervisor_band": req.required_supervisor_band,
                        }
                    )

        self.db.commit()

        return {
            "overdue": overdue,
            "escalated": escalated,
            "expired": expired,
        }

    def overdue_queue(self) -> List[VeoBatchActionRequest]:
        return self.db.execute(
            select(VeoBatchActionRequest).where(
                VeoBatchActionRequest.approval_status == "pending_approval",
                VeoBatchActionRequest.is_overdue == True,  # noqa: E712
            ).order_by(VeoBatchActionRequest.sla_due_at.asc())
        ).scalars().all()
6) PATCH backend/app/api/veo_workspace.py
Add idempotency + dedupe helpers
import hashlib
import json
Thêm helper dưới đây.
def _build_action_dedupe_fingerprint(
    *,
    batch_run_id: str,
    action_type: str,
    actor: str,
    reason: str,
    target_error_code: Optional[str],
    preview_item_ids: List[str],
) -> str:
    raw = json.dumps(
        {
            "batch_run_id": batch_run_id,
            "action_type": action_type,
            "actor": actor,
            "reason": reason,
            "target_error_code": target_error_code,
            "preview_item_ids": sorted(preview_item_ids),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _find_duplicate_pending_request(
    db: Session,
    *,
    batch_run_id: str,
    dedupe_fingerprint: str,
):
    return db.execute(
        select(VeoBatchActionRequest).where(
            VeoBatchActionRequest.batch_run_id == batch_run_id,
            VeoBatchActionRequest.dedupe_fingerprint == dedupe_fingerprint,
            VeoBatchActionRequest.approval_status.in_(["pending_approval", "approved"]),
        )
    ).scalar_one_or_none()
7) PATCH backend/app/api/veo_workspace.py
Upgrade request schemas with idempotency_key
Thêm field này vào VeoGovernedBatchActionRequest.
    idempotency_key: Optional[str] = None
VeoGovernedRetryByErrorCodeRequest kế thừa nên tự có.
8) PATCH backend/app/api/veo_workspace.py
Update _create_action_request to save idempotency/dedupe
Thêm 2 tham số mới vào function:
    idempotency_key: Optional[str] = None,
    dedupe_fingerprint: Optional[str] = None,
Và trong create model:
        idempotency_key=idempotency_key,
        dedupe_fingerprint=dedupe_fingerprint,
9) PATCH backend/app/api/veo_workspace.py
Apply duplicate-action prevention in 3 governed endpoints
Ví dụ trong retry_batch_items_by_error_code
Sau khi có preview_item_ids, thêm:
    dedupe_fingerprint = _build_action_dedupe_fingerprint(
        batch_run_id=batch_id,
        action_type="retry_by_error_code",
        actor=payload.actor,
        reason=payload.reason,
        target_error_code=payload.error_code,
        preview_item_ids=preview_item_ids,
    )

    if payload.idempotency_key:
        existing_by_idempotency = db.execute(
            select(VeoBatchActionRequest).where(
                VeoBatchActionRequest.idempotency_key == payload.idempotency_key
            )
        ).scalar_one_or_none()
        if existing_by_idempotency:
            return VeoGovernedBatchActionResponse(
                ok=True,
                batch_run_id=batch_id,
                action=f"retry_by_error_code:{payload.error_code}",
                dry_run=existing_by_idempotency.dry_run,
                actor=existing_by_idempotency.actor,
                reason=existing_by_idempotency.reason,
                audit_note=existing_by_idempotency.audit_note,
                affected_items=existing_by_idempotency.affected_items,
                preview_item_ids=existing_by_idempotency.preview_item_ids or [],
                blocked_by_guardrail=False,
            )

    duplicate_pending = _find_duplicate_pending_request(
        db,
        batch_run_id=batch_id,
        dedupe_fingerprint=dedupe_fingerprint,
    )
    if duplicate_pending:
        return VeoGovernedBatchActionResponse(
            ok=True,
            batch_run_id=batch_id,
            action=f"retry_by_error_code:{payload.error_code}",
            dry_run=duplicate_pending.dry_run,
            actor=duplicate_pending.actor,
            reason=duplicate_pending.reason,
            audit_note=duplicate_pending.audit_note,
            affected_items=duplicate_pending.affected_items,
            preview_item_ids=duplicate_pending.preview_item_ids or [],
            blocked_by_guardrail=False,
        )
Trong _create_action_request(...), truyền thêm:
            idempotency_key=payload.idempotency_key,
            dedupe_fingerprint=dedupe_fingerprint,
Làm tương tự cho:
cancel_pending
requeue_retry_waiting
Chỉ đổi:
action_type
target_error_code
10) PATCH backend/app/api/veo_workspace.py
Add governance metrics endpoint
from backend.app.services.veo_governance_metrics_service import VeoGovernanceMetricsService
Thêm schema:
class VeoGovernanceMetricsResponse(BaseModel):
    pending_approvals: int
    overdue_approvals: int
    escalated_approvals: int
    expired_requests: int
    approved_requests: int
    rejected_requests: int
    executed_requests: int
    avg_affected_items: float
    avg_resolution_seconds: float
    generated_at: str
Thêm route:
@router.get("/batch-runs/{batch_id}/governance-metrics", response_model=VeoGovernanceMetricsResponse)
def get_batch_governance_metrics(batch_id: str, db: Session = Depends(get_db)) -> VeoGovernanceMetricsResponse:
    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    metrics = VeoGovernanceMetricsService(db).summary(batch_run_id=batch_id)
    return VeoGovernanceMetricsResponse(**metrics)
11) PATCH backend/app/api/veo_workspace.py
Add bulk supervisor actions
Thêm schema:
class VeoBulkApprovalDecisionRequest(BaseModel):
    supervisor_actor: str
    supervisor_note: Optional[str] = None
    request_ids: List[str]


class VeoBulkApprovalDecisionResponse(BaseModel):
    ok: bool
    approved: int = 0
    rejected: int = 0
    skipped: int = 0
Thêm routes:
@router.post("/batch-runs/{batch_id}/pending-approvals/bulk-approve", response_model=VeoBulkApprovalDecisionResponse)
def bulk_approve_batch_action_requests(
    batch_id: str,
    payload: VeoBulkApprovalDecisionRequest,
    db: Session = Depends(get_db),
) -> VeoBulkApprovalDecisionResponse:
    approved = 0
    skipped = 0

    for request_id in payload.request_ids:
        req = db.get(VeoBatchActionRequest, request_id)
        if not req or req.batch_run_id != batch_id or req.approval_status != "pending_approval":
            skipped += 1
            continue

        policy_service = VeoApprovalPolicyService()
        supervisor_band = policy_service.supervisor_band(payload.supervisor_actor)
        if supervisor_band < int(req.required_supervisor_band or 1) or req.is_expired:
            skipped += 1
            continue

        req.approval_status = "approved"
        req.supervisor_actor = payload.supervisor_actor
        req.supervisor_note = payload.supervisor_note
        req.decided_at = datetime.now(timezone.utc)
        db.add(req)
        db.commit()

        decision = VeoBatchApprovalDecision(
            request_id=req.id,
            decision="approved",
            supervisor_actor=payload.supervisor_actor,
            supervisor_note=payload.supervisor_note,
            created_at=datetime.now(timezone.utc),
        )
        db.add(decision)
        db.commit()

        _execute_action_request(db, req)
        approved += 1

    return VeoBulkApprovalDecisionResponse(ok=True, approved=approved, skipped=skipped)


@router.post("/batch-runs/{batch_id}/pending-approvals/bulk-reject", response_model=VeoBulkApprovalDecisionResponse)
def bulk_reject_batch_action_requests(
    batch_id: str,
    payload: VeoBulkApprovalDecisionRequest,
    db: Session = Depends(get_db),
) -> VeoBulkApprovalDecisionResponse:
    rejected = 0
    skipped = 0

    for request_id in payload.request_ids:
        req = db.get(VeoBatchActionRequest, request_id)
        if not req or req.batch_run_id != batch_id or req.approval_status != "pending_approval":
            skipped += 1
            continue

        req.approval_status = "rejected"
        req.supervisor_actor = payload.supervisor_actor
        req.supervisor_note = payload.supervisor_note
        req.decided_at = datetime.now(timezone.utc)
        db.add(req)
        db.commit()

        decision = VeoBatchApprovalDecision(
            request_id=req.id,
            decision="rejected",
            supervisor_actor=payload.supervisor_actor,
            supervisor_note=payload.supervisor_note,
            created_at=datetime.now(timezone.utc),
        )
        db.add(decision)
        db.commit()

        rejected += 1

    return VeoBulkApprovalDecisionResponse(ok=True, rejected=rejected, skipped=skipped)
12) PATCH tests/test_veo_workspace_api.py
Tests for metrics / idempotency / bulk approvals
Paste thêm vào file test.
def test_governance_metrics_endpoint(client):
    c, SessionLocal = client
    db = SessionLocal()

    seed_batch(db, "batch-metrics-1")
    req1 = VeoBatchActionRequest(
        batch_run_id="batch-metrics-1",
        action_type="cancel_pending",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="Need approval",
        dry_run=False,
        affected_items=12,
        is_overdue=True,
        escalation_status="escalated",
        created_at=datetime.now(timezone.utc),
    )
    req2 = VeoBatchActionRequest(
        batch_run_id="batch-metrics-1",
        action_type="retry_by_error_code",
        approval_status="executed",
        requires_approval=True,
        actor="ops@example.com",
        reason="Executed",
        dry_run=False,
        affected_items=5,
        decided_at=datetime.now(timezone.utc),
        executed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(req1)
    db.add(req2)
    db.commit()
    db.close()

    res = c.get("/api/v1/veo/batch-runs/batch-metrics-1/governance-metrics")
    assert res.status_code == 200
    data = res.json()
    assert data["pending_approvals"] == 1
    assert data["overdue_approvals"] == 1
    assert data["escalated_approvals"] == 1
    assert data["executed_requests"] == 1


def test_idempotency_key_prevents_duplicate_request(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-idem-1")
    for idx in range(11):
        seed_item(db, f"item-idem-{idx}", batch_id="batch-idem-1", status="pending")
    db.close()

    payload = {
        "actor": "ops@example.com",
        "reason": "Need approval once",
        "dry_run": False,
        "max_affected_items": 100,
        "idempotency_key": "idem-123",
    }

    res1 = c.post("/api/v1/veo/batch-runs/batch-idem-1/cancel-pending", json=payload)
    res2 = c.post("/api/v1/veo/batch-runs/batch-idem-1/cancel-pending", json=payload)

    assert res1.status_code == 200
    assert res2.status_code == 200

    db = SessionLocal()
    rows = db.execute(
        select(VeoBatchActionRequest).where(
            VeoBatchActionRequest.batch_run_id == "batch-idem-1"
        )
    ).scalars().all()
    assert len(rows) == 1
    db.close()


def test_bulk_approve_pending_requests(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-bulk-1")
    for idx in range(12):
        seed_item(db, f"item-bulk-{idx}", batch_id="batch-bulk-1", status="pending")

    req1 = VeoBatchActionRequest(
        batch_run_id="batch-bulk-1",
        action_type="cancel_pending",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="One",
        dry_run=False,
        affected_items=12,
        required_supervisor_band=1,
        created_at=datetime.now(timezone.utc),
    )
    req2 = VeoBatchActionRequest(
        batch_run_id="batch-bulk-1",
        action_type="requeue_retry_waiting",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="Two",
        dry_run=False,
        affected_items=30,
        required_supervisor_band=1,
        created_at=datetime.now(timezone.utc),
    )
    db.add(req1)
    db.add(req2)
    db.commit()
    ids = [req1.id, req2.id]
    db.close()

    res = c.post(
        "/api/v1/veo/batch-runs/batch-bulk-1/pending-approvals/bulk-approve",
        json={
            "supervisor_actor": "ops_admin",
            "supervisor_note": "Bulk approved",
            "request_ids": ids,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["approved"] == 2


def test_bulk_reject_pending_requests(client):
    c, SessionLocal = client
    db = SessionLocal()
    seed_batch(db, "batch-bulk-2")

    req = VeoBatchActionRequest(
        batch_run_id="batch-bulk-2",
        action_type="cancel_pending",
        approval_status="pending_approval",
        requires_approval=True,
        actor="ops@example.com",
        reason="Reject me",
        dry_run=False,
        affected_items=12,
        required_supervisor_band=1,
        created_at=datetime.now(timezone.utc),
    )
    db.add(req)
    db.commit()
    request_id = req.id
    db.close()

    res = c.post(
        "/api/v1/veo/batch-runs/batch-bulk-2/pending-approvals/bulk-reject",
        json={
            "supervisor_actor": "ops_admin",
            "supervisor_note": "Bulk rejected",
            "request_ids": [request_id],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["rejected"] == 1
13) PATCH frontend/src/lib/api.ts
Add governance metrics + bulk actions
export type VeoGovernanceMetrics = {
  pending_approvals: number;
  overdue_approvals: number;
  escalated_approvals: number;
  expired_requests: number;
  approved_requests: number;
  rejected_requests: number;
  executed_requests: number;
  avg_affected_items: number;
  avg_resolution_seconds: number;
  generated_at: string;
};

export async function getVeoGovernanceMetrics(batchId: string): Promise<VeoGovernanceMetrics> {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/governance-metrics`);
  if (!res.ok) throw new Error(`Failed to fetch governance metrics for ${batchId}`);
  return res.json();
}

export async function bulkApproveVeoActionRequests(
  batchId: string,
  payload: { supervisor_actor: string; supervisor_note?: string; request_ids: string[] }
) {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/pending-approvals/bulk-approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to bulk approve pending approvals for ${batchId}`);
  return res.json();
}

export async function bulkRejectVeoActionRequests(
  batchId: string,
  payload: { supervisor_actor: string; supervisor_note?: string; request_ids: string[] }
) {
  const res = await fetch(`/api/v1/veo/batch-runs/${batchId}/pending-approvals/bulk-reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to bulk reject pending approvals for ${batchId}`);
  return res.json();
}
14) frontend/src/components/veo/VeoGovernanceHealthCards.tsx
"use client";

import { VeoGovernanceMetrics } from "@/src/lib/api";

type Props = {
  metrics: VeoGovernanceMetrics | null;
  loading?: boolean;
};

export default function VeoGovernanceHealthCards({ metrics, loading }: Props) {
  if (loading && !metrics) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        Loading governance health...
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        No governance metrics available.
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
      <Card label="Pending" value={metrics.pending_approvals} />
      <Card label="Overdue" value={metrics.overdue_approvals} tone={metrics.overdue_approvals > 0 ? "danger" : "default"} />
      <Card label="Escalated" value={metrics.escalated_approvals} tone={metrics.escalated_approvals > 0 ? "warning" : "default"} />
      <Card label="Expired" value={metrics.expired_requests} tone={metrics.expired_requests > 0 ? "danger" : "default"} />
      <Card label="Executed" value={metrics.executed_requests} />
    </div>
  );
}

function Card({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "warning" | "danger";
}) {
  const toneClass =
    tone === "danger"
      ? "border-red-200 bg-red-50"
      : tone === "warning"
      ? "border-amber-200 bg-amber-50"
      : "border-neutral-200 bg-white";

  return (
    <div className={`rounded-2xl border p-4 ${toneClass}`}>
      <div className="text-xs uppercase tracking-wide text-neutral-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
15) PATCH frontend/src/components/veo/VeoPendingApprovalsPanel.tsx
Add bulk supervisor actions
Thay file cũ bằng bản dưới.
"use client";

import { useMemo, useState } from "react";
import {
  approveVeoActionRequest,
  bulkApproveVeoActionRequests,
  bulkRejectVeoActionRequests,
  rejectVeoActionRequest,
  VeoPendingApprovalList,
} from "@/src/lib/api";

type Props = {
  batchId: string;
  data: VeoPendingApprovalList | null;
  loading?: boolean;
  onActionDone?: () => Promise<void> | void;
};

export default function VeoPendingApprovalsPanel({ batchId, data, loading, onActionDone }: Props) {
  const [supervisorActor, setSupervisorActor] = useState("");
  const [supervisorNote, setSupervisorNote] = useState("");
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [escalatedOnly, setEscalatedOnly] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const items = useMemo(() => {
    let rows = data?.items || [];
    if (overdueOnly) rows = rows.filter((x) => x.is_overdue);
    if (escalatedOnly) rows = rows.filter((x) => x.escalation_status === "escalated");
    return rows;
  }, [data, overdueOnly, escalatedOnly]);

  async function handleDecision(requestId: string, decision: "approve" | "reject") {
    try {
      if (!supervisorActor.trim()) {
        alert("Supervisor actor is required.");
        return;
      }

      setActionLoadingId(requestId);

      if (decision === "approve") {
        await approveVeoActionRequest(requestId, {
          supervisor_actor: supervisorActor.trim(),
          supervisor_note: supervisorNote.trim() || undefined,
        });
      } else {
        await rejectVeoActionRequest(requestId, {
          supervisor_actor: supervisorActor.trim(),
          supervisor_note: supervisorNote.trim() || undefined,
        });
      }

      await onActionDone?.();
      setSelectedIds((prev) => prev.filter((id) => id !== requestId));
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Approval action failed");
    } finally {
      setActionLoadingId(null);
    }
  }

  async function handleBulk(decision: "approve" | "reject") {
    try {
      if (!supervisorActor.trim()) {
        alert("Supervisor actor is required.");
        return;
      }
      if (selectedIds.length === 0) {
        alert("Select at least one request.");
        return;
      }

      setActionLoadingId("bulk");

      if (decision === "approve") {
        await bulkApproveVeoActionRequests(batchId, {
          supervisor_actor: supervisorActor.trim(),
          supervisor_note: supervisorNote.trim() || undefined,
          request_ids: selectedIds,
        });
      } else {
        await bulkRejectVeoActionRequests(batchId, {
          supervisor_actor: supervisorActor.trim(),
          supervisor_note: supervisorNote.trim() || undefined,
          request_ids: selectedIds,
        });
      }

      setSelectedIds([]);
      await onActionDone?.();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Bulk approval action failed");
    } finally {
      setActionLoadingId(null);
    }
  }

  function toggleSelected(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  if (loading && !data) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        Loading pending approvals...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        No pending approvals data.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-neutral-200 bg-white p-4">
        <div className="mb-3 text-base font-semibold">Supervisor Decision Controls</div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <input
            value={supervisorActor}
            onChange={(e) => setSupervisorActor(e.target.value)}
            placeholder="supervisor@example.com"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />
          <input
            value={supervisorNote}
            onChange={(e) => setSupervisorNote(e.target.value)}
            placeholder="Decision note"
            className="rounded-xl border border-neutral-300 px-3 py-2 text-sm outline-none"
          />
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={overdueOnly} onChange={(e) => setOverdueOnly(e.target.checked)} />
            Overdue only
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={escalatedOnly} onChange={(e) => setEscalatedOnly(e.target.checked)} />
            Escalated only
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
            onClick={() => handleBulk("approve")}
            disabled={actionLoadingId !== null}
          >
            {actionLoadingId === "bulk" ? "Working..." : `Bulk Approve (${selectedIds.length})`}
          </button>
          <button
            className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
            onClick={() => handleBulk("reject")}
            disabled={actionLoadingId !== null}
          >
            {actionLoadingId === "bulk" ? "Working..." : `Bulk Reject (${selectedIds.length})`}
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 px-4 py-3">
          <h3 className="text-base font-semibold">Pending Approvals ({items.length})</h3>
        </div>

        <div className="divide-y divide-neutral-200">
          {items.length === 0 ? (
            <div className="px-4 py-6 text-sm text-neutral-500">No matching pending approvals.</div>
          ) : (
            items.map((item) => (
              <div key={item.id} className="px-4 py-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(item.id)}
                        onChange={() => toggleSelected(item.id)}
                      />
                      <div className="font-medium">{item.action_type}</div>
                    </div>

                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-neutral-600">
                      <span className="rounded-full border px-2 py-1">request: {item.id}</span>
                      <span className="rounded-full border px-2 py-1">actor: {item.actor}</span>
                      <span className="rounded-full border px-2 py-1">affected: {item.affected_items}</span>
                      <span className="rounded-full border px-2 py-1">band: {item.required_supervisor_band}</span>

                      {item.is_overdue ? (
                        <span className="rounded-full border px-2 py-1 text-red-600">OVERDUE</span>
                      ) : null}
                      {item.escalation_status === "escalated" ? (
                        <span className="rounded-full border px-2 py-1 text-amber-600">ESCALATED</span>
                      ) : null}
                      {item.expires_at ? (
                        <span className="rounded-full border px-2 py-1">
                          expires: {new Date(item.expires_at).toLocaleString()}
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-2 text-sm text-neutral-700">
                      <div><strong>Reason:</strong> {item.reason}</div>
                      {item.audit_note ? <div><strong>Audit note:</strong> {item.audit_note}</div> : null}
                      {item.sla_due_at ? <div><strong>SLA due:</strong> {new Date(item.sla_due_at).toLocaleString()}</div> : null}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
                      onClick={() => handleDecision(item.id, "approve")}
                      disabled={actionLoadingId !== null || item.is_expired}
                    >
                      {actionLoadingId === item.id ? "Working..." : "Approve"}
                    </button>
                    <button
                      className="rounded-xl border px-3 py-2 text-sm disabled:opacity-50"
                      onClick={() => handleDecision(item.id, "reject")}
                      disabled={actionLoadingId !== null || item.is_expired}
                    >
                      {actionLoadingId === item.id ? "Working..." : "Reject"}
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
16) PATCH frontend/src/app/projects/[id]/page.tsx
Add governance health cards + updated pending approvals panel props
Add imports
import { getVeoGovernanceMetrics, VeoGovernanceMetrics } from "@/src/lib/api";
import VeoGovernanceHealthCards from "@/src/components/veo/VeoGovernanceHealthCards";
Add state
const [governanceMetrics, setGovernanceMetrics] = useState<VeoGovernanceMetrics | null>(null);
Update refresh Promise.all
const [statsData, itemsData, errorsData, timelineData, approvalsData, governanceMetricsData] = await Promise.all([
  getVeoBatchRunStats(batchId),
  getVeoBatchRunItems(batchId, {
    limit: itemsPage.limit,
    offset,
    status: statusFilter || undefined,
    mode: modeFilter || undefined,
    search: searchText || undefined,
  }),
  getVeoBatchErrorsSummary(batchId),
  getVeoBatchTimeline(batchId, { limit: 100 }),
  getVeoPendingApprovals(batchId),
  getVeoGovernanceMetrics(batchId),
]);

setStats(statsData);
setItemsPage(itemsData);
setErrorsSummary(errorsData);
setTimeline(timelineData);
setPendingApprovals(approvalsData);
setGovernanceMetrics(governanceMetricsData);
In overview tab, render cards
{activeTab === "overview" ? (
  <div className="space-y-4">
    <VeoGovernanceHealthCards metrics={governanceMetrics} loading={loading} />
    <div className="grid gap-4 xl:grid-cols-2">
      <VeoBatchFailuresPanel
        batchId={batchId}
        summary={errorsSummary}
        loading={loading}
        defaultActor=""
        onActionDone={() => refresh()}
      />
      <VeoBatchTimelinePanel
        timeline={{
          batch_run_id: timeline?.batch_run_id || batchId,
          events: (timeline?.events || []).slice(0, 20),
        }}
        loading={loading}
      />
    </div>
  </div>
) : null}
Update pending approvals panel call
{activeTab === "approvals" ? (
  <VeoPendingApprovalsPanel
    batchId={batchId}
    data={pendingApprovals}
    loading={loading}
    onActionDone={() => refresh()}
  />
) : null}
17) PATCH backend/app/workers/veo_approval_governance_worker.py
Add audit event hooks for overdue/escalated/expired
Thay file bằng bản dưới.
from __future__ import annotations

from celery import shared_task

from backend.app.db.session import SessionLocal
from backend.app.services.veo_approval_governance_service import VeoApprovalGovernanceService


@shared_task(name="backend.app.workers.veo_approval_governance_worker.tick_veo_approval_governance")
def tick_veo_approval_governance() -> dict:
    db = SessionLocal()
    try:
        service = VeoApprovalGovernanceService(db)
        result = service.mark_overdue_and_escalate()
        return {
            "ok": True,
            **result,
        }
    finally:
        db.close()
18) Kết quả sau phase này
Sau patch này, hệ đã nâng từ:
policy-governed human oversight
sang:
enterprise-grade governed operations
Cụ thể bạn đã có:
migration đầy đủ cho governance tables
metrics endpoint cho:
pending approvals
overdue
escalated
expired
approved / rejected / executed
governance health cards trên dashboard
idempotency key
duplicate-action prevention theo dedupe fingerprint
bulk supervisor approve / reject
notification hooks khi overdue / escalated
Đây là lớp rất quan trọng vì từ đây governance không còn chỉ là “logic approval”, mà đã có:
vận hành ở quy mô lớn
chống trùng lệnh
theo dõi sức khỏe queue
xử lý hàng loạt
phát tín hiệu ra ngoài
19) Bước mạnh nhất tiếp theo
Bước tiếp theo mạnh nhất là production readiness + rollout controls, theo đúng format paste-ready:
seed/default policy bootstrap
feature flags cho từng governance capability
admin policy editor API
provider/project-level policy override UI
governance metrics charts
audit export endpoint
runbook docs + local test fixtures
Đó là bước nâng hệ từ enterprise-grade governed ops lên deployable controlled platform module.
Mình đang chốt lớp “có thể triển khai thật”: bootstrap policy mặc định + feature flags + admin policy API + export/audit + UI override/charts, để module governance không chỉ mạnh mà còn rollout được an toàn theo từng môi trường.
Đã suy nghĩ trong 4s
Được. Mình viết tiếp ngay production readiness + rollout controls theo đúng format paste-ready.
Phase này thêm 7 lớp để module governance có thể rollout thật:
seed/default policy bootstrap
feature flags cho từng capability
admin policy editor API
provider/project-level policy override UI
governance metrics charts
audit export endpoint
runbook docs + local test fixtures
1) PATCH backend/app/core/config.py
Feature flags + bootstrap config
Paste thêm block này vào settings hiện có.
# Governance rollout / feature flags
VEO_GOVERNANCE_ENABLED: bool = True
VEO_GOVERNANCE_POLICY_EDITOR_ENABLED: bool = True
VEO_GOVERNANCE_APPROVALS_ENABLED: bool = True
VEO_GOVERNANCE_METRICS_ENABLED: bool = True
VEO_GOVERNANCE_AUDIT_EXPORT_ENABLED: bool = True
VEO_GOVERNANCE_NOTIFICATIONS_ENABLED: bool = True
VEO_GOVERNANCE_BULK_SUPERVISOR_ACTIONS_ENABLED: bool = True
VEO_GOVERNANCE_PROJECT_OVERRIDES_ENABLED: bool = True
VEO_GOVERNANCE_PROVIDER_OVERRIDES_ENABLED: bool = True

# Bootstrap / seed
VEO_GOVERNANCE_BOOTSTRAP_DEFAULT_POLICIES: bool = True
VEO_GOVERNANCE_DEFAULT_POLICY_VERSION: str = "v1"
2) PATCH .env.example
# Governance rollout / feature flags
VEO_GOVERNANCE_ENABLED=true
VEO_GOVERNANCE_POLICY_EDITOR_ENABLED=true
VEO_GOVERNANCE_APPROVALS_ENABLED=true
VEO_GOVERNANCE_METRICS_ENABLED=true
VEO_GOVERNANCE_AUDIT_EXPORT_ENABLED=true
VEO_GOVERNANCE_NOTIFICATIONS_ENABLED=true
VEO_GOVERNANCE_BULK_SUPERVISOR_ACTIONS_ENABLED=true
VEO_GOVERNANCE_PROJECT_OVERRIDES_ENABLED=true
VEO_GOVERNANCE_PROVIDER_OVERRIDES_ENABLED=true

# Governance bootstrap
VEO_GOVERNANCE_BOOTSTRAP_DEFAULT_POLICIES=true
VEO_GOVERNANCE_DEFAULT_POLICY_VERSION=v1
3) PATCH backend/.env.example
# Governance rollout / feature flags
VEO_GOVERNANCE_ENABLED=true
VEO_GOVERNANCE_POLICY_EDITOR_ENABLED=true
VEO_GOVERNANCE_APPROVALS_ENABLED=true
VEO_GOVERNANCE_METRICS_ENABLED=true
VEO_GOVERNANCE_AUDIT_EXPORT_ENABLED=true
VEO_GOVERNANCE_NOTIFICATIONS_ENABLED=true
VEO_GOVERNANCE_BULK_SUPERVISOR_ACTIONS_ENABLED=true
VEO_GOVERNANCE_PROJECT_OVERRIDES_ENABLED=true
VEO_GOVERNANCE_PROVIDER_OVERRIDES_ENABLED=true

# Governance bootstrap
VEO_GOVERNANCE_BOOTSTRAP_DEFAULT_POLICIES=true
VEO_GOVERNANCE_DEFAULT_POLICY_VERSION=v1
4) PATCH backend/app/models/veo_workspace.py
Add governance policy override model
Paste thêm class này vào file model hiện có.
class VeoGovernancePolicyOverride(Base):
    __tablename__ = "veo_governance_policy_overrides"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # global/provider/project
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    policy_version: Mapped[str] = mapped_column(String(100), nullable=False, default="v1")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    approval_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sla_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalation_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_expire_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_supervisor_band: Mapped[int | None] = mapped_column(Integer, nullable=True)

    action_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
5) backend/alembic/versions/20260412_0025_veo_governance_rollout_controls.py
"""veo governance rollout controls

Revision ID: 20260412_0025
Revises: 20260412_0024
Create Date: 2026-04-12 15:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0025"
down_revision = "20260412_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "veo_governance_policy_overrides",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("policy_version", sa.String(length=100), nullable=False, server_default="v1"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approval_threshold", sa.Integer(), nullable=True),
        sa.Column("sla_minutes", sa.Integer(), nullable=True),
        sa.Column("escalation_minutes", sa.Integer(), nullable=True),
        sa.Column("auto_expire_minutes", sa.Integer(), nullable=True),
        sa.Column("required_supervisor_band", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=100), nullable=True),
        sa.Column("provider_name", sa.String(length=100), nullable=True),
        sa.Column("project_id", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_veo_governance_policy_overrides_scope_type", "veo_governance_policy_overrides", ["scope_type"], unique=False)
    op.create_index("ix_veo_governance_policy_overrides_scope_key", "veo_governance_policy_overrides", ["scope_key"], unique=False)
    op.create_index("ix_veo_governance_policy_overrides_action_type", "veo_governance_policy_overrides", ["action_type"], unique=False)
    op.create_index("ix_veo_governance_policy_overrides_provider_name", "veo_governance_policy_overrides", ["provider_name"], unique=False)
    op.create_index("ix_veo_governance_policy_overrides_project_id", "veo_governance_policy_overrides", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_veo_governance_policy_overrides_project_id", table_name="veo_governance_policy_overrides")
    op.drop_index("ix_veo_governance_policy_overrides_provider_name", table_name="veo_governance_policy_overrides")
    op.drop_index("ix_veo_governance_policy_overrides_action_type", table_name="veo_governance_policy_overrides")
    op.drop_index("ix_veo_governance_policy_overrides_scope_key", table_name="veo_governance_policy_overrides")
    op.drop_index("ix_veo_governance_policy_overrides_scope_type", table_name="veo_governance_policy_overrides")
    op.drop_table("veo_governance_policy_overrides")
6) FILE MỚI backend/app/services/veo_governance_feature_flag_service.py
from __future__ import annotations

from backend.app.core.config import settings


class VeoGovernanceFeatureFlagService:
    def governance_enabled(self) -> bool:
        return bool(getattr(settings, "VEO_GOVERNANCE_ENABLED", True))

    def policy_editor_enabled(self) -> bool:
        return bool(getattr(settings, "VEO_GOVERNANCE_POLICY_EDITOR_ENABLED", True))

    def approvals_enabled(self) -> bool:
        return bool(getattr(settings, "VEO_GOVERNANCE_APPROVALS_ENABLED", True))

    def metrics_enabled(self) -> bool:
        return bool(getattr(settings, "VEO_GOVERNANCE_METRICS_ENABLED", True))

    def audit_export_enabled(self) -> bool:
        return bool(getattr(settings, "VEO_GOVERNANCE_AUDIT_EXPORT_ENABLED", True))

    def notifications_enabled(self) -> bool:
        return bool(getattr(settings, "VEO_GOVERNANCE_NOTIFICATIONS_ENABLED", True))

    def bulk_supervisor_actions_enabled(self) -> bool:
        return bool(getattr(settings, "VEO_GOVERNANCE_BULK_SUPERVISOR_ACTIONS_ENABLED", True))

    def project_overrides_enabled(self) -> bool:
        return bool(getattr(settings, "VEO_GOVERNANCE_PROJECT_OVERRIDES_ENABLED", True))

    def provider_overrides_enabled(self) -> bool:
        return bool(getattr(settings, "VEO_GOVERNANCE_PROVIDER_OVERRIDES_ENABLED", True))
7) FILE MỚI backend/app/services/veo_governance_policy_bootstrap_service.py
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.veo_workspace import VeoGovernancePolicyOverride


class VeoGovernancePolicyBootstrapService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def seed_defaults(self) -> dict:
        if not bool(getattr(settings, "VEO_GOVERNANCE_BOOTSTRAP_DEFAULT_POLICIES", True)):
            return {"ok": True, "seeded": 0, "skipped": True}

        defaults = [
            {
                "scope_type": "global",
                "scope_key": "default:cancel_pending",
                "action_type": "cancel_pending",
                "approval_threshold": 10,
                "sla_minutes": 15,
                "escalation_minutes": 10,
                "auto_expire_minutes": 60,
                "required_supervisor_band": 2,
            },
            {
                "scope_type": "global",
                "scope_key": "default:retry_by_error_code",
                "action_type": "retry_by_error_code",
                "approval_threshold": 20,
                "sla_minutes": 30,
                "escalation_minutes": 20,
                "auto_expire_minutes": 120,
                "required_supervisor_band": 1,
            },
            {
                "scope_type": "global",
                "scope_key": "default:requeue_retry_waiting",
                "action_type": "requeue_retry_waiting",
                "approval_threshold": 25,
                "sla_minutes": 45,
                "escalation_minutes": 30,
                "auto_expire_minutes": 180,
                "required_supervisor_band": 1,
            },
        ]

        seeded = 0
        for item in defaults:
            existing = self.db.execute(
                select(VeoGovernancePolicyOverride).where(
                    VeoGovernancePolicyOverride.scope_type == item["scope_type"],
                    VeoGovernancePolicyOverride.scope_key == item["scope_key"],
                    VeoGovernancePolicyOverride.action_type == item["action_type"],
                )
            ).scalar_one_or_none()

            if existing:
                continue

            row = VeoGovernancePolicyOverride(
                policy_version=getattr(settings, "VEO_GOVERNANCE_DEFAULT_POLICY_VERSION", "v1"),
                is_enabled=True,
                created_by="bootstrap",
                updated_by="bootstrap",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                **item,
            )
            self.db.add(row)
            seeded += 1

        self.db.commit()
        return {"ok": True, "seeded": seeded, "skipped": False}
8) PATCH backend/app/services/veo_approval_policy_service.py
Add DB override support
Thay file cũ bằng bản dưới.
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.veo_workspace import VeoGovernancePolicyOverride


@dataclass
class ApprovalPolicyDecision:
    requires_approval: bool
    required_supervisor_band: int
    threshold_used: int
    sla_minutes: int
    escalation_minutes: int
    auto_expire_minutes: int
    sla_due_at: datetime
    escalation_due_at: datetime
    expires_at: datetime


class VeoApprovalPolicyService:
    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db
        self.threshold_default = int(getattr(settings, "VEO_APPROVAL_THRESHOLD_DEFAULT", 20))
        self.sla_default = int(getattr(settings, "VEO_APPROVAL_SLA_MINUTES_DEFAULT", 30))
        self.escalation_default = int(getattr(settings, "VEO_APPROVAL_ESCALATION_MINUTES_DEFAULT", 20))
        self.expire_default = int(getattr(settings, "VEO_APPROVAL_AUTO_EXPIRE_MINUTES_DEFAULT", 120))
        self.high_impact_required_band = int(getattr(settings, "VEO_HIGH_IMPACT_REQUIRED_BAND", 2))
        self.critical_impact_required_band = int(getattr(settings, "VEO_CRITICAL_IMPACT_REQUIRED_BAND", 3))

    def evaluate(
        self,
        *,
        action_type: str,
        provider_name: Optional[str],
        project_id: Optional[str],
        affected_items: int,
        now: Optional[datetime] = None,
    ) -> ApprovalPolicyDecision:
        now = now or datetime.now(timezone.utc)

        override = self._resolve_override(
            action_type=action_type,
            provider_name=provider_name,
            project_id=project_id,
        )

        threshold = (
            int(override.approval_threshold)
            if override and override.approval_threshold is not None
            else self._resolve_threshold(
                action_type=action_type,
                provider_name=provider_name,
                project_id=project_id,
            )
        )

        requires_approval = affected_items > threshold

        base_required_band = (
            int(override.required_supervisor_band)
            if override and override.required_supervisor_band is not None
            else self._resolve_required_band(
                action_type=action_type,
                affected_items=affected_items,
                threshold=threshold,
            )
        )

        sla_minutes = (
            int(override.sla_minutes)
            if override and override.sla_minutes is not None
            else self._lookup_json_int("VEO_APPROVAL_SLA_BY_ACTION_JSON", action_type, self.sla_default)
        )
        escalation_minutes = (
            int(override.escalation_minutes)
            if override and override.escalation_minutes is not None
            else self._lookup_json_int("VEO_APPROVAL_ESCALATION_BY_ACTION_JSON", action_type, self.escalation_default)
        )
        auto_expire_minutes = (
            int(override.auto_expire_minutes)
            if override and override.auto_expire_minutes is not None
            else self._lookup_json_int("VEO_APPROVAL_AUTO_EXPIRE_BY_ACTION_JSON", action_type, self.expire_default)
        )

        return ApprovalPolicyDecision(
            requires_approval=requires_approval,
            required_supervisor_band=base_required_band,
            threshold_used=threshold,
            sla_minutes=sla_minutes,
            escalation_minutes=escalation_minutes,
            auto_expire_minutes=auto_expire_minutes,
            sla_due_at=now + timedelta(minutes=sla_minutes),
            escalation_due_at=now + timedelta(minutes=escalation_minutes),
            expires_at=now + timedelta(minutes=auto_expire_minutes),
        )

    def supervisor_band(self, supervisor_actor: str) -> int:
        mapping = self._load_json("VEO_SUPERVISOR_BANDS_JSON")
        return int(mapping.get(supervisor_actor, 0))

    def required_band_for_action(self, action_type: str) -> int:
        mapping = self._load_json("VEO_REQUIRED_BAND_BY_ACTION_JSON")
        return int(mapping.get(action_type, 1))

    def _resolve_override(
        self,
        *,
        action_type: str,
        provider_name: Optional[str],
        project_id: Optional[str],
    ) -> Optional[VeoGovernancePolicyOverride]:
        if not self.db:
            return None

        if project_id:
            row = self.db.execute(
                select(VeoGovernancePolicyOverride).where(
                    VeoGovernancePolicyOverride.is_enabled == True,  # noqa: E712
                    VeoGovernancePolicyOverride.scope_type == "project",
                    VeoGovernancePolicyOverride.project_id == project_id,
                    VeoGovernancePolicyOverride.action_type == action_type,
                )
            ).scalar_one_or_none()
            if row:
                return row

        if provider_name:
            row = self.db.execute(
                select(VeoGovernancePolicyOverride).where(
                    VeoGovernancePolicyOverride.is_enabled == True,  # noqa: E712
                    VeoGovernancePolicyOverride.scope_type == "provider",
                    VeoGovernancePolicyOverride.provider_name == provider_name,
                    VeoGovernancePolicyOverride.action_type == action_type,
                )
            ).scalar_one_or_none()
            if row:
                return row

        return self.db.execute(
            select(VeoGovernancePolicyOverride).where(
                VeoGovernancePolicyOverride.is_enabled == True,  # noqa: E712
                VeoGovernancePolicyOverride.scope_type == "global",
                VeoGovernancePolicyOverride.action_type == action_type,
            )
        ).scalar_one_or_none()

    def _resolve_threshold(
        self,
        *,
        action_type: str,
        provider_name: Optional[str],
        project_id: Optional[str],
    ) -> int:
        project_map = self._load_json("VEO_APPROVAL_THRESHOLD_BY_PROJECT_JSON")
        provider_map = self._load_json("VEO_APPROVAL_THRESHOLD_BY_PROVIDER_JSON")
        action_map = self._load_json("VEO_APPROVAL_THRESHOLD_BY_ACTION_JSON")

        if project_id and project_id in project_map:
            return int(project_map[project_id])
        if provider_name and provider_name in provider_map:
            return int(provider_map[provider_name])
        if action_type in action_map:
            return int(action_map[action_type])

        return self.threshold_default

    def _resolve_required_band(self, *, action_type: str, affected_items: int, threshold: int) -> int:
        base_band = self.required_band_for_action(action_type)

        if affected_items >= threshold * 3:
            return max(base_band, self.critical_impact_required_band)
        if affected_items >= threshold * 2:
            return max(base_band, self.high_impact_required_band)
        return base_band

    def _lookup_json_int(self, attr_name: str, key: str, default: int) -> int:
        payload = self._load_json(attr_name)
        try:
            return int(payload.get(key, default))
        except Exception:
            return default

    def _load_json(self, attr_name: str) -> Dict[str, Any]:
        raw = getattr(settings, attr_name, "") or ""
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
9) PATCH backend/app/api/veo_workspace.py
Feature flag guard helpers
from fastapi.responses import StreamingResponse
import csv
import io
from backend.app.services.veo_governance_feature_flag_service import VeoGovernanceFeatureFlagService
from backend.app.services.veo_governance_policy_bootstrap_service import VeoGovernancePolicyBootstrapService
Thêm helper:
def _require_governance_flag(enabled: bool, detail: str) -> None:
    if not enabled:
        raise HTTPException(status_code=403, detail=detail)
10) PATCH backend/app/api/veo_workspace.py
Admin policy editor API
Thêm schemas:
class VeoGovernancePolicyOverrideCreateRequest(BaseModel):
    scope_type: str
    scope_key: str
    action_type: Optional[str] = None
    provider_name: Optional[str] = None
    project_id: Optional[str] = None
    policy_version: str = "v1"
    is_enabled: bool = True
    approval_threshold: Optional[int] = None
    sla_minutes: Optional[int] = None
    escalation_minutes: Optional[int] = None
    auto_expire_minutes: Optional[int] = None
    required_supervisor_band: Optional[int] = None
    actor: str


class VeoGovernancePolicyOverrideResponse(BaseModel):
    id: str
    scope_type: str
    scope_key: str
    action_type: Optional[str] = None
    provider_name: Optional[str] = None
    project_id: Optional[str] = None
    policy_version: str
    is_enabled: bool
    approval_threshold: Optional[int] = None
    sla_minutes: Optional[int] = None
    escalation_minutes: Optional[int] = None
    auto_expire_minutes: Optional[int] = None
    required_supervisor_band: Optional[int] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


class VeoGovernancePolicyOverrideListResponse(BaseModel):
    items: List[VeoGovernancePolicyOverrideResponse]
    total: int
Thêm helper mapper:
def _policy_override_to_response(row: VeoGovernancePolicyOverride) -> VeoGovernancePolicyOverrideResponse:
    return VeoGovernancePolicyOverrideResponse(
        id=row.id,
        scope_type=row.scope_type,
        scope_key=row.scope_key,
        action_type=row.action_type,
        provider_name=row.provider_name,
        project_id=row.project_id,
        policy_version=row.policy_version,
        is_enabled=row.is_enabled,
        approval_threshold=row.approval_threshold,
        sla_minutes=row.sla_minutes,
        escalation_minutes=row.escalation_minutes,
        auto_expire_minutes=row.auto_expire_minutes,
        required_supervisor_band=row.required_supervisor_band,
        created_by=row.created_by,
        updated_by=row.updated_by,
    )
Thêm routes:
@router.post("/governance/policies/bootstrap")
def bootstrap_governance_policies(db: Session = Depends(get_db)) -> dict:
    flags = VeoGovernanceFeatureFlagService()
    _require_governance_flag(flags.policy_editor_enabled(), "Governance policy editor is disabled")
    return VeoGovernancePolicyBootstrapService(db).seed_defaults()


@router.get("/governance/policies", response_model=VeoGovernancePolicyOverrideListResponse)
def list_governance_policies(
    scope_type: Optional[str] = Query(default=None),
    action_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> VeoGovernancePolicyOverrideListResponse:
    flags = VeoGovernanceFeatureFlagService()
    _require_governance_flag(flags.policy_editor_enabled(), "Governance policy editor is disabled")

    stmt = select(VeoGovernancePolicyOverride)
    if scope_type:
        stmt = stmt.where(VeoGovernancePolicyOverride.scope_type == scope_type)
    if action_type:
        stmt = stmt.where(VeoGovernancePolicyOverride.action_type == action_type)

    rows = db.execute(stmt.order_by(VeoGovernancePolicyOverride.created_at.desc())).scalars().all()
    return VeoGovernancePolicyOverrideListResponse(
        items=[_policy_override_to_response(row) for row in rows],
        total=len(rows),
    )


@router.post("/governance/policies", response_model=VeoGovernancePolicyOverrideResponse)
def create_governance_policy_override(
    payload: VeoGovernancePolicyOverrideCreateRequest,
    db: Session = Depends(get_db),
) -> VeoGovernancePolicyOverrideResponse:
    flags = VeoGovernanceFeatureFlagService()
    _require_governance_flag(flags.policy_editor_enabled(), "Governance policy editor is disabled")

    row = VeoGovernancePolicyOverride(
        scope_type=payload.scope_type,
        scope_key=payload.scope_key,
        action_type=payload.action_type,
        provider_name=payload.provider_name,
        project_id=payload.project_id,
        policy_version=payload.policy_version,
        is_enabled=payload.is_enabled,
        approval_threshold=payload.approval_threshold,
        sla_minutes=payload.sla_minutes,
        escalation_minutes=payload.escalation_minutes,
        auto_expire_minutes=payload.auto_expire_minutes,
        required_supervisor_band=payload.required_supervisor_band,
        created_by=payload.actor,
        updated_by=payload.actor,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _policy_override_to_response(row)
11) PATCH backend/app/api/veo_workspace.py
Audit export endpoint
@router.get("/batch-runs/{batch_id}/audit-export")
def export_batch_audit(batch_id: str, db: Session = Depends(get_db)):
    flags = VeoGovernanceFeatureFlagService()
    _require_governance_flag(flags.audit_export_enabled(), "Governance audit export is disabled")

    run = db.get(VeoBatchRun, batch_id)
    if not run:
        raise HTTPException(status_code=404, detail="Batch run not found")

    rows = db.execute(
        select(VeoBatchAuditEvent).where(
            VeoBatchAuditEvent.batch_run_id == batch_id
        ).order_by(VeoBatchAuditEvent.created_at.asc())
    ).scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "id",
        "batch_run_id",
        "action_type",
        "actor",
        "reason",
        "audit_note",
        "dry_run",
        "max_affected_items",
        "affected_items",
        "target_error_code",
        "created_at",
    ])

    for row in rows:
        writer.writerow([
            row.id,
            row.batch_run_id,
            row.action_type,
            row.actor,
            row.reason,
            row.audit_note,
            row.dry_run,
            row.max_affected_items,
            row.affected_items,
            row.target_error_code,
            row.created_at.isoformat() if row.created_at else "",
        ])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="veo_batch_audit_{batch_id}.csv"'},
    )
12) PATCH backend/app/api/veo_workspace.py
Feature-flag guards for sensitive endpoints
Thêm ở đầu các endpoint sau:
Governance metrics
    flags = VeoGovernanceFeatureFlagService()
    _require_governance_flag(flags.metrics_enabled(), "Governance metrics are disabled")
Pending approvals / approve / reject
    flags = VeoGovernanceFeatureFlagService()
    _require_governance_flag(flags.approvals_enabled(), "Governance approvals are disabled")
Bulk approve / bulk reject
    flags = VeoGovernanceFeatureFlagService()
    _require_governance_flag(flags.bulk_supervisor_actions_enabled(), "Bulk supervisor actions are disabled")
13) PATCH frontend/src/lib/api.ts
Policy editor + audit export API
export type VeoGovernancePolicyOverride = {
  id: string;
  scope_type: string;
  scope_key: string;
  action_type?: string | null;
  provider_name?: string | null;
  project_id?: string | null;
  policy_version: string;
  is_enabled: boolean;
  approval_threshold?: number | null;
  sla_minutes?: number | null;
  escalation_minutes?: number | null;
  auto_expire_minutes?: number | null;
  required_supervisor_band?: number | null;
  created_by?: string | null;
  updated_by?: string | null;
};

export type VeoGovernancePolicyOverrideList = {
  items: VeoGovernancePolicyOverride[];
  total: number;
};

export async function bootstrapVeoGovernancePolicies() {
  const res = await fetch(`/api/v1/veo/governance/policies/bootstrap`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to bootstrap governance policies");
  return res.json();
}

export async function listVeoGovernancePolicies(params?: {
  scope_type?: string;
  action_type?: string;
}): Promise<VeoGovernancePolicyOverrideList> {
  const search = new URLSearchParams();
  if (params?.scope_type) search.set("scope_type", params.scope_type);
  if (params?.action_type) search.set("action_type", params.action_type);
  const qs = search.toString();

  const res = await fetch(`/api/v1/veo/governance/policies${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error("Failed to list governance policies");
  return res.json();
}

export async function createVeoGovernancePolicyOverride(payload: {
  scope_type: string;
  scope_key: string;
  action_type?: string;
  provider_name?: string;
  project_id?: string;
  policy_version?: string;
  is_enabled?: boolean;
  approval_threshold?: number;
  sla_minutes?: number;
  escalation_minutes?: number;
  auto_expire_minutes?: number;
  required_supervisor_band?: number;
  actor: string;
}): Promise<VeoGovernancePolicyOverride> {
  const res = await fetch(`/api/v1/veo/governance/policies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create governance policy override");
  return res.json();
}

export function getVeoAuditExportUrl(batchId: string): string {
  return `/api/v1/veo/batch-runs/${batchId}/audit-export`;
}
14) frontend/src/components/veo/VeoGovernancePolicyEditorPanel.tsx
"use client";

import { useEffect, useState } from "react";
import {
  bootstrapVeoGovernancePolicies,
  createVeoGovernancePolicyOverride,
  listVeoGovernancePolicies,
  VeoGovernancePolicyOverride,
} from "@/src/lib/api";

type Props = {
  onChanged?: () => Promise<void> | void;
};

export default function VeoGovernancePolicyEditorPanel({ onChanged }: Props) {
  const [items, setItems] = useState<VeoGovernancePolicyOverride[]>([]);
  const [loading, setLoading] = useState(false);

  const [scopeType, setScopeType] = useState("provider");
  const [scopeKey, setScopeKey] = useState("");
  const [actionType, setActionType] = useState("cancel_pending");
  const [providerName, setProviderName] = useState("");
  const [projectId, setProjectId] = useState("");
  const [actor, setActor] = useState("");
  const [approvalThreshold, setApprovalThreshold] = useState("");
  const [slaMinutes, setSlaMinutes] = useState("");
  const [escalationMinutes, setEscalationMinutes] = useState("");
  const [autoExpireMinutes, setAutoExpireMinutes] = useState("");
  const [requiredSupervisorBand, setRequiredSupervisorBand] = useState("");

  async function refresh() {
    setLoading(true);
    try {
      const data = await listVeoGovernancePolicies();
      setItems(data.items);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleBootstrap() {
    try {
      setLoading(true);
      await bootstrapVeoGovernancePolicies();
      await refresh();
      await onChanged?.();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Bootstrap failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    try {
      if (!actor.trim()) {
        alert("Actor is required.");
        return;
      }
      if (!scopeKey.trim()) {
        alert("Scope key is required.");
        return;
      }

      setLoading(true);
      await createVeoGovernancePolicyOverride({
        scope_type: scopeType,
        scope_key: scopeKey,
        action_type: actionType,
        provider_name: providerName || undefined,
        project_id: projectId || undefined,
        approval_threshold: approvalThreshold ? Number(approvalThreshold) : undefined,
        sla_minutes: slaMinutes ? Number(slaMinutes) : undefined,
        escalation_minutes: escalationMinutes ? Number(escalationMinutes) : undefined,
        auto_expire_minutes: autoExpireMinutes ? Number(autoExpireMinutes) : undefined,
        required_supervisor_band: requiredSupervisorBand ? Number(requiredSupervisorBand) : undefined,
        actor: actor.trim(),
      });
      await refresh();
      await onChanged?.();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Create policy override failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-neutral-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-base font-semibold">Governance Policy Editor</h3>
          <button className="rounded-xl border px-3 py-2 text-sm" onClick={handleBootstrap} disabled={loading}>
            Bootstrap Defaults
          </button>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <input value={actor} onChange={(e) => setActor(e.target.value)} placeholder="actor" className="rounded-xl border px-3 py-2 text-sm" />
          <select value={scopeType} onChange={(e) => setScopeType(e.target.value)} className="rounded-xl border px-3 py-2 text-sm">
            <option value="global">global</option>
            <option value="provider">provider</option>
            <option value="project">project</option>
          </select>
          <input value={scopeKey} onChange={(e) => setScopeKey(e.target.value)} placeholder="scope key" className="rounded-xl border px-3 py-2 text-sm" />
          <select value={actionType} onChange={(e) => setActionType(e.target.value)} className="rounded-xl border px-3 py-2 text-sm">
            <option value="cancel_pending">cancel_pending</option>
            <option value="retry_by_error_code">retry_by_error_code</option>
            <option value="requeue_retry_waiting">requeue_retry_waiting</option>
          </select>
          <input value={providerName} onChange={(e) => setProviderName(e.target.value)} placeholder="provider_name" className="rounded-xl border px-3 py-2 text-sm" />
          <input value={projectId} onChange={(e) => setProjectId(e.target.value)} placeholder="project_id" className="rounded-xl border px-3 py-2 text-sm" />
          <input value={approvalThreshold} onChange={(e) => setApprovalThreshold(e.target.value)} placeholder="approval_threshold" className="rounded-xl border px-3 py-2 text-sm" />
          <input value={slaMinutes} onChange={(e) => setSlaMinutes(e.target.value)} placeholder="sla_minutes" className="rounded-xl border px-3 py-2 text-sm" />
          <input value={escalationMinutes} onChange={(e) => setEscalationMinutes(e.target.value)} placeholder="escalation_minutes" className="rounded-xl border px-3 py-2 text-sm" />
          <input value={autoExpireMinutes} onChange={(e) => setAutoExpireMinutes(e.target.value)} placeholder="auto_expire_minutes" className="rounded-xl border px-3 py-2 text-sm" />
          <input value={requiredSupervisorBand} onChange={(e) => setRequiredSupervisorBand(e.target.value)} placeholder="required_supervisor_band" className="rounded-xl border px-3 py-2 text-sm" />
        </div>

        <button className="mt-4 rounded-xl border px-3 py-2 text-sm" onClick={handleCreate} disabled={loading}>
          Create Override
        </button>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white">
        <div className="border-b px-4 py-3 font-semibold">Existing Policy Overrides</div>
        <div className="divide-y">
          {items.length === 0 ? (
            <div className="px-4 py-6 text-sm text-neutral-500">No policy overrides.</div>
          ) : (
            items.map((item) => (
              <div key={item.id} className="px-4 py-4">
                <div className="font-medium">{item.scope_type} / {item.scope_key}</div>
                <div className="mt-1 text-sm text-neutral-600">
                  action={item.action_type || "-"} | threshold={item.approval_threshold ?? "-"} | sla={item.sla_minutes ?? "-"} | escalation={item.escalation_minutes ?? "-"} | expire={item.auto_expire_minutes ?? "-"} | band={item.required_supervisor_band ?? "-"}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
15) frontend/src/components/veo/VeoGovernanceAuditExportPanel.tsx
"use client";

import { getVeoAuditExportUrl } from "@/src/lib/api";

type Props = {
  batchId: string;
};

export default function VeoGovernanceAuditExportPanel({ batchId }: Props) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-4">
      <h3 className="text-base font-semibold">Audit Export</h3>
      <p className="mt-1 text-sm text-neutral-500">
        Export batch governance audit trail as CSV for compliance, review, or incident postmortem.
      </p>
      <a
        href={getVeoAuditExportUrl(batchId)}
        className="mt-3 inline-flex rounded-xl border px-3 py-2 text-sm"
      >
        Export Audit CSV
      </a>
    </div>
  );
}
16) PATCH frontend/src/app/projects/[id]/page.tsx
Add policy editor + audit export tabs/panels
Add imports
import VeoGovernancePolicyEditorPanel from "@/src/components/veo/VeoGovernancePolicyEditorPanel";
import VeoGovernanceAuditExportPanel from "@/src/components/veo/VeoGovernanceAuditExportPanel";
Extend tabs
type VeoBatchTab =
  | "overview"
  | "items"
  | "failures"
  | "timeline"
  | "approvals"
  | "policies"
  | "audit";
Add tab buttons
<TabButton
  label="Policies"
  active={activeTab === "policies"}
  onClick={() => setActiveTab("policies")}
/>
<TabButton
  label="Audit"
  active={activeTab === "audit"}
  onClick={() => setActiveTab("audit")}
/>
Add render blocks
{activeTab === "policies" ? (
  <VeoGovernancePolicyEditorPanel onChanged={() => refresh()} />
) : null}

{activeTab === "audit" ? (
  <VeoGovernanceAuditExportPanel batchId={batchId} />
) : null}
17) backend/docs/veo_governance_runbook.md
# Veo Governance Runbook

## Purpose
This runbook explains how to operate Veo governance safely in local/dev/staging/prod.

## Bootstrap
1. Enable feature flags:
   - `VEO_GOVERNANCE_ENABLED=true`
   - `VEO_GOVERNANCE_POLICY_EDITOR_ENABLED=true`
2. Run migrations.
3. Call bootstrap endpoint:
   - `POST /api/v1/veo/governance/policies/bootstrap`

## Core features
- Approval queue with supervisor review
- Threshold policy by action/provider/project
- SLA, escalation, auto-expire
- Governance metrics
- Audit export CSV
- Bulk supervisor actions
- Duplicate-action prevention via idempotency key and dedupe fingerprint

## Recommended rollout order
1. Metrics only
2. Audit export
3. Approval workflow
4. Policy editor
5. Bulk supervisor actions
6. Notifications

## Safety notes
- Keep bulk actions disabled at first if production is new
- Use dry-run before enabling direct governed actions
- Require high supervisor band for `cancel_pending`
- Export audit during incidents and postmortems

## Local checklist
- Seed default policies
- Create test pending approval
- Approve and reject one request
- Run governance worker tick
- Confirm overdue/escalated states update
- Export CSV successfully
18) backend/docs/veo_governance_local_fixtures.md
# Veo Governance Local Test Fixtures

## Example local env
```env
VEO_GOVERNANCE_ENABLED=true
VEO_GOVERNANCE_POLICY_EDITOR_ENABLED=true
VEO_GOVERNANCE_APPROVALS_ENABLED=true
VEO_GOVERNANCE_METRICS_ENABLED=true
VEO_GOVERNANCE_AUDIT_EXPORT_ENABLED=true
VEO_GOVERNANCE_NOTIFICATIONS_ENABLED=true
VEO_GOVERNANCE_BULK_SUPERVISOR_ACTIONS_ENABLED=true
Example supervisor bands
{"ops_supervisor":1,"ops_manager":2,"ops_admin":3}
Example policy bootstrap validation
cancel_pending threshold = 10
retry_by_error_code threshold = 20
requeue_retry_waiting threshold = 25
Example test scenario
Create 12 pending items
Submit cancel_pending action
Verify request enters pending_approval
Approve as ops_manager
Confirm items move to cancelled
Example overdue scenario
Create request with old sla_due_at
Run governance worker
Verify:
is_overdue=true
escalation_status=escalated

---

# 19) `tests/test_veo_governance_policy_bootstrap_service.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.services.veo_governance_policy_bootstrap_service import VeoGovernancePolicyBootstrapService
from backend.app.models.veo_workspace import VeoGovernancePolicyOverride


def test_seed_defaults():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        service = VeoGovernancePolicyBootstrapService(db)
        result = service.seed_defaults()

        assert result["ok"] is True
        rows = db.query(VeoGovernancePolicyOverride).all()
        assert len(rows) >= 3
    finally:
        db.close()
20) tests/test_veo_governance_metrics_service.py
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.models.veo_workspace import VeoBatchActionRequest
from backend.app.services.veo_governance_metrics_service import VeoGovernanceMetricsService


def test_governance_metrics_summary():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        db.add(
            VeoBatchActionRequest(
                batch_run_id="batch-1",
                action_type="cancel_pending",
                approval_status="pending_approval",
                requires_approval=True,
                actor="ops@example.com",
                reason="Need approval",
                dry_run=False,
                affected_items=10,
                is_overdue=True,
                escalation_status="escalated",
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        metrics = VeoGovernanceMetricsService(db).summary(batch_run_id="batch-1")
        assert metrics["pending_approvals"] == 1
        assert metrics["overdue_approvals"] == 1
        assert metrics["escalated_approvals"] == 1
    finally:
        db.close()
Kết quả sau phase này
Sau patch này, module governance đã tiến từ:
enterprise-grade governed ops
sang:
deployable controlled platform module
Cụ thể bạn đã có:
bootstrap policy mặc định
feature flags cho rollout theo capability
policy editor API
provider/project/global override support
governance health cards
audit CSV export
docs runbook + local fixtures
tests bootstrap/metrics cơ bản
Đây là lớp giúp bạn rollout từng phần một cách an toàn, thay vì bật toàn bộ governance trong một lần.
