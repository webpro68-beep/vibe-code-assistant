# Queue Saved Views + Workload Balancing + Telemetry Rollups Spec

PHASE 3 — QUEUE SAVED VIEWS + ASSIGNEE WORKLOAD BALANCING + TELEMETRY ROLLUPS
FILE-BY-FILE PATCH FORMAT
Mục tiêu của phase này là nâng queue từ mức “xử lý được” lên mức “vận hành được”:
có saved views theo vai trò/operator
có workload balancing để gợi ý / auto-assign hợp lý
có telemetry rollups để đo:
throughput
conflict rate
approval latency
execution success rate
Tôi giữ format theo kiểu paste-into-repo thật, không tái cấu trúc vô cớ.
0) PHẠM VI BẢN PATCH NÀY
Backend thêm
queue_saved_view model
queue_telemetry_rollup model
queue_assignment_service
queue_saved_view_service
queue_telemetry_service
queue metrics repository / rollup repo
queue API routes:
saved views CRUD
workload summary
recommendation / rebalance preview
telemetry summary
tests
Frontend thêm
saved views types + api
SavedViewsBar
WorkloadPanel
QueueTelemetryCards
RebalancePreviewModal
update UnifiedOperatorQueue / Pending queue screen
tests
1) BACKEND — MODELS
FILE: backend/app/models/queue_saved_view.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueSavedView(Base):
    __tablename__ = "queue_saved_view"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(50), nullable=False, default="private", index=True)
    # private | team | global

    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    columns: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sort: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
FILE: backend/app/models/queue_telemetry_rollup.py
from __future__ import annotations

import uuid
from datetime import datetime, date

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueTelemetryRollup(Base):
    __tablename__ = "queue_telemetry_rollup"
    __table_args__ = (
        UniqueConstraint("rollup_date", "queue_key", "dimension_type", "dimension_value", name="uq_queue_rollup_dim"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rollup_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    dimension_type: Mapped[str] = mapped_column(String(50), nullable=False, default="global", index=True)
    # global | assignee | provider | severity | project

    dimension_value: Mapped[str] = mapped_column(String(255), nullable=False, default="all", index=True)

    items_opened: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_closed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_acked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approvals_requested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approvals_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    executions_attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    executions_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflicts_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    avg_time_to_first_action_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_approval_latency_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_execution_latency_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
2) BACKEND — REPOSITORIES
FILE: backend/app/repositories/queue_saved_view_repository.py
from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.queue_saved_view import QueueSavedView


class QueueSavedViewRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: dict) -> QueueSavedView:
        obj = QueueSavedView(**data)
        self.session.add(obj)
        self.session.flush()
        self.session.refresh(obj)
        return obj

    def get(self, saved_view_id: str) -> QueueSavedView | None:
        return self.session.get(QueueSavedView, saved_view_id)

    def list_visible(self, owner_id: str, queue_key: str | None = None) -> list[QueueSavedView]:
        stmt = select(QueueSavedView).where(
            or_(
                QueueSavedView.owner_id == owner_id,
                QueueSavedView.scope.in_(["team", "global"]),
            )
        )
        if queue_key:
            stmt = stmt.where(QueueSavedView.queue_key == queue_key)

        stmt = stmt.order_by(
            QueueSavedView.is_pinned.desc(),
            QueueSavedView.is_default.desc(),
            QueueSavedView.updated_at.desc(),
        )
        return list(self.session.execute(stmt).scalars().all())

    def update(self, obj: QueueSavedView, patch: dict) -> QueueSavedView:
        for key, value in patch.items():
            setattr(obj, key, value)
        self.session.add(obj)
        self.session.flush()
        self.session.refresh(obj)
        return obj

    def delete(self, obj: QueueSavedView) -> None:
        self.session.delete(obj)
        self.session.flush()

    def clear_default_for_owner(self, owner_id: str, queue_key: str) -> None:
        stmt = select(QueueSavedView).where(
            and_(
                QueueSavedView.owner_id == owner_id,
                QueueSavedView.queue_key == queue_key,
                QueueSavedView.is_default.is_(True),
            )
        )
        items = self.session.execute(stmt).scalars().all()
        for item in items:
            item.is_default = False
            self.session.add(item)
        self.session.flush()
FILE: backend/app/repositories/queue_telemetry_rollup_repository.py
from __future__ import annotations

from datetime import date
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.queue_telemetry_rollup import QueueTelemetryRollup


class QueueTelemetryRollupRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(
        self,
        *,
        rollup_date: date,
        queue_key: str,
        dimension_type: str,
        dimension_value: str,
        patch: dict,
    ) -> QueueTelemetryRollup:
        stmt = select(QueueTelemetryRollup).where(
            and_(
                QueueTelemetryRollup.rollup_date == rollup_date,
                QueueTelemetryRollup.queue_key == queue_key,
                QueueTelemetryRollup.dimension_type == dimension_type,
                QueueTelemetryRollup.dimension_value == dimension_value,
            )
        )
        obj = self.session.execute(stmt).scalar_one_or_none()
        if not obj:
            obj = QueueTelemetryRollup(
                rollup_date=rollup_date,
                queue_key=queue_key,
                dimension_type=dimension_type,
                dimension_value=dimension_value,
                **patch,
            )
            self.session.add(obj)
        else:
            for key, value in patch.items():
                setattr(obj, key, value)

        self.session.flush()
        self.session.refresh(obj)
        return obj

    def list_range(
        self,
        *,
        queue_key: str,
        start_date: date,
        end_date: date,
        dimension_type: str = "global",
    ) -> list[QueueTelemetryRollup]:
        stmt = (
            select(QueueTelemetryRollup)
            .where(
                and_(
                    QueueTelemetryRollup.queue_key == queue_key,
                    QueueTelemetryRollup.rollup_date >= start_date,
                    QueueTelemetryRollup.rollup_date <= end_date,
                    QueueTelemetryRollup.dimension_type == dimension_type,
                )
            )
            .order_by(QueueTelemetryRollup.rollup_date.asc())
        )
        return list(self.session.execute(stmt).scalars().all())
3) BACKEND — SCHEMAS
FILE: backend/app/schemas/queue_saved_view.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class QueueSavedViewBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    scope: str = "private"
    queue_key: str
    filters: dict = Field(default_factory=dict)
    columns: list | None = None
    sort: dict | None = None
    is_default: bool = False
    is_pinned: bool = False


class QueueSavedViewCreate(QueueSavedViewBase):
    pass


class QueueSavedViewUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scope: str | None = None
    filters: dict | None = None
    columns: list | None = None
    sort: dict | None = None
    is_default: bool | None = None
    is_pinned: bool | None = None


class QueueSavedViewRead(QueueSavedViewBase):
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
FILE: backend/app/schemas/queue_workload.py
from __future__ import annotations

from pydantic import BaseModel


class AssigneeWorkloadSummary(BaseModel):
    assignee_id: str
    open_count: int
    pending_approval_count: int
    high_priority_count: int
    overdue_count: int
    recent_conflict_count: int
    capacity_score: float
    load_score: float
    recommended: bool = False


class QueueRebalanceCandidate(BaseModel):
    item_id: str
    current_assignee_id: str | None
    suggested_assignee_id: str | None
    reason: str
    score_delta: float


class QueueRebalancePreview(BaseModel):
    queue_key: str
    candidates: list[QueueRebalanceCandidate]
    summaries: list[AssigneeWorkloadSummary]
FILE: backend/app/schemas/queue_telemetry.py
from __future__ import annotations

from datetime import date
from pydantic import BaseModel


class QueueTelemetryPoint(BaseModel):
    rollup_date: date
    items_opened: int
    items_closed: int
    items_acked: int
    approvals_requested: int
    approvals_completed: int
    executions_attempted: int
    executions_succeeded: int
    conflicts_detected: int
    avg_time_to_first_action_sec: float
    avg_approval_latency_sec: float
    avg_execution_latency_sec: float


class QueueTelemetrySummary(BaseModel):
    queue_key: str
    dimension_type: str
    points: list[QueueTelemetryPoint]
    totals: dict
4) BACKEND — SERVICES
FILE: backend/app/services/queue_saved_view_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.queue_saved_view_repository import QueueSavedViewRepository
from app.schemas.queue_saved_view import QueueSavedViewCreate, QueueSavedViewUpdate


class QueueSavedViewService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = QueueSavedViewRepository(session)

    def create(self, actor_id: str, payload: QueueSavedViewCreate):
        data = payload.model_dump()
        if data.get("is_default"):
            self.repo.clear_default_for_owner(actor_id, data["queue_key"])
        obj = self.repo.create({**data, "owner_id": actor_id})
        self.session.commit()
        return obj

    def list_visible(self, actor_id: str, queue_key: str | None = None):
        return self.repo.list_visible(actor_id, queue_key=queue_key)

    def update(self, actor_id: str, saved_view_id: str, payload: QueueSavedViewUpdate):
        obj = self.repo.get(saved_view_id)
        if not obj:
            raise ValueError("saved_view_not_found")
        if obj.owner_id != actor_id and obj.scope != "global":
            raise PermissionError("forbidden_saved_view_update")

        patch = payload.model_dump(exclude_unset=True)
        if patch.get("is_default") is True:
            self.repo.clear_default_for_owner(obj.owner_id, obj.queue_key)

        obj = self.repo.update(obj, patch)
        self.session.commit()
        return obj

    def delete(self, actor_id: str, saved_view_id: str):
        obj = self.repo.get(saved_view_id)
        if not obj:
            raise ValueError("saved_view_not_found")
        if obj.owner_id != actor_id and obj.scope != "global":
            raise PermissionError("forbidden_saved_view_delete")

        self.repo.delete(obj)
        self.session.commit()
FILE: backend/app/services/queue_assignment_service.py
from __future__ import annotations

from collections import defaultdict
from sqlalchemy.orm import Session

from app.schemas.queue_workload import (
    AssigneeWorkloadSummary,
    QueueRebalanceCandidate,
    QueueRebalancePreview,
)


class QueueAssignmentService:
    def __init__(self, session: Session):
        self.session = session

    def summarize_assignee_workload(self, queue_items: list[dict], assignee_ids: list[str]) -> list[AssigneeWorkloadSummary]:
        bucket = defaultdict(lambda: {
            "open_count": 0,
            "pending_approval_count": 0,
            "high_priority_count": 0,
            "overdue_count": 0,
            "recent_conflict_count": 0,
        })

        for item in queue_items:
            assignee_id = item.get("assignee_id") or "unassigned"
            bucket[assignee_id]["open_count"] += 1
            if item.get("requires_approval"):
                bucket[assignee_id]["pending_approval_count"] += 1
            if item.get("priority_score", 0) >= 80:
                bucket[assignee_id]["high_priority_count"] += 1
            if item.get("is_overdue"):
                bucket[assignee_id]["overdue_count"] += 1
            if item.get("has_recent_conflict"):
                bucket[assignee_id]["recent_conflict_count"] += 1

        summaries: list[AssigneeWorkloadSummary] = []
        candidate_ids = list(dict.fromkeys([*assignee_ids, *bucket.keys()]))

        for assignee_id in candidate_ids:
            stats = bucket[assignee_id]
            load_score = (
                stats["open_count"] * 1.0
                + stats["pending_approval_count"] * 1.5
                + stats["high_priority_count"] * 2.0
                + stats["overdue_count"] * 2.5
                + stats["recent_conflict_count"] * 1.5
            )
            capacity_score = max(0.0, 100.0 - load_score)

            summaries.append(
                AssigneeWorkloadSummary(
                    assignee_id=assignee_id,
                    open_count=stats["open_count"],
                    pending_approval_count=stats["pending_approval_count"],
                    high_priority_count=stats["high_priority_count"],
                    overdue_count=stats["overdue_count"],
                    recent_conflict_count=stats["recent_conflict_count"],
                    load_score=round(load_score, 2),
                    capacity_score=round(capacity_score, 2),
                )
            )

        summaries.sort(key=lambda x: (x.load_score, -x.capacity_score, x.assignee_id))
        if summaries:
            summaries[0].recommended = True
        return summaries

    def build_rebalance_preview(
        self,
        *,
        queue_key: str,
        queue_items: list[dict],
        assignee_ids: list[str],
        max_candidates: int = 20,
    ) -> QueueRebalancePreview:
        summaries = self.summarize_assignee_workload(queue_items, assignee_ids)
        if not summaries:
            return QueueRebalancePreview(queue_key=queue_key, candidates=[], summaries=[])

        least_loaded = summaries[0].assignee_id
        candidates: list[QueueRebalanceCandidate] = []

        for item in queue_items:
            current = item.get("assignee_id")
            if current == least_loaded:
                continue
            if item.get("locked_for_execution"):
                continue
            if item.get("status") in {"closed", "executed"}:
                continue

            score_delta = float(item.get("priority_score", 0)) / 100.0
            reason = "rebalance_to_lower_load_assignee"
            candidates.append(
                QueueRebalanceCandidate(
                    item_id=item["id"],
                    current_assignee_id=current,
                    suggested_assignee_id=least_loaded,
                    reason=reason,
                    score_delta=round(score_delta, 2),
                )
            )
            if len(candidates) >= max_candidates:
                break

        return QueueRebalancePreview(
            queue_key=queue_key,
            candidates=candidates,
            summaries=summaries,
        )
FILE: backend/app/services/queue_telemetry_service.py
from __future__ import annotations

from datetime import date
from sqlalchemy.orm import Session

from app.repositories.queue_telemetry_rollup_repository import QueueTelemetryRollupRepository
from app.schemas.queue_telemetry import QueueTelemetryPoint, QueueTelemetrySummary


class QueueTelemetryService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = QueueTelemetryRollupRepository(session)

    def get_summary(
        self,
        *,
        queue_key: str,
        start_date: date,
        end_date: date,
        dimension_type: str = "global",
    ) -> QueueTelemetrySummary:
        rows = self.repo.list_range(
            queue_key=queue_key,
            start_date=start_date,
            end_date=end_date,
            dimension_type=dimension_type,
        )

        points = [
            QueueTelemetryPoint(
                rollup_date=row.rollup_date,
                items_opened=row.items_opened,
                items_closed=row.items_closed,
                items_acked=row.items_acked,
                approvals_requested=row.approvals_requested,
                approvals_completed=row.approvals_completed,
                executions_attempted=row.executions_attempted,
                executions_succeeded=row.executions_succeeded,
                conflicts_detected=row.conflicts_detected,
                avg_time_to_first_action_sec=row.avg_time_to_first_action_sec,
                avg_approval_latency_sec=row.avg_approval_latency_sec,
                avg_execution_latency_sec=row.avg_execution_latency_sec,
            )
            for row in rows
        ]

        totals = {
            "items_opened": sum(p.items_opened for p in points),
            "items_closed": sum(p.items_closed for p in points),
            "items_acked": sum(p.items_acked for p in points),
            "approvals_requested": sum(p.approvals_requested for p in points),
            "approvals_completed": sum(p.approvals_completed for p in points),
            "executions_attempted": sum(p.executions_attempted for p in points),
            "executions_succeeded": sum(p.executions_succeeded for p in points),
            "conflicts_detected": sum(p.conflicts_detected for p in points),
        }

        return QueueTelemetrySummary(
            queue_key=queue_key,
            dimension_type=dimension_type,
            points=points,
            totals=totals,
        )
5) BACKEND — ROLLUP WORKER
FILE: backend/app/workers/queue_telemetry_rollup_worker.py
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.queue_telemetry_rollup_repository import QueueTelemetryRollupRepository


def build_queue_rollups_for_day(target_date: date) -> None:
    session: Session = SessionLocal()
    try:
        repo = QueueTelemetryRollupRepository(session)

        # TODO:
        # Replace these placeholders by real aggregations from:
        # - operator queue items / incident states
        # - governance_change_request
        # - governance_approval
        # - governance_execution_attempt
        # - audit/action logs
        #
        # Current patch keeps the worker contract stable so repo thật chỉ cần
        # map phần aggregate query vào đây.

        queue_keys = ["governance_pending", "operator_queue"]

        for queue_key in queue_keys:
            repo.upsert(
                rollup_date=target_date,
                queue_key=queue_key,
                dimension_type="global",
                dimension_value="all",
                patch={
                    "items_opened": 0,
                    "items_closed": 0,
                    "items_acked": 0,
                    "approvals_requested": 0,
                    "approvals_completed": 0,
                    "executions_attempted": 0,
                    "executions_succeeded": 0,
                    "conflicts_detected": 0,
                    "avg_time_to_first_action_sec": 0.0,
                    "avg_approval_latency_sec": 0.0,
                    "avg_execution_latency_sec": 0.0,
                },
            )

        session.commit()
    finally:
        session.close()


def build_recent_queue_rollups(days: int = 7) -> None:
    today = date.today()
    for offset in range(days):
        build_queue_rollups_for_day(today - timedelta(days=offset))
6) BACKEND — ROUTES
FILE: backend/app/api/routes/queue_saved_views.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_actor_id
from app.schemas.queue_saved_view import (
    QueueSavedViewCreate,
    QueueSavedViewRead,
    QueueSavedViewUpdate,
)
from app.services.queue_saved_view_service import QueueSavedViewService

router = APIRouter(prefix="/queue/saved-views", tags=["queue-saved-views"])


@router.get("", response_model=list[QueueSavedViewRead])
def list_saved_views(
    queue_key: str | None = Query(default=None),
    session: Session = Depends(get_db),
    actor_id: str = Depends(get_current_actor_id),
):
    service = QueueSavedViewService(session)
    return service.list_visible(actor_id, queue_key=queue_key)


@router.post("", response_model=QueueSavedViewRead)
def create_saved_view(
    payload: QueueSavedViewCreate,
    session: Session = Depends(get_db),
    actor_id: str = Depends(get_current_actor_id),
):
    service = QueueSavedViewService(session)
    try:
        return service.create(actor_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{saved_view_id}", response_model=QueueSavedViewRead)
def update_saved_view(
    saved_view_id: str,
    payload: QueueSavedViewUpdate,
    session: Session = Depends(get_db),
    actor_id: str = Depends(get_current_actor_id),
):
    service = QueueSavedViewService(session)
    try:
        return service.update(actor_id, saved_view_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.delete("/{saved_view_id}")
def delete_saved_view(
    saved_view_id: str,
    session: Session = Depends(get_db),
    actor_id: str = Depends(get_current_actor_id),
):
    service = QueueSavedViewService(session)
    try:
        service.delete(actor_id, saved_view_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
FILE: backend/app/api/routes/queue_workload.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.queue_assignment_service import QueueAssignmentService

router = APIRouter(prefix="/queue/workload", tags=["queue-workload"])


@router.post("/summary")
def get_workload_summary(
    payload: dict,
    session: Session = Depends(get_db),
):
    queue_items = payload.get("queue_items", [])
    assignee_ids = payload.get("assignee_ids", [])
    service = QueueAssignmentService(session)
    return service.summarize_assignee_workload(queue_items, assignee_ids)


@router.post("/rebalance-preview")
def get_rebalance_preview(
    payload: dict,
    session: Session = Depends(get_db),
):
    service = QueueAssignmentService(session)
    return service.build_rebalance_preview(
        queue_key=payload["queue_key"],
        queue_items=payload.get("queue_items", []),
        assignee_ids=payload.get("assignee_ids", []),
        max_candidates=payload.get("max_candidates", 20),
    )
FILE: backend/app/api/routes/queue_telemetry.py
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.queue_telemetry_service import QueueTelemetryService

router = APIRouter(prefix="/queue/telemetry", tags=["queue-telemetry"])


@router.get("/summary")
def get_queue_telemetry_summary(
    queue_key: str = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    dimension_type: str = Query(default="global"),
    session: Session = Depends(get_db),
):
    service = QueueTelemetryService(session)
    return service.get_summary(
        queue_key=queue_key,
        start_date=start_date,
        end_date=end_date,
        dimension_type=dimension_type,
    )
FILE: backend/app/api/router.py
PATCH
from app.api.routes import queue_saved_views, queue_workload, queue_telemetry
api_router.include_router(queue_saved_views.router)
api_router.include_router(queue_workload.router)
api_router.include_router(queue_telemetry.router)
7) BACKEND — ALEMBIC MIGRATION
FILE: backend/alembic/versions/phase3_queue_saved_views_and_telemetry_rollups.py
"""phase3 queue saved views and telemetry rollups

Revision ID: phase3_queue_saved_views
Revises: <PUT_PREVIOUS_REVISION_HERE>
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "phase3_queue_saved_views"
down_revision = "<PUT_PREVIOUS_REVISION_HERE>"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "queue_saved_view",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sort", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queue_saved_view_owner_id", "queue_saved_view", ["owner_id"])
    op.create_index("ix_queue_saved_view_scope", "queue_saved_view", ["scope"])
    op.create_index("ix_queue_saved_view_queue_key", "queue_saved_view", ["queue_key"])

    op.create_table(
        "queue_telemetry_rollup",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rollup_date", sa.Date(), nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("dimension_type", sa.String(length=50), nullable=False),
        sa.Column("dimension_value", sa.String(length=255), nullable=False),
        sa.Column("items_opened", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_closed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_acked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approvals_requested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approvals_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executions_attempted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executions_succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflicts_detected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_time_to_first_action_sec", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_approval_latency_sec", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_execution_latency_sec", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rollup_date", "queue_key", "dimension_type", "dimension_value", name="uq_queue_rollup_dim"),
    )
    op.create_index("ix_queue_telemetry_rollup_rollup_date", "queue_telemetry_rollup", ["rollup_date"])
    op.create_index("ix_queue_telemetry_rollup_queue_key", "queue_telemetry_rollup", ["queue_key"])
    op.create_index("ix_queue_telemetry_rollup_dimension_type", "queue_telemetry_rollup", ["dimension_type"])
    op.create_index("ix_queue_telemetry_rollup_dimension_value", "queue_telemetry_rollup", ["dimension_value"])


def downgrade():
    op.drop_index("ix_queue_telemetry_rollup_dimension_value", table_name="queue_telemetry_rollup")
    op.drop_index("ix_queue_telemetry_rollup_dimension_type", table_name="queue_telemetry_rollup")
    op.drop_index("ix_queue_telemetry_rollup_queue_key", table_name="queue_telemetry_rollup")
    op.drop_index("ix_queue_telemetry_rollup_rollup_date", table_name="queue_telemetry_rollup")
    op.drop_table("queue_telemetry_rollup")

    op.drop_index("ix_queue_saved_view_queue_key", table_name="queue_saved_view")
    op.drop_index("ix_queue_saved_view_scope", table_name="queue_saved_view")
    op.drop_index("ix_queue_saved_view_owner_id", table_name="queue_saved_view")
    op.drop_table("queue_saved_view")
Nếu repo test SQLite in-memory, JSONB có thể cần map sang JSON trong test-only migration branch hoặc base model compat layer.
8) BACKEND — TESTS
FILE: backend/tests/services/test_queue_saved_view_service.py
def test_create_default_saved_view_clears_previous_default(session):
    from app.services.queue_saved_view_service import QueueSavedViewService
    from app.schemas.queue_saved_view import QueueSavedViewCreate

    service = QueueSavedViewService(session)

    first = service.create(
        "user-1",
        QueueSavedViewCreate(
            name="My View A",
            queue_key="operator_queue",
            filters={"status": ["open"]},
            is_default=True,
        ),
    )
    second = service.create(
        "user-1",
        QueueSavedViewCreate(
            name="My View B",
            queue_key="operator_queue",
            filters={"status": ["pending"]},
            is_default=True,
        ),
    )

    assert first.id != second.id

    items = service.list_visible("user-1", queue_key="operator_queue")
    first_ref = next(x for x in items if x.id == first.id)
    second_ref = next(x for x in items if x.id == second.id)

    assert first_ref.is_default is False
    assert second_ref.is_default is True
FILE: backend/tests/services/test_queue_assignment_service.py
def test_summarize_assignee_workload_marks_lowest_load_as_recommended(session):
    from app.services.queue_assignment_service import QueueAssignmentService

    service = QueueAssignmentService(session)

    queue_items = [
        {
            "id": "a",
            "assignee_id": "u1",
            "priority_score": 90,
            "requires_approval": True,
            "is_overdue": True,
            "has_recent_conflict": False,
        },
        {
            "id": "b",
            "assignee_id": "u1",
            "priority_score": 50,
            "requires_approval": False,
            "is_overdue": False,
            "has_recent_conflict": False,
        },
        {
            "id": "c",
            "assignee_id": "u2",
            "priority_score": 30,
            "requires_approval": False,
            "is_overdue": False,
            "has_recent_conflict": False,
        },
    ]

    result = service.summarize_assignee_workload(queue_items, ["u1", "u2"])
    recommended = next(x for x in result if x.recommended)

    assert recommended.assignee_id == "u2"
FILE: backend/tests/services/test_queue_telemetry_service.py
from datetime import date


def test_queue_telemetry_summary_aggregates_totals(session):
    from app.repositories.queue_telemetry_rollup_repository import QueueTelemetryRollupRepository
    from app.services.queue_telemetry_service import QueueTelemetryService

    repo = QueueTelemetryRollupRepository(session)
    repo.upsert(
        rollup_date=date(2026, 4, 10),
        queue_key="operator_queue",
        dimension_type="global",
        dimension_value="all",
        patch={
            "items_opened": 5,
            "items_closed": 2,
            "items_acked": 1,
            "approvals_requested": 3,
            "approvals_completed": 2,
            "executions_attempted": 4,
            "executions_succeeded": 3,
            "conflicts_detected": 1,
            "avg_time_to_first_action_sec": 10.0,
            "avg_approval_latency_sec": 20.0,
            "avg_execution_latency_sec": 30.0,
        },
    )
    session.commit()

    service = QueueTelemetryService(session)
    summary = service.get_summary(
        queue_key="operator_queue",
        start_date=date(2026, 4, 10),
        end_date=date(2026, 4, 10),
    )

    assert summary.totals["items_opened"] == 5
    assert summary.totals["executions_succeeded"] == 3
    assert summary.totals["conflicts_detected"] == 1
FILE: backend/tests/api/test_queue_saved_views_api.py
def test_create_and_list_saved_views(client, auth_headers):
    payload = {
        "name": "My Queue View",
        "queue_key": "operator_queue",
        "filters": {"status": ["open"]},
        "is_default": True,
    }

    create_res = client.post("/api/v1/queue/saved-views", json=payload, headers=auth_headers)
    assert create_res.status_code == 200, create_res.text

    list_res = client.get("/api/v1/queue/saved-views?queue_key=operator_queue", headers=auth_headers)
    assert list_res.status_code == 200, list_res.text
    assert len(list_res.json()) >= 1
FILE: backend/tests/api/test_queue_workload_api.py
def test_rebalance_preview_returns_candidates(client, auth_headers):
    payload = {
        "queue_key": "operator_queue",
        "assignee_ids": ["u1", "u2"],
        "queue_items": [
            {"id": "1", "assignee_id": "u1", "priority_score": 90, "status": "open"},
            {"id": "2", "assignee_id": "u1", "priority_score": 75, "status": "open"},
        ],
    }

    res = client.post("/api/v1/queue/workload/rebalance-preview", json=payload, headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["queue_key"] == "operator_queue"
    assert "candidates" in body
    assert "summaries" in body
9) FRONTEND — TYPES
FILE: frontend/src/types/queueSavedView.ts
export type QueueSavedView = {
  id: string;
  name: string;
  description?: string | null;
  owner_id: string;
  scope: "private" | "team" | "global";
  queue_key: string;
  filters: Record<string, unknown>;
  columns?: unknown[] | null;
  sort?: Record<string, unknown> | null;
  is_default: boolean;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
};

export type QueueSavedViewCreateInput = {
  name: string;
  description?: string;
  scope?: "private" | "team" | "global";
  queue_key: string;
  filters: Record<string, unknown>;
  columns?: unknown[];
  sort?: Record<string, unknown>;
  is_default?: boolean;
  is_pinned?: boolean;
};
FILE: frontend/src/types/queueWorkload.ts
export type AssigneeWorkloadSummary = {
  assignee_id: string;
  open_count: number;
  pending_approval_count: number;
  high_priority_count: number;
  overdue_count: number;
  recent_conflict_count: number;
  capacity_score: number;
  load_score: number;
  recommended: boolean;
};

export type QueueRebalanceCandidate = {
  item_id: string;
  current_assignee_id?: string | null;
  suggested_assignee_id?: string | null;
  reason: string;
  score_delta: number;
};

export type QueueRebalancePreview = {
  queue_key: string;
  candidates: QueueRebalanceCandidate[];
  summaries: AssigneeWorkloadSummary[];
};
FILE: frontend/src/types/queueTelemetry.ts
export type QueueTelemetryPoint = {
  rollup_date: string;
  items_opened: number;
  items_closed: number;
  items_acked: number;
  approvals_requested: number;
  approvals_completed: number;
  executions_attempted: number;
  executions_succeeded: number;
  conflicts_detected: number;
  avg_time_to_first_action_sec: number;
  avg_approval_latency_sec: number;
  avg_execution_latency_sec: number;
};

export type QueueTelemetrySummary = {
  queue_key: string;
  dimension_type: string;
  points: QueueTelemetryPoint[];
  totals: Record<string, number>;
};
10) FRONTEND — API
FILE: frontend/src/api/queueSavedViewsApi.ts
import { apiClient } from "./client";
import { QueueSavedView, QueueSavedViewCreateInput } from "../types/queueSavedView";

export async function listQueueSavedViews(queueKey?: string): Promise<QueueSavedView[]> {
  const query = queueKey ? `?queue_key=${encodeURIComponent(queueKey)}` : "";
  const res = await apiClient.get(`/queue/saved-views${query}`);
  return res.data;
}

export async function createQueueSavedView(input: QueueSavedViewCreateInput): Promise<QueueSavedView> {
  const res = await apiClient.post("/queue/saved-views", input);
  return res.data;
}

export async function updateQueueSavedView(id: string, patch: Partial<QueueSavedViewCreateInput>): Promise<QueueSavedView> {
  const res = await apiClient.patch(`/queue/saved-views/${id}`, patch);
  return res.data;
}

export async function deleteQueueSavedView(id: string): Promise<{ ok: boolean }> {
  const res = await apiClient.delete(`/queue/saved-views/${id}`);
  return res.data;
}
FILE: frontend/src/api/queueWorkloadApi.ts
import { apiClient } from "./client";
import { AssigneeWorkloadSummary, QueueRebalancePreview } from "../types/queueWorkload";

export async function fetchQueueWorkloadSummary(payload: {
  queue_items: Record<string, unknown>[];
  assignee_ids: string[];
}): Promise<AssigneeWorkloadSummary[]> {
  const res = await apiClient.post("/queue/workload/summary", payload);
  return res.data;
}

export async function fetchQueueRebalancePreview(payload: {
  queue_key: string;
  queue_items: Record<string, unknown>[];
  assignee_ids: string[];
  max_candidates?: number;
}): Promise<QueueRebalancePreview> {
  const res = await apiClient.post("/queue/workload/rebalance-preview", payload);
  return res.data;
}
FILE: frontend/src/api/queueTelemetryApi.ts
import { apiClient } from "./client";
import { QueueTelemetrySummary } from "../types/queueTelemetry";

export async function fetchQueueTelemetrySummary(params: {
  queue_key: string;
  start_date: string;
  end_date: string;
  dimension_type?: string;
}): Promise<QueueTelemetrySummary> {
  const res = await apiClient.get("/queue/telemetry/summary", { params });
  return res.data;
}
11) FRONTEND — COMPONENTS
FILE: frontend/src/components/queue/SavedViewsBar.tsx
import React, { useEffect, useState } from "react";
import {
  createQueueSavedView,
  listQueueSavedViews,
} from "../../api/queueSavedViewsApi";
import { QueueSavedView } from "../../types/queueSavedView";

type Props = {
  queueKey: string;
  activeFilters: Record<string, unknown>;
  onApplyView: (view: QueueSavedView) => void;
  onToast?: (input: { title: string; description?: string; variant?: string }) => void;
};

export function SavedViewsBar({ queueKey, activeFilters, onApplyView, onToast }: Props) {
  const [views, setViews] = useState<QueueSavedView[]>([]);
  const [name, setName] = useState("");

  async function load() {
    try {
      const result = await listQueueSavedViews(queueKey);
      setViews(result);
    } catch (error) {
      onToast?.({
        title: "Không tải được saved views",
        description: String(error),
        variant: "destructive",
      });
    }
  }

  useEffect(() => {
    void load();
  }, [queueKey]);

  async function handleSaveCurrentView() {
    if (!name.trim()) return;
    try {
      await createQueueSavedView({
        name: name.trim(),
        queue_key: queueKey,
        filters: activeFilters,
      });
      setName("");
      onToast?.({ title: "Đã lưu queue view" });
      await load();
    } catch (error) {
      onToast?.({
        title: "Lưu view thất bại",
        description: String(error),
        variant: "destructive",
      });
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border p-3">
      <div className="flex items-center gap-2">
        <input
          className="h-9 flex-1 rounded-md border px-3"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Lưu bộ lọc hiện tại thành saved view"
        />
        <button className="h-9 rounded-md border px-3" onClick={handleSaveCurrentView}>
          Save view
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {views.map((view) => (
          <button
            key={view.id}
            className="rounded-full border px-3 py-1 text-sm"
            onClick={() => onApplyView(view)}
          >
            {view.name}
            {view.is_default ? " • default" : ""}
          </button>
        ))}
      </div>
    </div>
  );
}
FILE: frontend/src/components/queue/WorkloadPanel.tsx
import React from "react";
import { AssigneeWorkloadSummary } from "../../types/queueWorkload";

type Props = {
  summaries: AssigneeWorkloadSummary[];
};

export function WorkloadPanel({ summaries }: Props) {
  return (
    <div className="rounded-xl border p-4">
      <div className="mb-3 text-sm font-semibold">Assignee workload</div>
      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left">
              <th className="py-2">Assignee</th>
              <th>Open</th>
              <th>Approval</th>
              <th>High priority</th>
              <th>Overdue</th>
              <th>Conflicts</th>
              <th>Load</th>
              <th>Capacity</th>
            </tr>
          </thead>
          <tbody>
            {summaries.map((item) => (
              <tr key={item.assignee_id} className="border-t">
                <td className="py-2">
                  {item.assignee_id}
                  {item.recommended ? " • recommended" : ""}
                </td>
                <td>{item.open_count}</td>
                <td>{item.pending_approval_count}</td>
                <td>{item.high_priority_count}</td>
                <td>{item.overdue_count}</td>
                <td>{item.recent_conflict_count}</td>
                <td>{item.load_score}</td>
                <td>{item.capacity_score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
FILE: frontend/src/components/queue/QueueTelemetryCards.tsx
import React from "react";
import { QueueTelemetrySummary } from "../../types/queueTelemetry";

type Props = {
  summary?: QueueTelemetrySummary | null;
};

export function QueueTelemetryCards({ summary }: Props) {
  const totals = summary?.totals ?? {};

  const cards = [
    ["Opened", totals.items_opened ?? 0],
    ["Closed", totals.items_closed ?? 0],
    ["Acked", totals.items_acked ?? 0],
    ["Approvals", totals.approvals_completed ?? 0],
    ["Exec success", totals.executions_succeeded ?? 0],
    ["Conflicts", totals.conflicts_detected ?? 0],
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
      {cards.map(([label, value]) => (
        <div key={String(label)} className="rounded-xl border p-4">
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="mt-1 text-xl font-semibold">{value}</div>
        </div>
      ))}
    </div>
  );
}
FILE: frontend/src/components/queue/RebalancePreviewModal.tsx
import React from "react";
import { QueueRebalancePreview } from "../../types/queueWorkload";

type Props = {
  open: boolean;
  preview?: QueueRebalancePreview | null;
  onClose: () => void;
};

export function RebalancePreviewModal({ open, preview, onClose }: Props) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6">
      <div className="max-h-[80vh] w-full max-w-4xl overflow-auto rounded-xl bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <div className="text-lg font-semibold">Rebalance preview</div>
          <button className="rounded-md border px-3 py-1" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="mb-6">
          <div className="mb-2 text-sm font-medium">Candidates</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="py-2">Item</th>
                <th>Current</th>
                <th>Suggested</th>
                <th>Reason</th>
                <th>Score delta</th>
              </tr>
            </thead>
            <tbody>
              {(preview?.candidates ?? []).map((item) => (
                <tr key={item.item_id} className="border-t">
                  <td className="py-2">{item.item_id}</td>
                  <td>{item.current_assignee_id ?? "-"}</td>
                  <td>{item.suggested_assignee_id ?? "-"}</td>
                  <td>{item.reason}</td>
                  <td>{item.score_delta}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
12) FRONTEND — PANEL PATCH
FILE: frontend/src/components/governance/PendingApprovalsPanel.tsx
PATCH Ý TƯỞNG
Thêm:
SavedViewsBar
WorkloadPanel
QueueTelemetryCards
nút Preview rebalance
import React, { useEffect, useMemo, useState } from "react";
import { SavedViewsBar } from "../queue/SavedViewsBar";
import { WorkloadPanel } from "../queue/WorkloadPanel";
import { QueueTelemetryCards } from "../queue/QueueTelemetryCards";
import { RebalancePreviewModal } from "../queue/RebalancePreviewModal";
import { fetchQueueWorkloadSummary, fetchQueueRebalancePreview } from "../../api/queueWorkloadApi";
import { fetchQueueTelemetrySummary } from "../../api/queueTelemetryApi";
Thêm state
const [workload, setWorkload] = useState([]);
const [telemetry, setTelemetry] = useState(null);
const [rebalanceOpen, setRebalanceOpen] = useState(false);
const [rebalancePreview, setRebalancePreview] = useState(null);
Dữ liệu queue_items map từ bảng hiện có
const queueItemsForWorkload = useMemo(
  () =>
    pendingApprovals.map((item) => ({
      id: item.id,
      assignee_id: item.assignee_id ?? null,
      priority_score: item.priority_score ?? 0,
      requires_approval: true,
      is_overdue: Boolean(item.is_overdue),
      has_recent_conflict: Boolean(item.has_recent_conflict),
      status: item.status,
      locked_for_execution: false,
    })),
  [pendingApprovals]
);
Load workload + telemetry
useEffect(() => {
  async function loadEnhancements() {
    try {
      const [workloadRes, telemetryRes] = await Promise.all([
        fetchQueueWorkloadSummary({
          queue_items: queueItemsForWorkload,
          assignee_ids: operators.map((x) => x.id),
        }),
        fetchQueueTelemetrySummary({
          queue_key: "governance_pending",
          start_date: range.startDate,
          end_date: range.endDate,
        }),
      ]);
      setWorkload(workloadRes);
      setTelemetry(telemetryRes);
    } catch (error) {
      onToast?.({
        title: "Không tải được queue analytics",
        description: String(error),
        variant: "destructive",
      });
    }
  }

  void loadEnhancements();
}, [queueItemsForWorkload, operators, range.startDate, range.endDate]);
Apply saved view
function handleApplySavedView(view) {
  setFilters((prev) => ({
    ...prev,
    ...view.filters,
  }));
  onToast?.({ title: `Đã áp dụng view: ${view.name}` });
}
Preview rebalance
async function handlePreviewRebalance() {
  try {
    const preview = await fetchQueueRebalancePreview({
      queue_key: "governance_pending",
      queue_items: queueItemsForWorkload,
      assignee_ids: operators.map((x) => x.id),
    });
    setRebalancePreview(preview);
    setRebalanceOpen(true);
  } catch (error) {
    onToast?.({
      title: "Không preview được rebalance",
      description: String(error),
      variant: "destructive",
    });
  }
}
Render
<div className="space-y-4">
  <QueueTelemetryCards summary={telemetry} />

  <SavedViewsBar
    queueKey="governance_pending"
    activeFilters={filters}
    onApplyView={handleApplySavedView}
    onToast={onToast}
  />

  <div className="flex justify-end">
    <button className="rounded-md border px-3 py-2" onClick={handlePreviewRebalance}>
      Preview rebalance
    </button>
  </div>

  <WorkloadPanel summaries={workload} />

  {/* existing PendingApprovalsTable / filters / bulk action UI remains below */}
</div>

<RebalancePreviewModal
  open={rebalanceOpen}
  preview={rebalancePreview}
  onClose={() => setRebalanceOpen(false)}
/>
13) FRONTEND — TESTS
FILE: frontend/src/components/queue/__tests__/SavedViewsBar.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SavedViewsBar } from "../SavedViewsBar";

jest.mock("../../../api/queueSavedViewsApi", () => ({
  listQueueSavedViews: jest.fn().mockResolvedValue([]),
  createQueueSavedView: jest.fn().mockResolvedValue({
    id: "1",
    name: "My View",
    queue_key: "operator_queue",
    owner_id: "u1",
    scope: "private",
    filters: {},
    is_default: false,
    is_pinned: false,
    created_at: "",
    updated_at: "",
  }),
}));

test("creates saved view from active filters", async () => {
  const user = userEvent.setup();
  const onToast = jest.fn();

  render(
    <SavedViewsBar
      queueKey="operator_queue"
      activeFilters={{ status: ["open"] }}
      onApplyView={jest.fn()}
      onToast={onToast}
    />
  );

  await user.type(screen.getByPlaceholderText(/Lưu bộ lọc hiện tại/i), "Ops View");
  await user.click(screen.getByText(/Save view/i));

  expect(onToast).toHaveBeenCalled();
});
FILE: frontend/src/components/queue/__tests__/WorkloadPanel.test.tsx
import { render, screen } from "@testing-library/react";
import { WorkloadPanel } from "../WorkloadPanel";

test("renders workload rows", () => {
  render(
    <WorkloadPanel
      summaries={[
        {
          assignee_id: "u1",
          open_count: 5,
          pending_approval_count: 2,
          high_priority_count: 1,
          overdue_count: 0,
          recent_conflict_count: 0,
          capacity_score: 90,
          load_score: 10,
          recommended: true,
        },
      ]}
    />
  );

  expect(screen.getByText("u1 • recommended")).toBeInTheDocument();
  expect(screen.getByText("5")).toBeInTheDocument();
});
14) ĐIỂM MAP NGẮN KHI GẮN VÀO REPO THẬT
Bám đúng kiểu bạn đang làm, chỉ cần map các điểm này:
Backend
1. SessionLocal
Worker rollup đang dùng:
from app.db.session import SessionLocal
Nếu repo của bạn export chỗ khác thì đổi import, còn contract giữ nguyên:
worker mở session riêng
commit riêng từng lượt rollup
2. Queue source thật
Bản patch trên đang cho queue_items đi vào service từ route/frontend.
Khi gắn production thật, bạn nên thay bằng:
queue repository / materialized read model thật
governance pending approvals read model
operator queue read model
Tức là:
route chỉ nhận filters
service tự query DB
frontend không phải gửi cả queue_items
Nhưng để paste nhanh, bản này giữ payload-driven để ít phụ thuộc.
3. Telemetry aggregate thật
Hiện worker là placeholder contract.
Khi map production:
items_opened/items_closed/items_acked ← operator queue events
approvals_requested/completed ← governance tables
executions_attempted/succeeded ← execution attempt table
conflicts_detected ← version conflict / rebase / optimistic lock fail logs
averages ← audit timeline timestamps
4. SQLite tests
Nếu test dùng SQLite memory:
JSONB đổi sang generic JSON
hoặc abstract type helper:
Postgres → JSONB
SQLite → JSON
15) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
add models
register models vào base import
add repositories
add schemas
add services
add routes
wire router
add migration
add tests
map worker schedule
Frontend
add queue types
add queue APIs
add SavedViewsBar
add WorkloadPanel
add QueueTelemetryCards
add RebalancePreviewModal
patch PendingApprovalsPanel / UnifiedOperatorQueue
add tests
16) KẾT QUẢ SAU PATCH NÀY
Sau bản này queue của bạn sẽ có thêm 3 lớp vận hành quan trọng:
A. Saved Views
Operator / approver có thể:
lưu bộ lọc riêng
mở lại work surface theo vai trò
giảm thao tác lọc lặp lại
B. Assignee Workload Balancing
Hệ bắt đầu nhìn được:
ai đang quá tải
ai còn capacity
nên rebalance item nào trước
C. Telemetry Rollups
Hệ bắt đầu đo được:
throughput
approval latency
execution success rate
conflict rate
Tức là queue chuyển từ:
“có endpoint để làm việc”
sang:
“có work surface + có logic phân tải + có số liệu để quản trị”
17) BƯỚC MẠNH NHẤT NGAY SAU BẢN NÀY
Bước mạnh nhất tiếp theo là:
PHASE 3 — AUTO-ASSIGN RECOMMENDATION ENGINE + QUEUE SLA + PRODUCTIVITY ANALYTICS
vì lúc đó hệ sẽ tiến thêm một nấc nữa:
không chỉ preview rebalance
mà bắt đầu recommend assign thật
theo:
specialty
provider/project familiarity
current capacity
SLA breach risk
historical acceptance / success rate
Đồng thời bổ sung:
time-to-first-action SLA
approval SLA breach
assignee productivity rollups
recommendation acceptance behavior
max active incidents / approval items per assignee
Nếu bạn muốn, tôi sẽ viết tiếp ngay bản PHASE 3 — AUTO-ASSIGN RECOMMENDATION ENGINE + QUEUE SLA + PRODUCTIVITY ANALYTICS cũng theo đúng format file-by-file paste-ready.
viết tiếp ngay bản PHASE 3 — AUTO-ASSIGN RECOMMENDATION ENGINE + QUEUE SLA + PRODUCTIVITY ANALYTICS cũng theo đúng format file-by-file paste-ready.
Đã suy nghĩ trong vài giây
Dưới đây là bản tiếp theo:
PHASE 3 — AUTO-ASSIGN RECOMMENDATION ENGINE + QUEUE SLA + PRODUCTIVITY ANALYTICS
FILE-BY-FILE PATCH FORMAT
Bản này nối trực tiếp sau:
Queue Saved Views
Assignee Workload Balancing
Telemetry Rollups
Mục tiêu là nâng queue từ mức:
nhìn được tải
preview rebalance
lên mức:
đề xuất assign thật
đo SLA thật
đo năng suất operator thật
đo recommendation acceptance thật
Tôi vẫn giữ nguyên nguyên tắc:
không tái cấu trúc vô cớ
paste-ready
bám monorepo production
có chỗ placeholder rõ ràng để map vào repo thật
0) PHẠM VI BẢN PATCH NÀY
Backend thêm
queue_assignment_recommendation model
queue_sla_policy model
queue_productivity_rollup model
recommendation repository
SLA policy repository
productivity rollup repository
recommendation engine service
SLA evaluation service
productivity analytics service
route:
recommendation preview
apply recommendation
SLA summary
productivity summary
worker rollup cho productivity
tests
Frontend thêm
recommendation types + api
SLA summary types + api
productivity types + api
AutoAssignPanel
SlaSummaryCards
ProductivityAnalyticsTable
patch queue screen
tests
1) BACKEND — MODELS
FILE: backend/app/models/queue_assignment_recommendation.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueAssignmentRecommendation(Base):
    __tablename__ = "queue_assignment_recommendation"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    current_assignee_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    recommended_assignee_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    recommendation_type: Mapped[str] = mapped_column(String(50), nullable=False, default="assign")
    # assign | reassign | escalate

    reason_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    impact_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sla_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="proposed", index=True)
    # proposed | accepted | rejected | expired | applied

    accepted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    features_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
FILE: backend/app/models/queue_sla_policy.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueSlaPolicy(Base):
    __tablename__ = "queue_sla_policy"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(100), nullable=False, default="default", index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    target_first_action_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    target_resolution_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    target_approval_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=14400)

    severity_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    priority_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
FILE: backend/app/models/queue_productivity_rollup.py
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueProductivityRollup(Base):
    __tablename__ = "queue_productivity_rollup"
    __table_args__ = (
        UniqueConstraint("rollup_date", "queue_key", "assignee_id", name="uq_queue_productivity_rollup"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rollup_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    assignee_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    assigned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_recommendation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_recommendation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approval_completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sla_breach_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    avg_time_to_first_action_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_resolution_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    productivity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
2) BACKEND — REPOSITORIES
FILE: backend/app/repositories/queue_assignment_recommendation_repository.py
from __future__ import annotations

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.models.queue_assignment_recommendation import QueueAssignmentRecommendation


class QueueAssignmentRecommendationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: dict) -> QueueAssignmentRecommendation:
        obj = QueueAssignmentRecommendation(**data)
        self.session.add(obj)
        self.session.flush()
        self.session.refresh(obj)
        return obj

    def get(self, recommendation_id: str) -> QueueAssignmentRecommendation | None:
        return self.session.get(QueueAssignmentRecommendation, recommendation_id)

    def list_for_item(self, item_id: str) -> list[QueueAssignmentRecommendation]:
        stmt = (
            select(QueueAssignmentRecommendation)
            .where(QueueAssignmentRecommendation.item_id == item_id)
            .order_by(desc(QueueAssignmentRecommendation.created_at))
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_proposed(self, queue_key: str, limit: int = 100) -> list[QueueAssignmentRecommendation]:
        stmt = (
            select(QueueAssignmentRecommendation)
            .where(
                and_(
                    QueueAssignmentRecommendation.queue_key == queue_key,
                    QueueAssignmentRecommendation.status == "proposed",
                )
            )
            .order_by(
                QueueAssignmentRecommendation.sla_risk_score.desc(),
                QueueAssignmentRecommendation.impact_score.desc(),
                QueueAssignmentRecommendation.created_at.desc(),
            )
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def update(self, obj: QueueAssignmentRecommendation, patch: dict) -> QueueAssignmentRecommendation:
        for key, value in patch.items():
            setattr(obj, key, value)
        self.session.add(obj)
        self.session.flush()
        self.session.refresh(obj)
        return obj
FILE: backend/app/repositories/queue_sla_policy_repository.py
from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.queue_sla_policy import QueueSlaPolicy


class QueueSlaPolicyRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: dict) -> QueueSlaPolicy:
        obj = QueueSlaPolicy(**data)
        self.session.add(obj)
        self.session.flush()
        self.session.refresh(obj)
        return obj

    def get_active_policy(self, queue_key: str, item_type: str = "default") -> QueueSlaPolicy | None:
        stmt = (
            select(QueueSlaPolicy)
            .where(
                and_(
                    QueueSlaPolicy.queue_key == queue_key,
                    QueueSlaPolicy.item_type == item_type,
                    QueueSlaPolicy.is_active.is_(True),
                )
            )
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()
FILE: backend/app/repositories/queue_productivity_rollup_repository.py
from __future__ import annotations

from datetime import date
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.queue_productivity_rollup import QueueProductivityRollup


class QueueProductivityRollupRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(
        self,
        *,
        rollup_date: date,
        queue_key: str,
        assignee_id: str,
        patch: dict,
    ) -> QueueProductivityRollup:
        stmt = select(QueueProductivityRollup).where(
            and_(
                QueueProductivityRollup.rollup_date == rollup_date,
                QueueProductivityRollup.queue_key == queue_key,
                QueueProductivityRollup.assignee_id == assignee_id,
            )
        )
        obj = self.session.execute(stmt).scalar_one_or_none()
        if not obj:
            obj = QueueProductivityRollup(
                rollup_date=rollup_date,
                queue_key=queue_key,
                assignee_id=assignee_id,
                **patch,
            )
            self.session.add(obj)
        else:
            for key, value in patch.items():
                setattr(obj, key, value)

        self.session.flush()
        self.session.refresh(obj)
        return obj

    def list_range(self, *, queue_key: str, start_date: date, end_date: date) -> list[QueueProductivityRollup]:
        stmt = (
            select(QueueProductivityRollup)
            .where(
                and_(
                    QueueProductivityRollup.queue_key == queue_key,
                    QueueProductivityRollup.rollup_date >= start_date,
                    QueueProductivityRollup.rollup_date <= end_date,
                )
            )
            .order_by(
                QueueProductivityRollup.rollup_date.asc(),
                QueueProductivityRollup.assignee_id.asc(),
            )
        )
        return list(self.session.execute(stmt).scalars().all())
3) BACKEND — SCHEMAS
FILE: backend/app/schemas/queue_assignment_recommendation.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class RecommendationCandidateInput(BaseModel):
    id: str
    assignee_id: str | None = None
    priority_score: float = 0
    severity: str | None = None
    requires_approval: bool = False
    is_overdue: bool = False
    has_recent_conflict: bool = False
    item_type: str = "default"
    provider: str | None = None
    project_id: str | None = None
    created_at: str | None = None


class AssigneeFeatureInput(BaseModel):
    assignee_id: str
    active_count: int = 0
    overdue_count: int = 0
    conflict_count: int = 0
    specialty_keys: list[str] = Field(default_factory=list)
    recent_success_rate: float = 0.0
    recommendation_acceptance_rate: float = 0.0
    avg_time_to_first_action_sec: float = 0.0


class RecommendationPreviewRequest(BaseModel):
    queue_key: str
    items: list[RecommendationCandidateInput]
    assignees: list[AssigneeFeatureInput]
    max_recommendations: int = 20


class QueueAssignmentRecommendationRead(BaseModel):
    id: str
    queue_key: str
    item_id: str
    current_assignee_id: str | None = None
    recommended_assignee_id: str | None = None
    recommendation_type: str
    reason_codes: list
    rationale: str | None = None
    confidence_score: float
    impact_score: float
    priority_score: float
    sla_risk_score: float
    status: str
    applied: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RecommendationActionRequest(BaseModel):
    actor_id: str
    apply_assignment: bool = False
    rejection_reason: str | None = None
FILE: backend/app/schemas/queue_sla.py
from __future__ import annotations

from pydantic import BaseModel


class QueueSlaItemSnapshot(BaseModel):
    id: str
    item_type: str = "default"
    severity: str | None = None
    priority_score: float = 0
    created_at_epoch_sec: int
    first_action_at_epoch_sec: int | None = None
    resolved_at_epoch_sec: int | None = None
    approval_completed_at_epoch_sec: int | None = None


class QueueSlaSummaryRequest(BaseModel):
    queue_key: str
    items: list[QueueSlaItemSnapshot]


class QueueSlaSummary(BaseModel):
    queue_key: str
    total_items: int
    first_action_breach_count: int
    resolution_breach_count: int
    approval_breach_count: int
    healthy_count: int
    breach_rate: float
FILE: backend/app/schemas/queue_productivity.py
from __future__ import annotations

from datetime import date
from pydantic import BaseModel


class QueueProductivityPoint(BaseModel):
    rollup_date: date
    assignee_id: str
    assigned_count: int
    accepted_recommendation_count: int
    rejected_recommendation_count: int
    first_action_count: int
    resolved_count: int
    approval_completed_count: int
    execution_success_count: int
    conflict_count: int
    sla_breach_count: int
    avg_time_to_first_action_sec: float
    avg_resolution_sec: float
    productivity_score: float


class QueueProductivitySummary(BaseModel):
    queue_key: str
    points: list[QueueProductivityPoint]
    totals_by_assignee: dict
4) BACKEND — SERVICES
FILE: backend/app/services/queue_recommendation_engine_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.queue_assignment_recommendation_repository import QueueAssignmentRecommendationRepository
from app.schemas.queue_assignment_recommendation import (
    AssigneeFeatureInput,
    QueueAssignmentRecommendationRead,
    RecommendationActionRequest,
    RecommendationCandidateInput,
    RecommendationPreviewRequest,
)


class QueueRecommendationEngineService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = QueueAssignmentRecommendationRepository(session)

    def _score_candidate(self, item: RecommendationCandidateInput, assignee: AssigneeFeatureInput) -> tuple[float, list[str], str]:
        score = 0.0
        reasons: list[str] = []

        load_penalty = assignee.active_count * 1.0 + assignee.overdue_count * 2.0 + assignee.conflict_count * 1.5
        score += max(0.0, 100.0 - load_penalty)

        if item.provider and item.provider in assignee.specialty_keys:
            score += 15.0
            reasons.append("provider_specialty_match")

        if item.project_id and item.project_id in assignee.specialty_keys:
            score += 10.0
            reasons.append("project_familiarity_match")

        score += assignee.recent_success_rate * 20.0
        if assignee.recommendation_acceptance_rate > 0:
            score += assignee.recommendation_acceptance_rate * 10.0
            reasons.append("high_recommendation_acceptance")

        if assignee.avg_time_to_first_action_sec > 0:
            speed_bonus = max(0.0, 10.0 - (assignee.avg_time_to_first_action_sec / 3600.0))
            score += speed_bonus
            reasons.append("strong_first_action_speed")

        if item.is_overdue:
            score += 8.0
            reasons.append("sla_risk_present")

        if item.has_recent_conflict:
            score -= 5.0
            reasons.append("recent_conflict_penalty")

        rationale = ", ".join(reasons) if reasons else "balanced_load_selection"
        return round(score, 2), reasons or ["balanced_load_selection"], rationale

    def preview(self, payload: RecommendationPreviewRequest) -> list[QueueAssignmentRecommendationRead]:
        created = []

        for item in payload.items:
            best = None
            best_score = -1.0
            best_reasons: list[str] = []
            best_rationale = "balanced_load_selection"

            for assignee in payload.assignees:
                score, reasons, rationale = self._score_candidate(item, assignee)
                if score > best_score:
                    best = assignee
                    best_score = score
                    best_reasons = reasons
                    best_rationale = rationale

            if not best:
                continue

            confidence_score = min(100.0, best_score)
            impact_score = min(100.0, item.priority_score + (10.0 if item.is_overdue else 0.0))
            sla_risk_score = min(100.0, (20.0 if item.is_overdue else 0.0) + item.priority_score * 0.5)

            obj = self.repo.create(
                {
                    "queue_key": payload.queue_key,
                    "item_id": item.id,
                    "current_assignee_id": item.assignee_id,
                    "recommended_assignee_id": best.assignee_id,
                    "recommendation_type": "assign" if not item.assignee_id else "reassign",
                    "reason_codes": best_reasons,
                    "rationale": best_rationale,
                    "confidence_score": confidence_score,
                    "impact_score": impact_score,
                    "priority_score": item.priority_score,
                    "sla_risk_score": sla_risk_score,
                    "status": "proposed",
                    "features_snapshot": {
                        "item": item.model_dump(),
                        "recommended_assignee": best.model_dump(),
                    },
                }
            )
            created.append(obj)

        self.session.commit()
        return [QueueAssignmentRecommendationRead.model_validate(x) for x in created]

    def list_proposed(self, queue_key: str):
        return self.repo.list_proposed(queue_key)

    def accept(self, recommendation_id: str, payload: RecommendationActionRequest):
        obj = self.repo.get(recommendation_id)
        if not obj:
            raise ValueError("recommendation_not_found")

        patch = {
            "status": "accepted",
            "accepted_by": payload.actor_id,
        }
        if payload.apply_assignment:
            patch["applied"] = True
            patch["status"] = "applied"

        obj = self.repo.update(obj, patch)
        self.session.commit()
        return obj

    def reject(self, recommendation_id: str, payload: RecommendationActionRequest):
        obj = self.repo.get(recommendation_id)
        if not obj:
            raise ValueError("recommendation_not_found")

        obj = self.repo.update(
            obj,
            {
                "status": "rejected",
                "rejected_by": payload.actor_id,
                "rejection_reason": payload.rejection_reason or "Rejected by operator",
            },
        )
        self.session.commit()
        return obj
FILE: backend/app/services/queue_sla_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.queue_sla_policy_repository import QueueSlaPolicyRepository
from app.schemas.queue_sla import QueueSlaSummary, QueueSlaSummaryRequest


class QueueSlaService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = QueueSlaPolicyRepository(session)

    def summarize(self, payload: QueueSlaSummaryRequest) -> QueueSlaSummary:
        total_items = len(payload.items)
        first_action_breach_count = 0
        resolution_breach_count = 0
        approval_breach_count = 0
        healthy_count = 0

        for item in payload.items:
            policy = self.repo.get_active_policy(payload.queue_key, item.item_type)
            target_first_action = policy.target_first_action_sec if policy else 3600
            target_resolution = policy.target_resolution_sec if policy else 86400
            target_approval = policy.target_approval_sec if policy else 14400

            has_breach = False

            if item.first_action_at_epoch_sec is not None:
                if (item.first_action_at_epoch_sec - item.created_at_epoch_sec) > target_first_action:
                    first_action_breach_count += 1
                    has_breach = True

            if item.resolved_at_epoch_sec is not None:
                if (item.resolved_at_epoch_sec - item.created_at_epoch_sec) > target_resolution:
                    resolution_breach_count += 1
                    has_breach = True

            if item.approval_completed_at_epoch_sec is not None:
                if (item.approval_completed_at_epoch_sec - item.created_at_epoch_sec) > target_approval:
                    approval_breach_count += 1
                    has_breach = True

            if not has_breach:
                healthy_count += 1

        total_breaches = first_action_breach_count + resolution_breach_count + approval_breach_count
        breach_rate = round((total_breaches / total_items), 4) if total_items else 0.0

        return QueueSlaSummary(
            queue_key=payload.queue_key,
            total_items=total_items,
            first_action_breach_count=first_action_breach_count,
            resolution_breach_count=resolution_breach_count,
            approval_breach_count=approval_breach_count,
            healthy_count=healthy_count,
            breach_rate=breach_rate,
        )
FILE: backend/app/services/queue_productivity_analytics_service.py
from __future__ import annotations

from datetime import date
from sqlalchemy.orm import Session

from app.repositories.queue_productivity_rollup_repository import QueueProductivityRollupRepository
from app.schemas.queue_productivity import QueueProductivityPoint, QueueProductivitySummary


class QueueProductivityAnalyticsService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = QueueProductivityRollupRepository(session)

    def get_summary(self, *, queue_key: str, start_date: date, end_date: date) -> QueueProductivitySummary:
        rows = self.repo.list_range(queue_key=queue_key, start_date=start_date, end_date=end_date)

        points = [
            QueueProductivityPoint(
                rollup_date=row.rollup_date,
                assignee_id=row.assignee_id,
                assigned_count=row.assigned_count,
                accepted_recommendation_count=row.accepted_recommendation_count,
                rejected_recommendation_count=row.rejected_recommendation_count,
                first_action_count=row.first_action_count,
                resolved_count=row.resolved_count,
                approval_completed_count=row.approval_completed_count,
                execution_success_count=row.execution_success_count,
                conflict_count=row.conflict_count,
                sla_breach_count=row.sla_breach_count,
                avg_time_to_first_action_sec=row.avg_time_to_first_action_sec,
                avg_resolution_sec=row.avg_resolution_sec,
                productivity_score=row.productivity_score,
            )
            for row in rows
        ]

        totals_by_assignee: dict[str, dict] = {}
        for point in points:
            bucket = totals_by_assignee.setdefault(
                point.assignee_id,
                {
                    "assigned_count": 0,
                    "accepted_recommendation_count": 0,
                    "rejected_recommendation_count": 0,
                    "first_action_count": 0,
                    "resolved_count": 0,
                    "approval_completed_count": 0,
                    "execution_success_count": 0,
                    "conflict_count": 0,
                    "sla_breach_count": 0,
                    "productivity_score_sum": 0.0,
                    "days": 0,
                },
            )
            bucket["assigned_count"] += point.assigned_count
            bucket["accepted_recommendation_count"] += point.accepted_recommendation_count
            bucket["rejected_recommendation_count"] += point.rejected_recommendation_count
            bucket["first_action_count"] += point.first_action_count
            bucket["resolved_count"] += point.resolved_count
            bucket["approval_completed_count"] += point.approval_completed_count
            bucket["execution_success_count"] += point.execution_success_count
            bucket["conflict_count"] += point.conflict_count
            bucket["sla_breach_count"] += point.sla_breach_count
            bucket["productivity_score_sum"] += point.productivity_score
            bucket["days"] += 1

        for assignee_id, bucket in totals_by_assignee.items():
            bucket["avg_productivity_score"] = round(
                bucket["productivity_score_sum"] / bucket["days"], 2
            ) if bucket["days"] else 0.0

        return QueueProductivitySummary(
            queue_key=queue_key,
            points=points,
            totals_by_assignee=totals_by_assignee,
        )
5) BACKEND — WORKER
FILE: backend/app/workers/queue_productivity_rollup_worker.py
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.queue_productivity_rollup_repository import QueueProductivityRollupRepository


def build_queue_productivity_rollups_for_day(target_date: date) -> None:
    session: Session = SessionLocal()
    try:
        repo = QueueProductivityRollupRepository(session)

        # TODO map vào audit log / operator actions / governance execution thật.
        # Patch này giữ contract ổn định để thay logic aggregate sau.

        samples = [
            {
                "queue_key": "governance_pending",
                "assignee_id": "operator-1",
                "assigned_count": 5,
                "accepted_recommendation_count": 2,
                "rejected_recommendation_count": 1,
                "first_action_count": 4,
                "resolved_count": 3,
                "approval_completed_count": 2,
                "execution_success_count": 2,
                "conflict_count": 1,
                "sla_breach_count": 1,
                "avg_time_to_first_action_sec": 900.0,
                "avg_resolution_sec": 7200.0,
                "productivity_score": 81.0,
            }
        ]

        for row in samples:
            repo.upsert(
                rollup_date=target_date,
                queue_key=row["queue_key"],
                assignee_id=row["assignee_id"],
                patch={k: v for k, v in row.items() if k not in {"queue_key", "assignee_id"}},
            )

        session.commit()
    finally:
        session.close()


def build_recent_queue_productivity_rollups(days: int = 7) -> None:
    today = date.today()
    for offset in range(days):
        build_queue_productivity_rollups_for_day(today - timedelta(days=offset))
6) BACKEND — ROUTES
FILE: backend/app/api/routes/queue_recommendations.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.queue_assignment_recommendation import (
    QueueAssignmentRecommendationRead,
    RecommendationActionRequest,
    RecommendationPreviewRequest,
)
from app.services.queue_recommendation_engine_service import QueueRecommendationEngineService

router = APIRouter(prefix="/queue/recommendations", tags=["queue-recommendations"])


@router.post("/preview", response_model=list[QueueAssignmentRecommendationRead])
def preview_recommendations(
    payload: RecommendationPreviewRequest,
    session: Session = Depends(get_db),
):
    service = QueueRecommendationEngineService(session)
    return service.preview(payload)


@router.get("/proposed", response_model=list[QueueAssignmentRecommendationRead])
def list_proposed_recommendations(
    queue_key: str = Query(...),
    session: Session = Depends(get_db),
):
    service = QueueRecommendationEngineService(session)
    return service.list_proposed(queue_key)


@router.post("/{recommendation_id}/accept", response_model=QueueAssignmentRecommendationRead)
def accept_recommendation(
    recommendation_id: str,
    payload: RecommendationActionRequest,
    session: Session = Depends(get_db),
):
    service = QueueRecommendationEngineService(session)
    try:
        return service.accept(recommendation_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{recommendation_id}/reject", response_model=QueueAssignmentRecommendationRead)
def reject_recommendation(
    recommendation_id: str,
    payload: RecommendationActionRequest,
    session: Session = Depends(get_db),
):
    service = QueueRecommendationEngineService(session)
    try:
        return service.reject(recommendation_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
FILE: backend/app/api/routes/queue_sla.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.queue_sla import QueueSlaSummary, QueueSlaSummaryRequest
from app.services.queue_sla_service import QueueSlaService

router = APIRouter(prefix="/queue/sla", tags=["queue-sla"])


@router.post("/summary", response_model=QueueSlaSummary)
def get_queue_sla_summary(
    payload: QueueSlaSummaryRequest,
    session: Session = Depends(get_db),
):
    service = QueueSlaService(session)
    return service.summarize(payload)
FILE: backend/app/api/routes/queue_productivity.py
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.queue_productivity_analytics_service import QueueProductivityAnalyticsService

router = APIRouter(prefix="/queue/productivity", tags=["queue-productivity"])


@router.get("/summary")
def get_queue_productivity_summary(
    queue_key: str = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    session: Session = Depends(get_db),
):
    service = QueueProductivityAnalyticsService(session)
    return service.get_summary(
        queue_key=queue_key,
        start_date=start_date,
        end_date=end_date,
    )
FILE: backend/app/api/router.py
PATCH
from app.api.routes import queue_recommendations, queue_sla, queue_productivity
api_router.include_router(queue_recommendations.router)
api_router.include_router(queue_sla.router)
api_router.include_router(queue_productivity.router)
7) BACKEND — ALEMBIC MIGRATION
FILE: backend/alembic/versions/phase3_auto_assign_sla_productivity.py
"""phase3 auto assign sla productivity

Revision ID: phase3_auto_assign_sla_productivity
Revises: <PUT_PREVIOUS_REVISION_HERE>
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "phase3_auto_assign_sla_productivity"
down_revision = "<PUT_PREVIOUS_REVISION_HERE>"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "queue_assignment_recommendation",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("item_id", sa.String(length=255), nullable=False),
        sa.Column("current_assignee_id", sa.String(length=255), nullable=True),
        sa.Column("recommended_assignee_id", sa.String(length=255), nullable=True),
        sa.Column("recommendation_type", sa.String(length=50), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("impact_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sla_risk_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="proposed"),
        sa.Column("accepted_by", sa.String(length=255), nullable=True),
        sa.Column("rejected_by", sa.String(length=255), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("features_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queue_assignment_recommendation_queue_key", "queue_assignment_recommendation", ["queue_key"])
    op.create_index("ix_queue_assignment_recommendation_item_id", "queue_assignment_recommendation", ["item_id"])
    op.create_index("ix_queue_assignment_recommendation_current_assignee_id", "queue_assignment_recommendation", ["current_assignee_id"])
    op.create_index("ix_queue_assignment_recommendation_recommended_assignee_id", "queue_assignment_recommendation", ["recommended_assignee_id"])
    op.create_index("ix_queue_assignment_recommendation_status", "queue_assignment_recommendation", ["status"])

    op.create_table(
        "queue_sla_policy",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("item_type", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_first_action_sec", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("target_resolution_sec", sa.Integer(), nullable=False, server_default="86400"),
        sa.Column("target_approval_sec", sa.Integer(), nullable=False, server_default="14400"),
        sa.Column("severity_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("priority_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queue_sla_policy_queue_key", "queue_sla_policy", ["queue_key"])
    op.create_index("ix_queue_sla_policy_item_type", "queue_sla_policy", ["item_type"])

    op.create_table(
        "queue_productivity_rollup",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rollup_date", sa.Date(), nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("assignee_id", sa.String(length=255), nullable=False),
        sa.Column("assigned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_recommendation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_recommendation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_action_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approval_completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflict_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sla_breach_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_time_to_first_action_sec", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_resolution_sec", sa.Float(), nullable=False, server_default="0"),
        sa.Column("productivity_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rollup_date", "queue_key", "assignee_id", name="uq_queue_productivity_rollup"),
    )
    op.create_index("ix_queue_productivity_rollup_rollup_date", "queue_productivity_rollup", ["rollup_date"])
    op.create_index("ix_queue_productivity_rollup_queue_key", "queue_productivity_rollup", ["queue_key"])
    op.create_index("ix_queue_productivity_rollup_assignee_id", "queue_productivity_rollup", ["assignee_id"])


def downgrade():
    op.drop_index("ix_queue_productivity_rollup_assignee_id", table_name="queue_productivity_rollup")
    op.drop_index("ix_queue_productivity_rollup_queue_key", table_name="queue_productivity_rollup")
    op.drop_index("ix_queue_productivity_rollup_rollup_date", table_name="queue_productivity_rollup")
    op.drop_table("queue_productivity_rollup")

    op.drop_index("ix_queue_sla_policy_item_type", table_name="queue_sla_policy")
    op.drop_index("ix_queue_sla_policy_queue_key", table_name="queue_sla_policy")
    op.drop_table("queue_sla_policy")

    op.drop_index("ix_queue_assignment_recommendation_status", table_name="queue_assignment_recommendation")
    op.drop_index("ix_queue_assignment_recommendation_recommended_assignee_id", table_name="queue_assignment_recommendation")
    op.drop_index("ix_queue_assignment_recommendation_current_assignee_id", table_name="queue_assignment_recommendation")
    op.drop_index("ix_queue_assignment_recommendation_item_id", table_name="queue_assignment_recommendation")
    op.drop_index("ix_queue_assignment_recommendation_queue_key", table_name="queue_assignment_recommendation")
    op.drop_table("queue_assignment_recommendation")
8) BACKEND — TESTS
FILE: backend/tests/services/test_queue_recommendation_engine_service.py
def test_preview_creates_recommendations_and_prefers_lower_load_specialty_match(session):
    from app.services.queue_recommendation_engine_service import QueueRecommendationEngineService
    from app.schemas.queue_assignment_recommendation import RecommendationPreviewRequest

    service = QueueRecommendationEngineService(session)

    payload = RecommendationPreviewRequest(
        queue_key="operator_queue",
        items=[
            {
                "id": "item-1",
                "assignee_id": None,
                "priority_score": 90,
                "provider": "runway",
                "project_id": "p-1",
                "is_overdue": True,
            }
        ],
        assignees=[
            {
                "assignee_id": "u1",
                "active_count": 10,
                "overdue_count": 2,
                "conflict_count": 1,
                "specialty_keys": [],
                "recent_success_rate": 0.5,
                "recommendation_acceptance_rate": 0.3,
                "avg_time_to_first_action_sec": 4000,
            },
            {
                "assignee_id": "u2",
                "active_count": 2,
                "overdue_count": 0,
                "conflict_count": 0,
                "specialty_keys": ["runway", "p-1"],
                "recent_success_rate": 0.9,
                "recommendation_acceptance_rate": 0.8,
                "avg_time_to_first_action_sec": 600,
            },
        ],
    )

    results = service.preview(payload)
    assert len(results) == 1
    assert results[0].recommended_assignee_id == "u2"
FILE: backend/tests/services/test_queue_sla_service.py
def test_queue_sla_summary_counts_breaches(session):
    from app.services.queue_sla_service import QueueSlaService
    from app.schemas.queue_sla import QueueSlaSummaryRequest

    service = QueueSlaService(session)

    payload = QueueSlaSummaryRequest(
        queue_key="operator_queue",
        items=[
            {
                "id": "a",
                "created_at_epoch_sec": 0,
                "first_action_at_epoch_sec": 7200,
                "resolved_at_epoch_sec": 10000,
                "approval_completed_at_epoch_sec": 2000,
            },
            {
                "id": "b",
                "created_at_epoch_sec": 0,
                "first_action_at_epoch_sec": 100,
                "resolved_at_epoch_sec": 200,
                "approval_completed_at_epoch_sec": 300,
            },
        ],
    )

    result = service.summarize(payload)
    assert result.total_items == 2
    assert result.first_action_breach_count >= 1
FILE: backend/tests/services/test_queue_productivity_analytics_service.py
from datetime import date


def test_queue_productivity_summary_aggregates_by_assignee(session):
    from app.repositories.queue_productivity_rollup_repository import QueueProductivityRollupRepository
    from app.services.queue_productivity_analytics_service import QueueProductivityAnalyticsService

    repo = QueueProductivityRollupRepository(session)
    repo.upsert(
        rollup_date=date(2026, 4, 12),
        queue_key="operator_queue",
        assignee_id="u1",
        patch={
            "assigned_count": 5,
            "accepted_recommendation_count": 2,
            "rejected_recommendation_count": 1,
            "first_action_count": 4,
            "resolved_count": 3,
            "approval_completed_count": 2,
            "execution_success_count": 2,
            "conflict_count": 1,
            "sla_breach_count": 1,
            "avg_time_to_first_action_sec": 500.0,
            "avg_resolution_sec": 1500.0,
            "productivity_score": 84.0,
        },
    )
    session.commit()

    service = QueueProductivityAnalyticsService(session)
    result = service.get_summary(
        queue_key="operator_queue",
        start_date=date(2026, 4, 12),
        end_date=date(2026, 4, 12),
    )

    assert result.totals_by_assignee["u1"]["assigned_count"] == 5
    assert result.totals_by_assignee["u1"]["avg_productivity_score"] == 84.0
FILE: backend/tests/api/test_queue_recommendations_api.py
def test_preview_and_accept_recommendation(client, auth_headers):
    preview_payload = {
        "queue_key": "operator_queue",
        "items": [
            {"id": "item-1", "priority_score": 80, "item_type": "default"}
        ],
        "assignees": [
            {"assignee_id": "u1", "active_count": 1, "recent_success_rate": 0.9}
        ],
    }

    preview_res = client.post("/api/v1/queue/recommendations/preview", json=preview_payload, headers=auth_headers)
    assert preview_res.status_code == 200, preview_res.text
    recommendation_id = preview_res.json()[0]["id"]

    accept_res = client.post(
        f"/api/v1/queue/recommendations/{recommendation_id}/accept",
        json={"actor_id": "operator-admin", "apply_assignment": False},
        headers=auth_headers,
    )
    assert accept_res.status_code == 200, accept_res.text
    assert accept_res.json()["status"] == "accepted"
9) FRONTEND — TYPES
FILE: frontend/src/types/queueRecommendation.ts
export type QueueAssignmentRecommendation = {
  id: string;
  queue_key: string;
  item_id: string;
  current_assignee_id?: string | null;
  recommended_assignee_id?: string | null;
  recommendation_type: string;
  reason_codes: string[];
  rationale?: string | null;
  confidence_score: number;
  impact_score: number;
  priority_score: number;
  sla_risk_score: number;
  status: string;
  applied: boolean;
  created_at: string;
};
FILE: frontend/src/types/queueSla.ts
export type QueueSlaSummary = {
  queue_key: string;
  total_items: number;
  first_action_breach_count: number;
  resolution_breach_count: number;
  approval_breach_count: number;
  healthy_count: number;
  breach_rate: number;
};
FILE: frontend/src/types/queueProductivity.ts
export type QueueProductivitySummary = {
  queue_key: string;
  points: Array<{
    rollup_date: string;
    assignee_id: string;
    assigned_count: number;
    accepted_recommendation_count: number;
    rejected_recommendation_count: number;
    first_action_count: number;
    resolved_count: number;
    approval_completed_count: number;
    execution_success_count: number;
    conflict_count: number;
    sla_breach_count: number;
    avg_time_to_first_action_sec: number;
    avg_resolution_sec: number;
    productivity_score: number;
  }>;
  totals_by_assignee: Record<string, Record<string, number>>;
};
10) FRONTEND — API
FILE: frontend/src/api/queueRecommendationsApi.ts
import { apiClient } from "./client";
import { QueueAssignmentRecommendation } from "../types/queueRecommendation";

export async function previewQueueRecommendations(payload: Record<string, unknown>): Promise<QueueAssignmentRecommendation[]> {
  const res = await apiClient.post("/queue/recommendations/preview", payload);
  return res.data;
}

export async function listProposedQueueRecommendations(queueKey: string): Promise<QueueAssignmentRecommendation[]> {
  const res = await apiClient.get("/queue/recommendations/proposed", {
    params: { queue_key: queueKey },
  });
  return res.data;
}

export async function acceptQueueRecommendation(recommendationId: string, payload: Record<string, unknown>) {
  const res = await apiClient.post(`/queue/recommendations/${recommendationId}/accept`, payload);
  return res.data;
}

export async function rejectQueueRecommendation(recommendationId: string, payload: Record<string, unknown>) {
  const res = await apiClient.post(`/queue/recommendations/${recommendationId}/reject`, payload);
  return res.data;
}
FILE: frontend/src/api/queueSlaApi.ts
import { apiClient } from "./client";
import { QueueSlaSummary } from "../types/queueSla";

export async function fetchQueueSlaSummary(payload: Record<string, unknown>): Promise<QueueSlaSummary> {
  const res = await apiClient.post("/queue/sla/summary", payload);
  return res.data;
}
FILE: frontend/src/api/queueProductivityApi.ts
import { apiClient } from "./client";
import { QueueProductivitySummary } from "../types/queueProductivity";

export async function fetchQueueProductivitySummary(params: {
  queue_key: string;
  start_date: string;
  end_date: string;
}): Promise<QueueProductivitySummary> {
  const res = await apiClient.get("/queue/productivity/summary", { params });
  return res.data;
}
11) FRONTEND — COMPONENTS
FILE: frontend/src/components/queue/AutoAssignPanel.tsx
import React from "react";
import { QueueAssignmentRecommendation } from "../../types/queueRecommendation";

type Props = {
  recommendations: QueueAssignmentRecommendation[];
  onAccept: (recommendationId: string) => void;
  onReject: (recommendationId: string) => void;
};

export function AutoAssignPanel({ recommendations, onAccept, onReject }: Props) {
  return (
    <div className="rounded-xl border p-4">
      <div className="mb-3 text-sm font-semibold">Auto-assign recommendations</div>
      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left">
              <th className="py-2">Item</th>
              <th>Current</th>
              <th>Suggested</th>
              <th>Confidence</th>
              <th>Impact</th>
              <th>SLA risk</th>
              <th>Reason</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {recommendations.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="py-2">{item.item_id}</td>
                <td>{item.current_assignee_id ?? "-"}</td>
                <td>{item.recommended_assignee_id ?? "-"}</td>
                <td>{item.confidence_score}</td>
                <td>{item.impact_score}</td>
                <td>{item.sla_risk_score}</td>
                <td>{item.reason_codes.join(", ")}</td>
                <td>
                  <div className="flex gap-2">
                    <button className="rounded-md border px-2 py-1" onClick={() => onAccept(item.id)}>
                      Accept
                    </button>
                    <button className="rounded-md border px-2 py-1" onClick={() => onReject(item.id)}>
                      Reject
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
FILE: frontend/src/components/queue/SlaSummaryCards.tsx
import React from "react";
import { QueueSlaSummary } from "../../types/queueSla";

type Props = {
  summary?: QueueSlaSummary | null;
};

export function SlaSummaryCards({ summary }: Props) {
  if (!summary) return null;

  const cards = [
    ["Total", summary.total_items],
    ["Healthy", summary.healthy_count],
    ["First action breach", summary.first_action_breach_count],
    ["Resolution breach", summary.resolution_breach_count],
    ["Approval breach", summary.approval_breach_count],
    ["Breach rate", summary.breach_rate],
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
      {cards.map(([label, value]) => (
        <div key={String(label)} className="rounded-xl border p-4">
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="mt-1 text-xl font-semibold">{value}</div>
        </div>
      ))}
    </div>
  );
}
FILE: frontend/src/components/queue/ProductivityAnalyticsTable.tsx
import React from "react";
import { QueueProductivitySummary } from "../../types/queueProductivity";

type Props = {
  summary?: QueueProductivitySummary | null;
};

export function ProductivityAnalyticsTable({ summary }: Props) {
  const rows = summary?.totals_by_assignee ?? {};

  return (
    <div className="rounded-xl border p-4">
      <div className="mb-3 text-sm font-semibold">Productivity analytics</div>
      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left">
              <th className="py-2">Assignee</th>
              <th>Assigned</th>
              <th>Accepted rec</th>
              <th>Rejected rec</th>
              <th>Resolved</th>
              <th>Execution success</th>
              <th>Conflicts</th>
              <th>SLA breach</th>
              <th>Avg productivity</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(rows).map(([assigneeId, item]) => (
              <tr key={assigneeId} className="border-t">
                <td className="py-2">{assigneeId}</td>
                <td>{item.assigned_count ?? 0}</td>
                <td>{item.accepted_recommendation_count ?? 0}</td>
                <td>{item.rejected_recommendation_count ?? 0}</td>
                <td>{item.resolved_count ?? 0}</td>
                <td>{item.execution_success_count ?? 0}</td>
                <td>{item.conflict_count ?? 0}</td>
                <td>{item.sla_breach_count ?? 0}</td>
                <td>{item.avg_productivity_score ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
12) FRONTEND — PATCH QUEUE SCREEN
FILE: frontend/src/components/governance/PendingApprovalsPanel.tsx
PATCH Ý TƯỞNG
Thêm import:
import React, { useEffect, useMemo, useState } from "react";
import { AutoAssignPanel } from "../queue/AutoAssignPanel";
import { SlaSummaryCards } from "../queue/SlaSummaryCards";
import { ProductivityAnalyticsTable } from "../queue/ProductivityAnalyticsTable";
import {
  acceptQueueRecommendation,
  listProposedQueueRecommendations,
  previewQueueRecommendations,
  rejectQueueRecommendation,
} from "../../api/queueRecommendationsApi";
import { fetchQueueSlaSummary } from "../../api/queueSlaApi";
import { fetchQueueProductivitySummary } from "../../api/queueProductivityApi";
State mới
const [recommendations, setRecommendations] = useState([]);
const [slaSummary, setSlaSummary] = useState(null);
const [productivitySummary, setProductivitySummary] = useState(null);
Map pending approvals sang payload recommendation/SLA
const recommendationItems = useMemo(
  () =>
    pendingApprovals.map((item) => ({
      id: item.id,
      assignee_id: item.assignee_id ?? null,
      priority_score: item.priority_score ?? 0,
      severity: item.severity ?? "medium",
      requires_approval: true,
      is_overdue: Boolean(item.is_overdue),
      has_recent_conflict: Boolean(item.has_recent_conflict),
      item_type: item.item_type ?? "default",
      provider: item.provider ?? null,
      project_id: item.project_id ?? null,
    })),
  [pendingApprovals]
);
Load recommendations + sla + productivity
useEffect(() => {
  async function loadAdvancedQueueAnalytics() {
    try {
      const [previewRes, slaRes, productivityRes] = await Promise.all([
        previewQueueRecommendations({
          queue_key: "governance_pending",
          items: recommendationItems,
          assignees: operators.map((op) => ({
            assignee_id: op.id,
            active_count: op.active_count ?? 0,
            overdue_count: op.overdue_count ?? 0,
            conflict_count: op.conflict_count ?? 0,
            specialty_keys: op.specialty_keys ?? [],
            recent_success_rate: op.recent_success_rate ?? 0,
            recommendation_acceptance_rate: op.recommendation_acceptance_rate ?? 0,
            avg_time_to_first_action_sec: op.avg_time_to_first_action_sec ?? 0,
          })),
        }),
        fetchQueueSlaSummary({
          queue_key: "governance_pending",
          items: pendingApprovals.map((item) => ({
            id: item.id,
            item_type: item.item_type ?? "default",
            severity: item.severity ?? "medium",
            priority_score: item.priority_score ?? 0,
            created_at_epoch_sec: item.created_at_epoch_sec,
            first_action_at_epoch_sec: item.first_action_at_epoch_sec ?? null,
            resolved_at_epoch_sec: item.resolved_at_epoch_sec ?? null,
            approval_completed_at_epoch_sec: item.approval_completed_at_epoch_sec ?? null,
          })),
        }),
        fetchQueueProductivitySummary({
          queue_key: "governance_pending",
          start_date: range.startDate,
          end_date: range.endDate,
        }),
      ]);

      setRecommendations(previewRes);
      setSlaSummary(slaRes);
      setProductivitySummary(productivityRes);
    } catch (error) {
      onToast?.({
        title: "Không tải được advanced queue analytics",
        description: String(error),
        variant: "destructive",
      });
    }
  }

  if (pendingApprovals.length > 0) {
    void loadAdvancedQueueAnalytics();
  }
}, [pendingApprovals, operators, range.startDate, range.endDate]);
Accept / reject handlers
async function handleAcceptRecommendation(recommendationId: string) {
  try {
    await acceptQueueRecommendation(recommendationId, {
      actor_id: actorId,
      apply_assignment: false,
    });
    onToast?.({ title: "Đã accept recommendation" });
    const updated = await listProposedQueueRecommendations("governance_pending");
    setRecommendations(updated);
  } catch (error) {
    onToast?.({
      title: "Accept recommendation thất bại",
      description: String(error),
      variant: "destructive",
    });
  }
}

async function handleRejectRecommendation(recommendationId: string) {
  try {
    await rejectQueueRecommendation(recommendationId, {
      actor_id: actorId,
      rejection_reason: "Rejected by operator",
    });
    onToast?.({ title: "Đã reject recommendation" });
    const updated = await listProposedQueueRecommendations("governance_pending");
    setRecommendations(updated);
  } catch (error) {
    onToast?.({
      title: "Reject recommendation thất bại",
      description: String(error),
      variant: "destructive",
    });
  }
}
Render thêm khối mới
<div className="space-y-4">
  <SlaSummaryCards summary={slaSummary} />

  <AutoAssignPanel
    recommendations={recommendations}
    onAccept={handleAcceptRecommendation}
    onReject={handleRejectRecommendation}
  />

  <ProductivityAnalyticsTable summary={productivitySummary} />

  {/* existing queue table / timeline / bulk actions below */}
</div>
13) FRONTEND — TESTS
FILE: frontend/src/components/queue/__tests__/AutoAssignPanel.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AutoAssignPanel } from "../AutoAssignPanel";

test("renders recommendations and handles accept", async () => {
  const user = userEvent.setup();
  const onAccept = jest.fn();
  const onReject = jest.fn();

  render(
    <AutoAssignPanel
      recommendations={[
        {
          id: "r1",
          queue_key: "operator_queue",
          item_id: "item-1",
          current_assignee_id: null,
          recommended_assignee_id: "u1",
          recommendation_type: "assign",
          reason_codes: ["balanced_load_selection"],
          confidence_score: 90,
          impact_score: 80,
          priority_score: 70,
          sla_risk_score: 60,
          status: "proposed",
          applied: false,
          created_at: "",
        },
      ]}
      onAccept={onAccept}
      onReject={onReject}
    />
  );

  await user.click(screen.getByText("Accept"));
  expect(onAccept).toHaveBeenCalledWith("r1");
});
FILE: frontend/src/components/queue/__tests__/SlaSummaryCards.test.tsx
import { render, screen } from "@testing-library/react";
import { SlaSummaryCards } from "../SlaSummaryCards";

test("renders sla summary cards", () => {
  render(
    <SlaSummaryCards
      summary={{
        queue_key: "operator_queue",
        total_items: 10,
        first_action_breach_count: 2,
        resolution_breach_count: 1,
        approval_breach_count: 1,
        healthy_count: 6,
        breach_rate: 0.4,
      }}
    />
  );

  expect(screen.getByText("Total")).toBeInTheDocument();
  expect(screen.getByText("10")).toBeInTheDocument();
});
14) ĐIỂM MAP RẤT NGẮN KHI GẮN VÀO REPO THẬT
Backend
1. Apply assignment thật
Hiện accept(..., apply_assignment=True) mới chỉ đánh dấu recommendation là applied.
Khi map production thật, bạn nên nối thêm:
queue item assignee update
audit log event
notification event
optimistic concurrency nếu item version có đổi
Tức là trong QueueRecommendationEngineService.accept(...):
nếu apply_assignment=True
gọi QueueRepository.assign(item_id, recommended_assignee_id, actor_id, ...)
2. SLA policy source
Hiện SLA policy lookup theo:
queue_key
item_type
Production hơn nên cộng thêm:
severity override
priority bucket override
provider/project override nếu cần
3. Productivity rollup source thật
Worker hiện placeholder.
Map production:
assigned_count ← queue assign events
accepted_recommendation_count / rejected_recommendation_count ← recommendation table
first_action_count / resolved_count ← operator actions
approval_completed_count ← governance approval
execution_success_count ← execution attempts
conflict_count ← CAS/version conflict logs
sla_breach_count ← SLA evaluator materialization
4. Recommendation preview side effect
Hiện preview route tạo record thật trong DB.
Nếu muốn production sạch hơn, bạn có 2 mode:
preview_only → chỉ tính, không persist
persist_proposed → lưu DB
Bản patch này chọn kiểu persist luôn để:
đo acceptance behavior
đo recommendation history
dùng ngay cho operator review
15) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
add 3 models
register imports vào base
add 3 repositories
add schemas
add recommendation engine service
add SLA service
add productivity analytics service
add routes
wire router
add migration
add tests
wire worker schedule
Frontend
add types
add APIs
add AutoAssignPanel
add SlaSummaryCards
add ProductivityAnalyticsTable
patch queue panel
add tests
16) KẾT QUẢ SAU PATCH NÀY
Sau bản này queue của bạn sẽ tăng thêm 3 lớp rất mạnh:
A. Auto-Assign Recommendation Engine
Hệ bắt đầu biết:
item nào nên giao cho ai
vì sao nên giao
confidence / impact / sla risk là bao nhiêu
B. Queue SLA
Hệ bắt đầu biết:
queue có đang breach không
breach ở first action / resolution / approval
breach rate tổng thể là bao nhiêu
C. Productivity Analytics
Hệ bắt đầu biết:
operator nào xử lý nhiều
accept recommendation ra sao
resolve / execution success tốt ra sao
conflict / SLA breach của từng người
Tức là queue chuyển từ:
“có gợi ý thao tác”
sang:
“có gợi ý phân công + có chuẩn SLA + có số liệu năng suất”
PHASE 3 — RECOMMENDATION ACCEPTANCE BEHAVIOR + SPECIALTY/CAPACITY MODEL + AUTO-ASSIGN ACTION ENDPOINTS
Mục tiêu của bản này là nâng queue từ:
recommendation để người vận hành tự bấm
sang:
có hành vi học từ accept/reject
có mô hình specialty/capacity
có action endpoint để assign thật
có cooldown / suppression / max-active guardrails
vẫn giữ controlled execution, chưa nhảy sang autonomous hoàn toàn
Tôi viết theo format file-by-file paste-ready, bám production mapping ngắn gọn để dễ gắn vào repo thật.
1) BACKEND — MODELS
backend/app/models/queue_operator_capacity_profile.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueOperatorCapacityProfile(Base):
    __tablename__ = "queue_operator_capacity_profile"
    __table_args__ = (
        UniqueConstraint("queue_key", "operator_id", name="uq_queue_operator_capacity_profile"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    max_active_items: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    target_active_items: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)

    accepts_auto_assign: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    accepts_recommendations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
backend/app/models/queue_operator_specialty.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueOperatorSpecialty(Base):
    __tablename__ = "queue_operator_specialty"
    __table_args__ = (
        UniqueConstraint(
            "queue_key",
            "operator_id",
            "dimension_type",
            "dimension_value",
            name="uq_queue_operator_specialty_dim",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # provider | project | severity | item_type
    dimension_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    dimension_value: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    affinity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_resolution_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
backend/app/models/queue_assignment_action.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueAssignmentAction(Base):
    __tablename__ = "queue_assignment_action"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # manual_assign | accept_and_assign | auto_assign | reassign | suppress

    recommendation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    previous_assignee_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    new_assignee_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
2) BACKEND — REGISTER IMPORTS
backend/app/db/base.py
Thêm import:
from app.models.queue_operator_capacity_profile import QueueOperatorCapacityProfile
from app.models.queue_operator_specialty import QueueOperatorSpecialty
from app.models.queue_assignment_action import QueueAssignmentAction
3) BACKEND — REPOSITORIES
backend/app/repositories/queue_operator_capacity_profile_repository.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.queue_operator_capacity_profile import QueueOperatorCapacityProfile


class QueueOperatorCapacityProfileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, queue_key: str, operator_id: str) -> QueueOperatorCapacityProfile | None:
        stmt = select(QueueOperatorCapacityProfile).where(
            QueueOperatorCapacityProfile.queue_key == queue_key,
            QueueOperatorCapacityProfile.operator_id == operator_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        *,
        queue_key: str,
        operator_id: str,
        max_active_items: int,
        target_active_items: int,
        cooldown_seconds: int,
        accepts_auto_assign: bool,
        accepts_recommendations: bool,
    ) -> QueueOperatorCapacityProfile:
        obj = self.get(queue_key, operator_id)
        if obj is None:
            obj = QueueOperatorCapacityProfile(
                queue_key=queue_key,
                operator_id=operator_id,
                max_active_items=max_active_items,
                target_active_items=target_active_items,
                cooldown_seconds=cooldown_seconds,
                accepts_auto_assign=accepts_auto_assign,
                accepts_recommendations=accepts_recommendations,
            )
            self.db.add(obj)
            self.db.flush()
            return obj

        obj.max_active_items = max_active_items
        obj.target_active_items = target_active_items
        obj.cooldown_seconds = cooldown_seconds
        obj.accepts_auto_assign = accepts_auto_assign
        obj.accepts_recommendations = accepts_recommendations
        self.db.flush()
        return obj
backend/app/repositories/queue_operator_specialty_repository.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.queue_operator_specialty import QueueOperatorSpecialty


class QueueOperatorSpecialtyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_operator(self, queue_key: str, operator_id: str) -> list[QueueOperatorSpecialty]:
        stmt = select(QueueOperatorSpecialty).where(
            QueueOperatorSpecialty.queue_key == queue_key,
            QueueOperatorSpecialty.operator_id == operator_id,
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_dimension(
        self,
        *,
        queue_key: str,
        dimension_type: str,
        dimension_value: str,
    ) -> list[QueueOperatorSpecialty]:
        stmt = select(QueueOperatorSpecialty).where(
            QueueOperatorSpecialty.queue_key == queue_key,
            QueueOperatorSpecialty.dimension_type == dimension_type,
            QueueOperatorSpecialty.dimension_value == dimension_value,
        )
        return list(self.db.execute(stmt).scalars().all())

    def upsert(
        self,
        *,
        queue_key: str,
        operator_id: str,
        dimension_type: str,
        dimension_value: str,
        affinity_score: float,
        success_rate: float,
        avg_resolution_seconds: int,
        sample_size: int,
    ) -> QueueOperatorSpecialty:
        stmt = select(QueueOperatorSpecialty).where(
            QueueOperatorSpecialty.queue_key == queue_key,
            QueueOperatorSpecialty.operator_id == operator_id,
            QueueOperatorSpecialty.dimension_type == dimension_type,
            QueueOperatorSpecialty.dimension_value == dimension_value,
        )
        obj = self.db.execute(stmt).scalar_one_or_none()

        if obj is None:
            obj = QueueOperatorSpecialty(
                queue_key=queue_key,
                operator_id=operator_id,
                dimension_type=dimension_type,
                dimension_value=dimension_value,
                affinity_score=affinity_score,
                success_rate=success_rate,
                avg_resolution_seconds=avg_resolution_seconds,
                sample_size=sample_size,
            )
            self.db.add(obj)
            self.db.flush()
            return obj

        obj.affinity_score = affinity_score
        obj.success_rate = success_rate
        obj.avg_resolution_seconds = avg_resolution_seconds
        obj.sample_size = sample_size
        self.db.flush()
        return obj
backend/app/repositories/queue_assignment_action_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.queue_assignment_action import QueueAssignmentAction


class QueueAssignmentActionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        queue_key: str,
        item_id: str,
        item_version: int,
        action_type: str,
        actor_id: str,
        recommendation_id: str | None = None,
        previous_assignee_id: str | None = None,
        new_assignee_id: str | None = None,
        confidence_score: float | None = None,
        impact_score: float | None = None,
        reason: str | None = None,
        metadata_json: dict | None = None,
    ) -> QueueAssignmentAction:
        obj = QueueAssignmentAction(
            queue_key=queue_key,
            item_id=item_id,
            item_version=item_version,
            action_type=action_type,
            actor_id=actor_id,
            recommendation_id=recommendation_id,
            previous_assignee_id=previous_assignee_id,
            new_assignee_id=new_assignee_id,
            confidence_score=confidence_score,
            impact_score=impact_score,
            reason=reason,
            metadata_json=metadata_json,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_recent_for_item(self, queue_key: str, item_id: str, limit: int = 20) -> list[QueueAssignmentAction]:
        stmt = (
            select(QueueAssignmentAction)
            .where(
                QueueAssignmentAction.queue_key == queue_key,
                QueueAssignmentAction.item_id == item_id,
            )
            .order_by(desc(QueueAssignmentAction.created_at))
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
4) BACKEND — INTERFACES / REQUIRED MAP POINTS
Repo thật của bạn nên có các method sau. Nếu đã có tên khác thì map vào adapter/repository hiện tại.
backend/app/services/interfaces/queue_repository.py
from __future__ import annotations

from typing import Protocol, Any


class QueueRepositoryProtocol(Protocol):
    def get_item(self, queue_key: str, item_id: str) -> Any:
        ...

    def list_open_items_for_assignee(self, queue_key: str, assignee_id: str) -> list[Any]:
        ...

    def assign(
        self,
        *,
        queue_key: str,
        item_id: str,
        assignee_id: str,
        actor_id: str,
        expected_version: int | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> Any:
        ...
backend/app/services/interfaces/operator_activity_repository.py
from __future__ import annotations

from typing import Protocol


class OperatorActivityRepositoryProtocol(Protocol):
    def last_assignment_at(self, queue_key: str, operator_id: str):
        ...
5) BACKEND — SCHEMAS
backend/app/schemas/queue_auto_assign.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class QueueOperatorCapacityProfileIn(BaseModel):
    queue_key: str
    operator_id: str
    max_active_items: int = Field(default=10, ge=1)
    target_active_items: int = Field(default=6, ge=0)
    cooldown_seconds: int = Field(default=300, ge=0)
    accepts_auto_assign: bool = True
    accepts_recommendations: bool = True


class QueueOperatorCapacityProfileOut(BaseModel):
    queue_key: str
    operator_id: str
    max_active_items: int
    target_active_items: int
    cooldown_seconds: int
    accepts_auto_assign: bool
    accepts_recommendations: bool

    class Config:
        from_attributes = True


class QueueOperatorSpecialtyOut(BaseModel):
    queue_key: str
    operator_id: str
    dimension_type: str
    dimension_value: str
    affinity_score: float
    success_rate: float
    avg_resolution_seconds: int
    sample_size: int

    class Config:
        from_attributes = True


class RecommendationAcceptanceSummary(BaseModel):
    operator_id: str
    accepted_count: int
    rejected_count: int
    acceptance_rate: float
    last_30d_accepted_count: int
    last_30d_rejected_count: int
    last_30d_acceptance_rate: float


class QueueRecommendationCandidateOut(BaseModel):
    operator_id: str
    score: float
    confidence_score: float
    impact_score: float
    load_score: float
    specialty_score: float
    acceptance_behavior_score: float
    cooldown_blocked: bool
    capacity_blocked: bool
    reasons: list[str]


class QueueAutoAssignPreviewOut(BaseModel):
    queue_key: str
    item_id: str
    item_version: int
    top_candidates: list[QueueRecommendationCandidateOut]
    selected_candidate: QueueRecommendationCandidateOut | None
    guardrails_applied: list[str]


class QueueAutoAssignExecuteIn(BaseModel):
    queue_key: str
    item_id: str
    expected_version: int | None = None
    actor_id: str
    mode: str = "best_effort"
    persist_recommendation: bool = True
    suppress_seconds_on_no_candidate: int = 300


class QueueAutoAssignExecuteOut(BaseModel):
    queue_key: str
    item_id: str
    assigned: bool
    assignee_id: str | None = None
    recommendation_id: str | None = None
    action_id: str | None = None
    reason: str | None = None
    guardrails_applied: list[str] = []
    executed_at: datetime
6) BACKEND — ACCEPTANCE BEHAVIOR SERVICE
backend/app/services/queue_recommendation_acceptance_behavior_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.queue_recommendation import QueueRecommendation


@dataclass
class AcceptanceBehaviorScore:
    operator_id: str
    accepted_count: int
    rejected_count: int
    acceptance_rate: float
    last_30d_accepted_count: int
    last_30d_rejected_count: int
    last_30d_acceptance_rate: float
    score: float


class QueueRecommendationAcceptanceBehaviorService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summarize(self, *, queue_key: str, operator_id: str) -> AcceptanceBehaviorScore:
        now = datetime.now(timezone.utc)
        last_30d = now - timedelta(days=30)

        total_stmt = (
            select(
                func.count().filter(QueueRecommendation.status == "accepted"),
                func.count().filter(QueueRecommendation.status == "rejected"),
            )
            .where(
                QueueRecommendation.queue_key == queue_key,
                QueueRecommendation.recommended_assignee_id == operator_id,
            )
        )
        accepted_count, rejected_count = self.db.execute(total_stmt).one()

        recent_stmt = (
            select(
                func.count().filter(QueueRecommendation.status == "accepted"),
                func.count().filter(QueueRecommendation.status == "rejected"),
            )
            .where(
                QueueRecommendation.queue_key == queue_key,
                QueueRecommendation.recommended_assignee_id == operator_id,
                QueueRecommendation.created_at >= last_30d,
            )
        )
        last_30d_accepted_count, last_30d_rejected_count = self.db.execute(recent_stmt).one()

        accepted_count = int(accepted_count or 0)
        rejected_count = int(rejected_count or 0)
        last_30d_accepted_count = int(last_30d_accepted_count or 0)
        last_30d_rejected_count = int(last_30d_rejected_count or 0)

        total = accepted_count + rejected_count
        recent_total = last_30d_accepted_count + last_30d_rejected_count

        acceptance_rate = accepted_count / total if total else 0.5
        last_30d_acceptance_rate = last_30d_accepted_count / recent_total if recent_total else acceptance_rate

        # nhẹ nhàng, không để history thống trị toàn bộ score
        score = (0.4 * acceptance_rate) + (0.6 * last_30d_acceptance_rate)

        return AcceptanceBehaviorScore(
            operator_id=operator_id,
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            acceptance_rate=acceptance_rate,
            last_30d_accepted_count=last_30d_accepted_count,
            last_30d_rejected_count=last_30d_rejected_count,
            last_30d_acceptance_rate=last_30d_acceptance_rate,
            score=score,
        )
7) BACKEND — SPECIALTY/CAPACITY SCORING SERVICE
backend/app/services/queue_operator_fit_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.queue_operator_capacity_profile_repository import QueueOperatorCapacityProfileRepository
from app.repositories.queue_operator_specialty_repository import QueueOperatorSpecialtyRepository
from app.services.interfaces.operator_activity_repository import OperatorActivityRepositoryProtocol
from app.services.interfaces.queue_repository import QueueRepositoryProtocol
from app.services.queue_recommendation_acceptance_behavior_service import (
    QueueRecommendationAcceptanceBehaviorService,
)


@dataclass
class OperatorFitResult:
    operator_id: str
    score: float
    confidence_score: float
    impact_score: float
    load_score: float
    specialty_score: float
    acceptance_behavior_score: float
    cooldown_blocked: bool
    capacity_blocked: bool
    reasons: list[str]


class QueueOperatorFitService:
    def __init__(
        self,
        db: Session,
        *,
        queue_repository: QueueRepositoryProtocol,
        operator_activity_repository: OperatorActivityRepositoryProtocol,
    ) -> None:
        self.db = db
        self.queue_repository = queue_repository
        self.operator_activity_repository = operator_activity_repository
        self.capacity_repo = QueueOperatorCapacityProfileRepository(db)
        self.specialty_repo = QueueOperatorSpecialtyRepository(db)
        self.behavior_service = QueueRecommendationAcceptanceBehaviorService(db)

    def score_operator(
        self,
        *,
        queue_key: str,
        item,
        operator_id: str,
    ) -> OperatorFitResult:
        reasons: list[str] = []

        profile = self.capacity_repo.get(queue_key, operator_id)
        active_items = self.queue_repository.list_open_items_for_assignee(queue_key, operator_id)
        active_count = len(active_items)

        cooldown_blocked = False
        capacity_blocked = False

        if profile:
            if active_count >= profile.max_active_items:
                capacity_blocked = True
                reasons.append(f"max_active_items_reached:{profile.max_active_items}")

            last_assignment_at = self.operator_activity_repository.last_assignment_at(queue_key, operator_id)
            if last_assignment_at is not None:
                elapsed = (datetime.now(timezone.utc) - last_assignment_at).total_seconds()
                if elapsed < profile.cooldown_seconds:
                    cooldown_blocked = True
                    reasons.append(f"cooldown_active:{profile.cooldown_seconds}")

            if active_count <= profile.target_active_items:
                load_score = 1.0
            else:
                overflow = max(0, active_count - profile.target_active_items)
                spread = max(1, profile.max_active_items - profile.target_active_items)
                load_score = max(0.0, 1.0 - (overflow / spread))
        else:
            load_score = max(0.0, 1.0 - min(active_count / 10.0, 1.0))
            reasons.append("no_capacity_profile_defaulted")

        specialty_score = self._compute_specialty_score(queue_key=queue_key, item=item, operator_id=operator_id)
        behavior = self.behavior_service.summarize(queue_key=queue_key, operator_id=operator_id)
        acceptance_behavior_score = behavior.score

        # tổng hợp score
        base_score = (
            0.35 * load_score
            + 0.40 * specialty_score
            + 0.25 * acceptance_behavior_score
        )

        if cooldown_blocked:
            base_score *= 0.35
        if capacity_blocked:
            base_score = 0.0

        confidence_score = min(1.0, 0.5 + (0.5 * specialty_score))
        impact_score = min(1.0, 0.5 + (0.3 * specialty_score) + (0.2 * load_score))

        return OperatorFitResult(
            operator_id=operator_id,
            score=round(base_score, 4),
            confidence_score=round(confidence_score, 4),
            impact_score=round(impact_score, 4),
            load_score=round(load_score, 4),
            specialty_score=round(specialty_score, 4),
            acceptance_behavior_score=round(acceptance_behavior_score, 4),
            cooldown_blocked=cooldown_blocked,
            capacity_blocked=capacity_blocked,
            reasons=reasons,
        )

    def _compute_specialty_score(self, *, queue_key: str, item, operator_id: str) -> float:
        dimensions: list[tuple[str, str]] = []

        if getattr(item, "provider", None):
            dimensions.append(("provider", str(item.provider)))
        if getattr(item, "project_id", None):
            dimensions.append(("project", str(item.project_id)))
        if getattr(item, "severity", None):
            dimensions.append(("severity", str(item.severity)))
        if getattr(item, "item_type", None):
            dimensions.append(("item_type", str(item.item_type)))

        scores: list[float] = []
        operator_specs = self.specialty_repo.list_for_operator(queue_key, operator_id)

        spec_map = {(s.dimension_type, s.dimension_value): s for s in operator_specs}
        for dim_type, dim_value in dimensions:
            spec = spec_map.get((dim_type, dim_value))
            if spec is None:
                continue

            affinity_component = max(0.0, min(spec.affinity_score, 1.0))
            success_component = max(0.0, min(spec.success_rate, 1.0))
            sample_component = min(spec.sample_size / 20.0, 1.0)

            scores.append((0.45 * affinity_component) + (0.40 * success_component) + (0.15 * sample_component))

        if not scores:
            return 0.5

        return sum(scores) / len(scores)
8) BACKEND — AUTO-ASSIGN SERVICE
backend/app/services/queue_auto_assign_service.py
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.queue_assignment_action_repository import QueueAssignmentActionRepository
from app.repositories.queue_recommendation_repository import QueueRecommendationRepository
from app.services.interfaces.queue_repository import QueueRepositoryProtocol
from app.services.queue_operator_fit_service import QueueOperatorFitService
from app.schemas.queue_auto_assign import (
    QueueAutoAssignExecuteOut,
    QueueAutoAssignPreviewOut,
    QueueRecommendationCandidateOut,
)


class QueueAutoAssignService:
    def __init__(
        self,
        db: Session,
        *,
        queue_repository: QueueRepositoryProtocol,
        operator_activity_repository,
        candidate_operator_ids_provider,
        audit_log_service=None,
        notification_service=None,
    ) -> None:
        self.db = db
        self.queue_repository = queue_repository
        self.operator_activity_repository = operator_activity_repository
        self.candidate_operator_ids_provider = candidate_operator_ids_provider
        self.audit_log_service = audit_log_service
        self.notification_service = notification_service

        self.fit_service = QueueOperatorFitService(
            db,
            queue_repository=queue_repository,
            operator_activity_repository=operator_activity_repository,
        )
        self.assignment_action_repo = QueueAssignmentActionRepository(db)
        self.recommendation_repo = QueueRecommendationRepository(db)

    def preview(self, *, queue_key: str, item_id: str) -> QueueAutoAssignPreviewOut:
        item = self.queue_repository.get_item(queue_key, item_id)
        if item is None:
            raise ValueError("queue item not found")

        candidates = self._rank_candidates(queue_key=queue_key, item=item)

        selected = candidates[0] if candidates else None
        guardrails = self._build_guardrails(candidates)

        return QueueAutoAssignPreviewOut(
            queue_key=queue_key,
            item_id=item_id,
            item_version=int(getattr(item, "version", 1)),
            top_candidates=[QueueRecommendationCandidateOut(**asdict(c)) for c in candidates[:5]],
            selected_candidate=QueueRecommendationCandidateOut(**asdict(selected)) if selected else None,
            guardrails_applied=guardrails,
        )

    def execute(
        self,
        *,
        queue_key: str,
        item_id: str,
        actor_id: str,
        expected_version: int | None = None,
        persist_recommendation: bool = True,
        suppress_seconds_on_no_candidate: int = 300,
    ) -> QueueAutoAssignExecuteOut:
        item = self.queue_repository.get_item(queue_key, item_id)
        if item is None:
            raise ValueError("queue item not found")

        candidates = self._rank_candidates(queue_key=queue_key, item=item)
        guardrails = self._build_guardrails(candidates)

        selected = candidates[0] if candidates else None
        if selected is None or selected.capacity_blocked or selected.score <= 0:
            # optional: create suppress action
            action = self.assignment_action_repo.create(
                queue_key=queue_key,
                item_id=item_id,
                item_version=int(getattr(item, "version", 1)),
                action_type="suppress",
                actor_id=actor_id,
                previous_assignee_id=getattr(item, "assignee_id", None),
                new_assignee_id=None,
                confidence_score=None,
                impact_score=None,
                reason="no_eligible_candidate",
                metadata_json={"suppress_seconds": suppress_seconds_on_no_candidate},
            )
            self.db.commit()
            return QueueAutoAssignExecuteOut(
                queue_key=queue_key,
                item_id=item_id,
                assigned=False,
                assignee_id=None,
                recommendation_id=None,
                action_id=str(action.id),
                reason="no_eligible_candidate",
                guardrails_applied=guardrails,
                executed_at=datetime.now(timezone.utc),
            )

        recommendation = None
        if persist_recommendation:
            recommendation = self.recommendation_repo.create(
                queue_key=queue_key,
                item_id=item_id,
                recommended_assignee_id=selected.operator_id,
                confidence_score=selected.confidence_score,
                impact_score=selected.impact_score,
                status="accepted",
                reason="auto_assign_selected_best_candidate",
                metadata_json={
                    "load_score": selected.load_score,
                    "specialty_score": selected.specialty_score,
                    "acceptance_behavior_score": selected.acceptance_behavior_score,
                    "guardrails_applied": guardrails,
                    "auto_assign": True,
                },
            )

        updated_item = self.queue_repository.assign(
            queue_key=queue_key,
            item_id=item_id,
            assignee_id=selected.operator_id,
            actor_id=actor_id,
            expected_version=expected_version,
            reason="auto_assign",
            metadata={
                "recommendation_id": str(recommendation.id) if recommendation else None,
                "guardrails_applied": guardrails,
            },
        )

        action = self.assignment_action_repo.create(
            queue_key=queue_key,
            item_id=item_id,
            item_version=int(getattr(updated_item, "version", getattr(item, "version", 1))),
            action_type="auto_assign",
            actor_id=actor_id,
            recommendation_id=str(recommendation.id) if recommendation else None,
            previous_assignee_id=getattr(item, "assignee_id", None),
            new_assignee_id=selected.operator_id,
            confidence_score=selected.confidence_score,
            impact_score=selected.impact_score,
            reason="auto_assign_selected_best_candidate",
            metadata_json={
                "load_score": selected.load_score,
                "specialty_score": selected.specialty_score,
                "acceptance_behavior_score": selected.acceptance_behavior_score,
            },
        )

        if self.audit_log_service:
            self.audit_log_service.log(
                event_type="queue.auto_assign.executed",
                actor_id=actor_id,
                entity_type="queue_item",
                entity_id=item_id,
                payload={
                    "queue_key": queue_key,
                    "assignee_id": selected.operator_id,
                    "recommendation_id": str(recommendation.id) if recommendation else None,
                },
            )

        if self.notification_service:
            self.notification_service.emit(
                event_type="queue.assignment.created",
                payload={
                    "queue_key": queue_key,
                    "item_id": item_id,
                    "assignee_id": selected.operator_id,
                    "actor_id": actor_id,
                },
            )

        self.db.commit()

        return QueueAutoAssignExecuteOut(
            queue_key=queue_key,
            item_id=item_id,
            assigned=True,
            assignee_id=selected.operator_id,
            recommendation_id=str(recommendation.id) if recommendation else None,
            action_id=str(action.id),
            reason="assigned",
            guardrails_applied=guardrails,
            executed_at=datetime.now(timezone.utc),
        )

    def _rank_candidates(self, *, queue_key: str, item) -> list:
        operator_ids = self.candidate_operator_ids_provider(queue_key=queue_key, item=item)
        results = [
            self.fit_service.score_operator(queue_key=queue_key, item=item, operator_id=operator_id)
            for operator_id in operator_ids
        ]
        results.sort(key=lambda x: (x.capacity_blocked, x.cooldown_blocked, -x.score))
        return results

    def _build_guardrails(self, candidates: list) -> list[str]:
        out: list[str] = []
        if any(c.cooldown_blocked for c in candidates):
            out.append("cooldown_guardrail")
        if any(c.capacity_blocked for c in candidates):
            out.append("max_active_guardrail")
        return out
9) BACKEND — PATCH ACCEPT(...) CỦA RECOMMENDATION ENGINE
Đây là điểm map production rất quan trọng theo đúng note của bạn.
backend/app/services/queue_recommendation_engine_service.py
Trong method accept(...), patch logic chính như sau:
def accept(
    self,
    *,
    recommendation_id: str,
    actor_id: str,
    apply_assignment: bool = False,
    expected_item_version: int | None = None,
):
    recommendation = self.recommendation_repo.get(recommendation_id)
    if recommendation is None:
        raise ValueError("recommendation not found")

    if recommendation.status not in {"proposed"}:
        return recommendation

    recommendation.status = "accepted"
    recommendation.accepted_by = actor_id
    self.db.flush()

    if apply_assignment:
        item = self.queue_repository.get_item(recommendation.queue_key, recommendation.item_id)
        previous_assignee_id = getattr(item, "assignee_id", None)

        updated_item = self.queue_repository.assign(
            queue_key=recommendation.queue_key,
            item_id=recommendation.item_id,
            assignee_id=recommendation.recommended_assignee_id,
            actor_id=actor_id,
            expected_version=expected_item_version,
            reason="accepted_recommendation",
            metadata={"recommendation_id": recommendation_id},
        )

        self.assignment_action_repo.create(
            queue_key=recommendation.queue_key,
            item_id=recommendation.item_id,
            item_version=int(getattr(updated_item, "version", getattr(item, "version", 1))),
            action_type="accept_and_assign",
            actor_id=actor_id,
            recommendation_id=recommendation_id,
            previous_assignee_id=previous_assignee_id,
            new_assignee_id=recommendation.recommended_assignee_id,
            confidence_score=recommendation.confidence_score,
            impact_score=recommendation.impact_score,
            reason="accepted_recommendation",
            metadata_json={"expected_item_version": expected_item_version},
        )

        if self.audit_log_service:
            self.audit_log_service.log(
                event_type="queue.recommendation.accepted_and_applied",
                actor_id=actor_id,
                entity_type="queue_item",
                entity_id=recommendation.item_id,
                payload={
                    "queue_key": recommendation.queue_key,
                    "recommendation_id": recommendation_id,
                    "assignee_id": recommendation.recommended_assignee_id,
                },
            )

        if self.notification_service:
            self.notification_service.emit(
                event_type="queue.assignment.created",
                payload={
                    "queue_key": recommendation.queue_key,
                    "item_id": recommendation.item_id,
                    "assignee_id": recommendation.recommended_assignee_id,
                    "actor_id": actor_id,
                },
            )

    self.db.commit()
    return recommendation
10) BACKEND — ROUTES
backend/app/api/routes/queue_auto_assign.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.queue_auto_assign import (
    QueueAutoAssignExecuteIn,
    QueueAutoAssignExecuteOut,
    QueueAutoAssignPreviewOut,
    QueueOperatorCapacityProfileIn,
    QueueOperatorCapacityProfileOut,
)
from app.repositories.queue_operator_capacity_profile_repository import QueueOperatorCapacityProfileRepository
from app.services.queue_auto_assign_service import QueueAutoAssignService

router = APIRouter(prefix="/queue/auto-assign", tags=["queue-auto-assign"])


def get_queue_repository():
    from app.dependencies.queue_runtime import get_queue_repository
    return get_queue_repository()


def get_operator_activity_repository():
    from app.dependencies.queue_runtime import get_operator_activity_repository
    return get_operator_activity_repository()


def candidate_operator_ids_provider(queue_key: str, item):
    from app.dependencies.queue_runtime import get_candidate_operator_ids_provider
    provider = get_candidate_operator_ids_provider()
    return provider(queue_key=queue_key, item=item)


@router.get("/preview", response_model=QueueAutoAssignPreviewOut)
def preview_auto_assign(
    queue_key: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    service = QueueAutoAssignService(
        db,
        queue_repository=get_queue_repository(),
        operator_activity_repository=get_operator_activity_repository(),
        candidate_operator_ids_provider=candidate_operator_ids_provider,
    )
    try:
        return service.preview(queue_key=queue_key, item_id=item_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/execute", response_model=QueueAutoAssignExecuteOut)
def execute_auto_assign(
    payload: QueueAutoAssignExecuteIn,
    db: Session = Depends(get_db),
):
    service = QueueAutoAssignService(
        db,
        queue_repository=get_queue_repository(),
        operator_activity_repository=get_operator_activity_repository(),
        candidate_operator_ids_provider=candidate_operator_ids_provider,
    )
    try:
        return service.execute(
            queue_key=payload.queue_key,
            item_id=payload.item_id,
            actor_id=payload.actor_id,
            expected_version=payload.expected_version,
            persist_recommendation=payload.persist_recommendation,
            suppress_seconds_on_no_candidate=payload.suppress_seconds_on_no_candidate,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        message = str(e).lower()
        if "version" in message or "conflict" in message:
            raise HTTPException(status_code=409, detail=str(e))
        raise


@router.post("/capacity-profile", response_model=QueueOperatorCapacityProfileOut)
def upsert_capacity_profile(
    payload: QueueOperatorCapacityProfileIn,
    db: Session = Depends(get_db),
):
    repo = QueueOperatorCapacityProfileRepository(db)
    obj = repo.upsert(
        queue_key=payload.queue_key,
        operator_id=payload.operator_id,
        max_active_items=payload.max_active_items,
        target_active_items=payload.target_active_items,
        cooldown_seconds=payload.cooldown_seconds,
        accepts_auto_assign=payload.accepts_auto_assign,
        accepts_recommendations=payload.accepts_recommendations,
    )
    db.commit()
    db.refresh(obj)
    return obj
backend/app/api/routes/queue_recommendations.py
Patch endpoint accept để nhận expected_item_version:
class RecommendationAcceptIn(BaseModel):
    actor_id: str
    apply_assignment: bool = False
    expected_item_version: int | None = None
Và ở route:
service.accept(
    recommendation_id=recommendation_id,
    actor_id=payload.actor_id,
    apply_assignment=payload.apply_assignment,
    expected_item_version=payload.expected_item_version,
)
11) BACKEND — ROUTER WIRING
backend/app/api/api_v1/api.py
from app.api.routes import queue_auto_assign
và:
api_router.include_router(queue_auto_assign.router)
12) BACKEND — MIGRATION
backend/alembic/versions/phase3_auto_assign_acceptance_behavior.py
"""phase3 auto assign acceptance behavior

Revision ID: 003_phase3_auto_assign
Revises: 002_phase3_queue_sla_productivity
Create Date: 2026-04-12 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "003_phase3_auto_assign"
down_revision = "002_phase3_queue_sla_productivity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "queue_operator_capacity_profile",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("operator_id", sa.String(length=100), nullable=False),
        sa.Column("max_active_items", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("target_active_items", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("accepts_auto_assign", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("accepts_recommendations", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("queue_key", "operator_id", name="uq_queue_operator_capacity_profile"),
    )
    op.create_index("ix_queue_operator_capacity_profile_queue_key", "queue_operator_capacity_profile", ["queue_key"])
    op.create_index("ix_queue_operator_capacity_profile_operator_id", "queue_operator_capacity_profile", ["operator_id"])

    op.create_table(
        "queue_operator_specialty",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("operator_id", sa.String(length=100), nullable=False),
        sa.Column("dimension_type", sa.String(length=50), nullable=False),
        sa.Column("dimension_value", sa.String(length=120), nullable=False),
        sa.Column("affinity_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_resolution_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "queue_key",
            "operator_id",
            "dimension_type",
            "dimension_value",
            name="uq_queue_operator_specialty_dim",
        ),
    )
    op.create_index("ix_queue_operator_specialty_queue_key", "queue_operator_specialty", ["queue_key"])
    op.create_index("ix_queue_operator_specialty_operator_id", "queue_operator_specialty", ["operator_id"])
    op.create_index("ix_queue_operator_specialty_dimension_type", "queue_operator_specialty", ["dimension_type"])
    op.create_index("ix_queue_operator_specialty_dimension_value", "queue_operator_specialty", ["dimension_value"])

    op.create_table(
        "queue_assignment_action",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("item_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("recommendation_id", sa.String(length=100), nullable=True),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("previous_assignee_id", sa.String(length=100), nullable=True),
        sa.Column("new_assignee_id", sa.String(length=100), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("impact_score", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_queue_assignment_action_queue_key", "queue_assignment_action", ["queue_key"])
    op.create_index("ix_queue_assignment_action_item_id", "queue_assignment_action", ["item_id"])
    op.create_index("ix_queue_assignment_action_action_type", "queue_assignment_action", ["action_type"])
    op.create_index("ix_queue_assignment_action_recommendation_id", "queue_assignment_action", ["recommendation_id"])
    op.create_index("ix_queue_assignment_action_actor_id", "queue_assignment_action", ["actor_id"])


def downgrade():
    op.drop_index("ix_queue_assignment_action_actor_id", table_name="queue_assignment_action")
    op.drop_index("ix_queue_assignment_action_recommendation_id", table_name="queue_assignment_action")
    op.drop_index("ix_queue_assignment_action_action_type", table_name="queue_assignment_action")
    op.drop_index("ix_queue_assignment_action_item_id", table_name="queue_assignment_action")
    op.drop_index("ix_queue_assignment_action_queue_key", table_name="queue_assignment_action")
    op.drop_table("queue_assignment_action")

    op.drop_index("ix_queue_operator_specialty_dimension_value", table_name="queue_operator_specialty")
    op.drop_index("ix_queue_operator_specialty_dimension_type", table_name="queue_operator_specialty")
    op.drop_index("ix_queue_operator_specialty_operator_id", table_name="queue_operator_specialty")
    op.drop_index("ix_queue_operator_specialty_queue_key", table_name="queue_operator_specialty")
    op.drop_table("queue_operator_specialty")

    op.drop_index("ix_queue_operator_capacity_profile_operator_id", table_name="queue_operator_capacity_profile")
    op.drop_index("ix_queue_operator_capacity_profile_queue_key", table_name="queue_operator_capacity_profile")
    op.drop_table("queue_operator_capacity_profile")
13) BACKEND — TESTS
backend/tests/services/test_queue_recommendation_acceptance_behavior_service.py
from app.services.queue_recommendation_acceptance_behavior_service import (
    QueueRecommendationAcceptanceBehaviorService,
)


def test_acceptance_behavior_summary(db_session, seed_queue_recommendations):
    service = QueueRecommendationAcceptanceBehaviorService(db_session)

    summary = service.summarize(queue_key="render_ops", operator_id="op_a")

    assert summary.operator_id == "op_a"
    assert 0.0 <= summary.acceptance_rate <= 1.0
    assert 0.0 <= summary.last_30d_acceptance_rate <= 1.0
    assert 0.0 <= summary.score <= 1.0
backend/tests/services/test_queue_operator_fit_service.py
from datetime import datetime, timedelta, timezone

from app.services.queue_operator_fit_service import QueueOperatorFitService


class FakeQueueRepository:
    def __init__(self, item, assignee_open_counts):
        self.item = item
        self.assignee_open_counts = assignee_open_counts

    def get_item(self, queue_key, item_id):
        return self.item

    def list_open_items_for_assignee(self, queue_key, assignee_id):
        return [object()] * self.assignee_open_counts.get(assignee_id, 0)

    def assign(self, **kwargs):
        raise NotImplementedError


class FakeOperatorActivityRepository:
    def __init__(self, last_assignment_map):
        self.last_assignment_map = last_assignment_map

    def last_assignment_at(self, queue_key, operator_id):
        return self.last_assignment_map.get(operator_id)


class Item:
    id = "item_1"
    version = 3
    provider = "veo"
    project_id = "proj_1"
    severity = "high"
    item_type = "render_job"
    assignee_id = None


def test_fit_service_blocks_when_capacity_reached(db_session, seed_capacity_profiles):
    queue_repo = FakeQueueRepository(Item(), {"op_a": 10})
    activity_repo = FakeOperatorActivityRepository({"op_a": datetime.now(timezone.utc) - timedelta(hours=2)})

    service = QueueOperatorFitService(
        db_session,
        queue_repository=queue_repo,
        operator_activity_repository=activity_repo,
    )

    result = service.score_operator(queue_key="render_ops", item=Item(), operator_id="op_a")
    assert result.capacity_blocked is True
    assert result.score == 0.0
backend/tests/services/test_queue_auto_assign_service.py
from datetime import datetime, timedelta, timezone

from app.repositories.queue_operator_capacity_profile_repository import QueueOperatorCapacityProfileRepository
from app.services.queue_auto_assign_service import QueueAutoAssignService


class FakeItem:
    id = "item_1"
    version = 5
    provider = "veo"
    project_id = "proj_1"
    severity = "high"
    item_type = "render_job"
    assignee_id = None


class FakeQueueRepository:
    def __init__(self):
        self.item = FakeItem()
        self.assigned_to = None

    def get_item(self, queue_key, item_id):
        return self.item

    def list_open_items_for_assignee(self, queue_key, assignee_id):
        if assignee_id == "op_a":
            return [object()] * 2
        if assignee_id == "op_b":
            return [object()] * 9
        return []

    def assign(self, *, queue_key, item_id, assignee_id, actor_id, expected_version=None, reason=None, metadata=None):
        if expected_version is not None and expected_version != self.item.version:
            raise RuntimeError("version conflict")
        self.item.assignee_id = assignee_id
        self.item.version += 1
        self.assigned_to = assignee_id
        return self.item


class FakeOperatorActivityRepository:
    def last_assignment_at(self, queue_key, operator_id):
        if operator_id == "op_a":
            return datetime.now(timezone.utc) - timedelta(hours=1)
        return datetime.now(timezone.utc) - timedelta(seconds=30)


def test_auto_assign_selects_best_candidate(db_session):
    queue_repo = FakeQueueRepository()
    activity_repo = FakeOperatorActivityRepository()

    cap_repo = QueueOperatorCapacityProfileRepository(db_session)
    cap_repo.upsert(
        queue_key="render_ops",
        operator_id="op_a",
        max_active_items=10,
        target_active_items=6,
        cooldown_seconds=60,
        accepts_auto_assign=True,
        accepts_recommendations=True,
    )
    cap_repo.upsert(
        queue_key="render_ops",
        operator_id="op_b",
        max_active_items=10,
        target_active_items=6,
        cooldown_seconds=300,
        accepts_auto_assign=True,
        accepts_recommendations=True,
    )
    db_session.commit()

    service = QueueAutoAssignService(
        db_session,
        queue_repository=queue_repo,
        operator_activity_repository=activity_repo,
        candidate_operator_ids_provider=lambda queue_key, item: ["op_a", "op_b"],
    )

    result = service.execute(
        queue_key="render_ops",
        item_id="item_1",
        actor_id="system:auto_assign",
        expected_version=5,
    )

    assert result.assigned is True
    assert result.assignee_id == "op_a"
backend/tests/api/test_queue_auto_assign_routes.py
def test_preview_auto_assign(client, db_session, seed_queue_runtime_deps):
    response = client.get("/api/v1/queue/auto-assign/preview", params={"queue_key": "render_ops", "item_id": "item_1"})
    assert response.status_code == 200
    body = response.json()
    assert body["queue_key"] == "render_ops"
    assert body["item_id"] == "item_1"
    assert "top_candidates" in body


def test_execute_auto_assign_conflict(client, db_session, seed_queue_runtime_deps):
    response = client.post(
        "/api/v1/queue/auto-assign/execute",
        json={
            "queue_key": "render_ops",
            "item_id": "item_1",
            "actor_id": "system:auto_assign",
            "expected_version": 999,
        },
    )
    assert response.status_code == 409
14) BACKEND — WORKER SCHEDULE / ROLLUP JOB
Sau bản này, nên có worker để refresh specialty profile từ dữ liệu thật.
backend/app/workers/queue_specialty_rollup_worker.py
from __future__ import annotations

from celery import shared_task
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.queue_operator_specialty_repository import QueueOperatorSpecialtyRepository


@shared_task(name="queue.refresh_operator_specialty_rollups")
def refresh_operator_specialty_rollups() -> dict:
    db: Session = SessionLocal()
    try:
        repo = QueueOperatorSpecialtyRepository(db)

        # TODO: map production thật từ operator actions / execution success / resolve history
        # Hiện placeholder minimal để nối pipeline.
        sample_profiles = [
            {
                "queue_key": "render_ops",
                "operator_id": "op_a",
                "dimension_type": "provider",
                "dimension_value": "veo",
                "affinity_score": 0.9,
                "success_rate": 0.92,
                "avg_resolution_seconds": 900,
                "sample_size": 18,
            },
            {
                "queue_key": "render_ops",
                "operator_id": "op_b",
                "dimension_type": "provider",
                "dimension_value": "runway",
                "affinity_score": 0.85,
                "success_rate": 0.88,
                "avg_resolution_seconds": 1100,
                "sample_size": 14,
            },
        ]

        for p in sample_profiles:
            repo.upsert(**p)

        db.commit()
        return {"ok": True, "profiles_upserted": len(sample_profiles)}
    finally:
        db.close()
15) FRONTEND — TYPES
frontend/src/types/queueAutoAssign.ts
export type QueueRecommendationCandidate = {
  operator_id: string;
  score: number;
  confidence_score: number;
  impact_score: number;
  load_score: number;
  specialty_score: number;
  acceptance_behavior_score: number;
  cooldown_blocked: boolean;
  capacity_blocked: boolean;
  reasons: string[];
};

export type QueueAutoAssignPreview = {
  queue_key: string;
  item_id: string;
  item_version: number;
  top_candidates: QueueRecommendationCandidate[];
  selected_candidate: QueueRecommendationCandidate | null;
  guardrails_applied: string[];
};

export type QueueAutoAssignExecuteRequest = {
  queue_key: string;
  item_id: string;
  expected_version?: number | null;
  actor_id: string;
  mode?: string;
  persist_recommendation?: boolean;
  suppress_seconds_on_no_candidate?: number;
};

export type QueueAutoAssignExecuteResponse = {
  queue_key: string;
  item_id: string;
  assigned: boolean;
  assignee_id: string | null;
  recommendation_id: string | null;
  action_id: string | null;
  reason: string | null;
  guardrails_applied: string[];
  executed_at: string;
};

export type QueueOperatorCapacityProfile = {
  queue_key: string;
  operator_id: string;
  max_active_items: number;
  target_active_items: number;
  cooldown_seconds: number;
  accepts_auto_assign: boolean;
  accepts_recommendations: boolean;
};
16) FRONTEND — API
frontend/src/api/queueAutoAssign.ts
import { apiClient } from "./client";
import {
  QueueAutoAssignExecuteRequest,
  QueueAutoAssignExecuteResponse,
  QueueAutoAssignPreview,
  QueueOperatorCapacityProfile,
} from "../types/queueAutoAssign";

export async function fetchAutoAssignPreview(queueKey: string, itemId: string) {
  const res = await apiClient.get<QueueAutoAssignPreview>("/queue/auto-assign/preview", {
    params: { queue_key: queueKey, item_id: itemId },
  });
  return res.data;
}

export async function executeAutoAssign(payload: QueueAutoAssignExecuteRequest) {
  const res = await apiClient.post<QueueAutoAssignExecuteResponse>("/queue/auto-assign/execute", payload);
  return res.data;
}

export async function upsertCapacityProfile(payload: QueueOperatorCapacityProfile) {
  const res = await apiClient.post<QueueOperatorCapacityProfile>("/queue/auto-assign/capacity-profile", payload);
  return res.data;
}
17) FRONTEND — AUTO ASSIGN PANEL
frontend/src/components/queue/AutoAssignActionPanel.tsx
import React, { useEffect, useState } from "react";
import { executeAutoAssign, fetchAutoAssignPreview } from "../../api/queueAutoAssign";
import { QueueAutoAssignPreview } from "../../types/queueAutoAssign";

type Props = {
  queueKey: string;
  itemId: string;
  itemVersion?: number;
  actorId: string;
  onToast: (input: { title: string; description?: string; variant?: "default" | "destructive" }) => void;
  onAssigned?: () => void;
};

export function AutoAssignActionPanel({
  queueKey,
  itemId,
  itemVersion,
  actorId,
  onToast,
  onAssigned,
}: Props) {
  const [preview, setPreview] = useState<QueueAutoAssignPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);

  async function loadPreview() {
    setLoading(true);
    try {
      const data = await fetchAutoAssignPreview(queueKey, itemId);
      setPreview(data);
    } catch (err: any) {
      onToast({
        title: "Không tải được preview auto-assign",
        description: err?.response?.data?.detail || "Unknown error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }

  async function runAssign() {
    setExecuting(true);
    try {
      const res = await executeAutoAssign({
        queue_key: queueKey,
        item_id: itemId,
        expected_version: itemVersion ?? preview?.item_version ?? null,
        actor_id: actorId,
        persist_recommendation: true,
        suppress_seconds_on_no_candidate: 300,
      });

      if (res.assigned) {
        onToast({
          title: "Auto-assign thành công",
          description: `Assigned cho ${res.assignee_id}`,
        });
        onAssigned?.();
        await loadPreview();
      } else {
        onToast({
          title: "Không có candidate phù hợp",
          description: res.reason || "no_eligible_candidate",
        });
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "Unknown error";
      onToast({
        title: "Auto-assign thất bại",
        description: detail,
        variant: "destructive",
      });
    } finally {
      setExecuting(false);
    }
  }

  useEffect(() => {
    loadPreview();
  }, [queueKey, itemId]);

  return (
    <div className="rounded-xl border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Auto-Assign</h3>
        <button className="border rounded px-3 py-1" onClick={loadPreview} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {!preview ? (
        <div className="text-sm text-gray-500">Chưa có preview.</div>
      ) : (
        <>
          <div className="text-sm">
            <div><strong>Guardrails:</strong> {preview.guardrails_applied.join(", ") || "none"}</div>
            <div><strong>Selected:</strong> {preview.selected_candidate?.operator_id || "none"}</div>
          </div>

          <div className="space-y-2">
            {preview.top_candidates.map((c) => (
              <div key={c.operator_id} className="rounded border p-3 text-sm">
                <div className="flex items-center justify-between">
                  <strong>{c.operator_id}</strong>
                  <span>score={c.score.toFixed(2)}</span>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div>confidence: {c.confidence_score.toFixed(2)}</div>
                  <div>impact: {c.impact_score.toFixed(2)}</div>
                  <div>load: {c.load_score.toFixed(2)}</div>
                  <div>specialty: {c.specialty_score.toFixed(2)}</div>
                  <div>acceptance: {c.acceptance_behavior_score.toFixed(2)}</div>
                  <div>cooldown: {String(c.cooldown_blocked)}</div>
                </div>
                {c.reasons.length > 0 && (
                  <div className="mt-2 text-xs text-gray-500">{c.reasons.join(" | ")}</div>
                )}
              </div>
            ))}
          </div>

          <button
            className="rounded bg-black text-white px-4 py-2 disabled:opacity-50"
            onClick={runAssign}
            disabled={executing}
          >
            {executing ? "Đang assign..." : "Run Auto-Assign"}
          </button>
        </>
      )}
    </div>
  );
}
18) FRONTEND — PATCH QUEUE PANEL
frontend/src/components/queue/OperatorQueuePanel.tsx
Trong panel item detail hoặc action sidebar, nối thêm:
import { AutoAssignActionPanel } from "./AutoAssignActionPanel";
Và render:
<AutoAssignActionPanel
  queueKey={selectedItem.queue_key}
  itemId={selectedItem.item_id}
  itemVersion={selectedItem.version}
  actorId={currentActorId}
  onToast={onToast}
  onAssigned={() => {
    refetchQueue();
    refetchItemDetail?.();
  }}
/>
19) FRONTEND — TEST
frontend/src/components/queue/__tests__/AutoAssignActionPanel.test.tsx
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { AutoAssignActionPanel } from "../AutoAssignActionPanel";

jest.mock("../../../api/queueAutoAssign", () => ({
  fetchAutoAssignPreview: jest.fn().mockResolvedValue({
    queue_key: "render_ops",
    item_id: "item_1",
    item_version: 3,
    top_candidates: [
      {
        operator_id: "op_a",
        score: 0.91,
        confidence_score: 0.95,
        impact_score: 0.88,
        load_score: 0.90,
        specialty_score: 0.92,
        acceptance_behavior_score: 0.84,
        cooldown_blocked: false,
        capacity_blocked: false,
        reasons: [],
      },
    ],
    selected_candidate: {
      operator_id: "op_a",
      score: 0.91,
      confidence_score: 0.95,
      impact_score: 0.88,
      load_score: 0.90,
      specialty_score: 0.92,
      acceptance_behavior_score: 0.84,
      cooldown_blocked: false,
      capacity_blocked: false,
      reasons: [],
    },
    guardrails_applied: [],
  }),
  executeAutoAssign: jest.fn().mockResolvedValue({
    queue_key: "render_ops",
    item_id: "item_1",
    assigned: true,
    assignee_id: "op_a",
    recommendation_id: "rec_1",
    action_id: "act_1",
    reason: "assigned",
    guardrails_applied: [],
    executed_at: "2026-04-12T10:00:00Z",
  }),
}));

describe("AutoAssignActionPanel", () => {
  it("loads preview and executes assign", async () => {
    const onToast = jest.fn();
    const onAssigned = jest.fn();

    render(
      <AutoAssignActionPanel
        queueKey="render_ops"
        itemId="item_1"
        itemVersion={3}
        actorId="operator_1"
        onToast={onToast}
        onAssigned={onAssigned}
      />
    );

    await waitFor(() => expect(screen.getByText("op_a")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Run Auto-Assign"));

    await waitFor(() => {
      expect(onAssigned).toHaveBeenCalled();
    });
  });
});
20) MAP PRODUCTION NGẮN GỌN KHI GẮN VÀO REPO THẬT
Đây là phần quan trọng nhất để patch không bị “đẹp nhưng không chạy”.
A. candidate_operator_ids_provider(...)
Repo thật phải map được danh sách operator ứng viên từ:
role/permission
queue membership
shift/on-call
active status
accepts_auto_assign
Ví dụ nên trả:
["op_a", "op_b", "op_c"]
và lọc từ:
operator đang disabled
ngoài ca trực
không thuộc queue
đã vượt max_active_items cứng ở policy layer nếu muốn
B. QueueRepository.assign(...)
Bản thật nên làm đủ 4 việc:
update assignee
tăng version
ghi audit log hoặc emit domain event
raise CAS/version conflict nếu expected_version lệch
Pseudo:
def assign(...):
    item = self.get_item(...)
    if expected_version is not None and item.version != expected_version:
        raise VersionConflictError(...)
    item.assignee_id = assignee_id
    item.version += 1
    self.db.flush()
    return item
C. OperatorActivityRepository.last_assignment_at(...)
Nên map từ:
queue_assign_events
queue_assignment_action
audit log event type = queue.assignment.created
Ưu tiên dùng bảng event thật để cooldown chính xác.
D. Specialty rollup source thật
Nên rollup từ:
resolved_count theo provider/project/severity/item_type
execution_success_count
avg_resolution_seconds
conflict_count
reopen_count nếu có
approval success nếu item đi qua governance
Công thức specialty nên dùng trọng số nhẹ lúc đầu, tránh overfit.
E. Acceptance behavior không nên thống trị toàn bộ score
Hiện tôi để:
load 35%
specialty 40%
acceptance 25%
Đây là mức an toàn.
Không nên để acceptance quá cao, vì hệ dễ bias theo người “hay bấm accept” thay vì người xử lý tốt.
F. Cooldown / suppression
Khi không có candidate phù hợp:
tạo suppress action
TTL suppression nên map vào queue item state thật hoặc ephemeral cache
tránh loop auto-assign spam cùng item
Tối thiểu production nên có:
suppressed_until
last_auto_assign_attempt_at
last_auto_assign_reason
21) KẾT QUẢ SAU BẢN NÀY
Sau patch này queue của bạn có thêm 4 lớp mạnh:
1. Recommendation acceptance behavior
Hệ biết:
operator nào thường accept recommendation
hành vi gần đây tốt/xấu ra sao
score acceptance có thể dùng như tín hiệu mềm
2. Specialty model
Hệ biết:
ai mạnh theo provider
ai mạnh theo project
ai mạnh theo severity
ai mạnh theo item_type
3. Capacity model
Hệ biết:
operator nào đã quá tải
operator nào đang trong cooldown
operator nào phù hợp để nhận thêm việc
4. Auto-assign action endpoint
Hệ đã có thể:
preview candidate
chọn best candidate
assign thật
persist recommendation history
ghi assignment action
map conflict 409
Nói ngắn gọn, queue chuyển từ:
recommendation support
sang:
controlled assignment execution
22) BƯỚC MẠNH NHẤT NGAY SAU BẢN NÀY
Bước tiếp theo mạnh nhất là:
PHASE 3 — SUPPRESSION WINDOWS + REASSIGN POLICY + AUTO-ASSIGN GOVERNANCE GUARDRAILS
Vì lúc đó hệ sẽ tiến thêm 1 nấc từ:
assign được
sang:
biết khi nào không nên assign
biết khi nào được reassign
biết item nào cần human approval trước khi auto-assign
có suppression TTL / repeated-failure guard / no-thrash policy
có policy cho critical severity / sensitive project / governance-bound items
Tức là khi đó queue sẽ chuyển từ:
controlled execution
sang:
policy-governed controlled execution
Tôi có thể viết tiếp ngay bản đó cũng theo đúng format file-by-file paste-ready.
PHASE 3 — SUPPRESSION WINDOWS + REASSIGN POLICY + AUTO-ASSIGN GOVERNANCE GUARDRAILS Vì lúc đó hệ sẽ tiến thêm 1 nấc từ: assign được sang: biết khi nào không nên assign biết khi nào được reassign biết item nào cần human approval trước khi auto-assign có suppression TTL / repeated-failure guard / no-thrash policy có policy cho critical severity / sensitive project / governance-bound items Tức là khi đó queue sẽ chuyển từ: controlled execution sang: policy-governed controlled execution Tôi có thể viết tiếp ngay bản đó cũng theo đúng format file-by-file paste-ready.
Đã suy nghĩ trong vài giây
Dưới đây là bản:
PHASE 3 — SUPPRESSION WINDOWS + REASSIGN POLICY + AUTO-ASSIGN GOVERNANCE GUARDRAILS
Mục tiêu của bản này là nâng queue từ:
assign được
sang:
biết khi nào không nên assign
biết khi nào được reassign
biết item nào phải qua human approval trước khi auto-assign
có suppression TTL / repeated-failure guard / no-thrash policy
có policy cho critical severity / sensitive project / governance-bound items
Tức là queue chuyển từ:
controlled execution
sang:
policy-governed controlled execution
Tôi viết theo đúng kiểu file-by-file paste-ready, bám repo thật, không tái cấu trúc vô cớ.
1) THIẾT KẾ NGẮN GỌN
Bản này thêm 5 lớp:
A. Suppression windows
Mỗi item có thể bị suppress đến một thời điểm:
chưa đủ điều kiện auto-assign lại
vừa bị fail/reject/reassign nhiều lần
chưa qua human review
đang nằm trong cooldown window
B. Reassign policy
Không phải item nào cũng được chuyển người liên tục.
Cần guard:
max reassign trong 24h
min age since last assignment
block khi item vừa mới được assign
block khi item đang governance lock / approval pending
C. Governance guardrails
Một số item bắt buộc human approval nếu:
severity = critical
project nhạy cảm
provider đặc biệt
item thuộc governance-bound category
item vượt impact/risk threshold
D. Repeated-failure guard
Nếu một item đã:
auto-assign fail liên tiếp
accept rồi conflict nhiều lần
reassign rồi vẫn unresolved
thì hệ không tiếp tục cố auto-assign nữa mà suppress + escalate.
E. No-thrash policy
Không để item bị:
assign → reassign → assign → reassign liên tục trong thời gian ngắn
2) BACKEND — MODELS
backend/app/models/queue_assignment_guardrail_state.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueAssignmentGuardrailState(Base):
    __tablename__ = "queue_assignment_guardrail_state"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True, unique=True)

    suppressed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    suppression_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    auto_assign_attempt_count_24h: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_assign_failure_count_24h: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reassign_count_24h: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assignment_flip_count_24h: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_auto_assign_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_auto_assign_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_assignment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reassignment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    governance_approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    governance_approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    policy_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
backend/app/models/queue_assignment_policy_rule.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueAssignmentPolicyRule(Base):
    __tablename__ = "queue_assignment_policy_rule"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    scope_type: Mapped[str] = mapped_column(String(50), nullable=False, default="global")
    # global | severity | provider | project | item_type

    scope_value: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    # suppress | require_human_review | require_governance_approval | block_reassign | limit_reassign | cooldown

    condition_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    effect_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    reason_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
backend/app/models/queue_assignment_governance_decision.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueAssignmentGovernanceDecision(Base):
    __tablename__ = "queue_assignment_governance_decision"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    decision_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # auto_assign_allowed | human_review_required | governance_approval_required | reassign_blocked

    decision_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # allowed | blocked | pending_review | pending_approval

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_rule_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
3) BACKEND — REGISTER IMPORTS
backend/app/db/base.py
Thêm import:
from app.models.queue_assignment_guardrail_state import QueueAssignmentGuardrailState
from app.models.queue_assignment_policy_rule import QueueAssignmentPolicyRule
from app.models.queue_assignment_governance_decision import QueueAssignmentGovernanceDecision
4) BACKEND — REPOSITORIES
backend/app/repositories/queue_assignment_guardrail_state_repository.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.queue_assignment_guardrail_state import QueueAssignmentGuardrailState


class QueueAssignmentGuardrailStateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, queue_key: str, item_id: str) -> QueueAssignmentGuardrailState | None:
        stmt = select(QueueAssignmentGuardrailState).where(
            QueueAssignmentGuardrailState.queue_key == queue_key,
            QueueAssignmentGuardrailState.item_id == item_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_or_create(self, queue_key: str, item_id: str) -> QueueAssignmentGuardrailState:
        obj = self.get(queue_key, item_id)
        if obj is not None:
            return obj

        obj = QueueAssignmentGuardrailState(
            queue_key=queue_key,
            item_id=item_id,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def set_suppression(
        self,
        *,
        queue_key: str,
        item_id: str,
        suppressed_until: datetime,
        suppression_reason: str,
        policy_snapshot_json: dict | None = None,
    ) -> QueueAssignmentGuardrailState:
        obj = self.get_or_create(queue_key, item_id)
        obj.suppressed_until = suppressed_until
        obj.suppression_reason = suppression_reason
        obj.policy_snapshot_json = policy_snapshot_json
        self.db.flush()
        return obj

    def clear_suppression(self, *, queue_key: str, item_id: str) -> QueueAssignmentGuardrailState:
        obj = self.get_or_create(queue_key, item_id)
        obj.suppressed_until = None
        obj.suppression_reason = None
        self.db.flush()
        return obj
backend/app/repositories/queue_assignment_policy_rule_repository.py
from __future__ import annotations

from sqlalchemy import asc, select
from sqlalchemy.orm import Session

from app.models.queue_assignment_policy_rule import QueueAssignmentPolicyRule


class QueueAssignmentPolicyRuleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_enabled_for_queue(self, queue_key: str) -> list[QueueAssignmentPolicyRule]:
        stmt = (
            select(QueueAssignmentPolicyRule)
            .where(
                QueueAssignmentPolicyRule.queue_key == queue_key,
                QueueAssignmentPolicyRule.enabled.is_(True),
            )
            .order_by(asc(QueueAssignmentPolicyRule.priority))
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self,
        *,
        queue_key: str,
        rule_key: str,
        enabled: bool,
        priority: int,
        scope_type: str,
        scope_value: str | None,
        action_type: str,
        condition_json: dict,
        effect_json: dict,
        reason_template: str | None = None,
        created_by: str | None = None,
    ) -> QueueAssignmentPolicyRule:
        obj = QueueAssignmentPolicyRule(
            queue_key=queue_key,
            rule_key=rule_key,
            enabled=enabled,
            priority=priority,
            scope_type=scope_type,
            scope_value=scope_value,
            action_type=action_type,
            condition_json=condition_json,
            effect_json=effect_json,
            reason_template=reason_template,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(obj)
        self.db.flush()
        return obj
backend/app/repositories/queue_assignment_governance_decision_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.queue_assignment_governance_decision import QueueAssignmentGovernanceDecision


class QueueAssignmentGovernanceDecisionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        queue_key: str,
        item_id: str,
        decision_type: str,
        decision_status: str,
        reason: str | None = None,
        policy_rule_key: str | None = None,
        actor_id: str | None = None,
        metadata_json: dict | None = None,
    ) -> QueueAssignmentGovernanceDecision:
        obj = QueueAssignmentGovernanceDecision(
            queue_key=queue_key,
            item_id=item_id,
            decision_type=decision_type,
            decision_status=decision_status,
            reason=reason,
            policy_rule_key=policy_rule_key,
            actor_id=actor_id,
            metadata_json=metadata_json,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_recent_for_item(self, queue_key: str, item_id: str, limit: int = 20) -> list[QueueAssignmentGovernanceDecision]:
        stmt = (
            select(QueueAssignmentGovernanceDecision)
            .where(
                QueueAssignmentGovernanceDecision.queue_key == queue_key,
                QueueAssignmentGovernanceDecision.item_id == item_id,
            )
            .order_by(desc(QueueAssignmentGovernanceDecision.created_at))
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
5) BACKEND — SCHEMAS
backend/app/schemas/queue_assignment_policy.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class QueueAssignmentPolicyRuleIn(BaseModel):
    queue_key: str
    rule_key: str
    enabled: bool = True
    priority: int = 100
    scope_type: str = "global"
    scope_value: str | None = None
    action_type: str
    condition_json: dict
    effect_json: dict
    reason_template: str | None = None
    created_by: str | None = None


class QueueAssignmentPolicyRuleOut(BaseModel):
    queue_key: str
    rule_key: str
    enabled: bool
    priority: int
    scope_type: str
    scope_value: str | None
    action_type: str
    condition_json: dict
    effect_json: dict
    reason_template: str | None

    class Config:
        from_attributes = True


class QueueGuardrailDecisionOut(BaseModel):
    allowed: bool
    blocked: bool
    requires_human_review: bool
    requires_governance_approval: bool
    suppression_active: bool
    suppressed_until: datetime | None
    reasons: list[str]
    applied_rule_keys: list[str]
    policy_snapshot_json: dict | None = None


class QueueReassignPreviewOut(BaseModel):
    queue_key: str
    item_id: str
    allowed: bool
    blocked: bool
    reasons: list[str]
    current_assignee_id: str | None
    reassign_count_24h: int
    assignment_flip_count_24h: int
    min_seconds_since_last_assignment_required: int | None = None
    seconds_since_last_assignment: int | None = None


class QueueReassignExecuteIn(BaseModel):
    queue_key: str
    item_id: str
    new_assignee_id: str
    actor_id: str
    expected_version: int | None = None
    reason: str | None = None


class QueueReassignExecuteOut(BaseModel):
    queue_key: str
    item_id: str
    reassigned: bool
    previous_assignee_id: str | None
    new_assignee_id: str | None
    action_id: str | None
    reason: str | None
    guardrails_applied: list[str] = []
    executed_at: datetime
6) BACKEND — POLICY EVALUATOR SERVICE
backend/app/services/queue_assignment_policy_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.queue_assignment_guardrail_state_repository import QueueAssignmentGuardrailStateRepository
from app.repositories.queue_assignment_policy_rule_repository import QueueAssignmentPolicyRuleRepository


@dataclass
class QueueGuardrailDecision:
    allowed: bool
    blocked: bool
    requires_human_review: bool
    requires_governance_approval: bool
    suppression_active: bool
    suppressed_until: datetime | None
    reasons: list[str]
    applied_rule_keys: list[str]
    policy_snapshot_json: dict | None = None


class QueueAssignmentPolicyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.guardrail_state_repo = QueueAssignmentGuardrailStateRepository(db)
        self.policy_rule_repo = QueueAssignmentPolicyRuleRepository(db)

    def evaluate_auto_assign(self, *, queue_key: str, item: Any) -> QueueGuardrailDecision:
        reasons: list[str] = []
        applied_rule_keys: list[str] = []
        requires_human_review = False
        requires_governance_approval = False
        blocked = False
        suppressed_until = None
        suppression_active = False

        state = self.guardrail_state_repo.get_or_create(queue_key, getattr(item, "id"))

        now = datetime.now(timezone.utc)
        if state.suppressed_until and state.suppressed_until > now:
            suppression_active = True
            blocked = True
            suppressed_until = state.suppressed_until
            reasons.append(state.suppression_reason or "suppression_active")
            applied_rule_keys.append("state:suppression_active")

        rules = self.policy_rule_repo.list_enabled_for_queue(queue_key)
        context = self._build_context(item=item, state=state)

        for rule in rules:
            if not self._scope_matches(rule, item):
                continue
            if not self._conditions_match(rule.condition_json, context):
                continue

            applied_rule_keys.append(rule.rule_key)

            if rule.action_type == "require_human_review":
                requires_human_review = True
                reasons.append(rule.reason_template or rule.rule_key)

            elif rule.action_type == "require_governance_approval":
                requires_governance_approval = True
                blocked = True
                reasons.append(rule.reason_template or rule.rule_key)

            elif rule.action_type == "suppress":
                blocked = True
                reasons.append(rule.reason_template or rule.rule_key)

            elif rule.action_type == "cooldown":
                blocked = True
                reasons.append(rule.reason_template or rule.rule_key)

        if state.human_review_required:
            requires_human_review = True
            reasons.append(state.human_review_reason or "human_review_required")
            applied_rule_keys.append("state:human_review_required")

        if state.governance_approval_required:
            requires_governance_approval = True
            blocked = True
            reasons.append(state.governance_approval_reason or "governance_approval_required")
            applied_rule_keys.append("state:governance_approval_required")

        allowed = not blocked and not requires_governance_approval

        return QueueGuardrailDecision(
            allowed=allowed,
            blocked=blocked,
            requires_human_review=requires_human_review,
            requires_governance_approval=requires_governance_approval,
            suppression_active=suppression_active,
            suppressed_until=suppressed_until,
            reasons=reasons,
            applied_rule_keys=applied_rule_keys,
            policy_snapshot_json={
                "item_id": getattr(item, "id", None),
                "severity": getattr(item, "severity", None),
                "provider": getattr(item, "provider", None),
                "project_id": getattr(item, "project_id", None),
                "rules_applied": applied_rule_keys,
            },
        )

    def _build_context(self, *, item: Any, state) -> dict:
        return {
            "severity": getattr(item, "severity", None),
            "provider": getattr(item, "provider", None),
            "project_id": getattr(item, "project_id", None),
            "item_type": getattr(item, "item_type", None),
            "is_critical": getattr(item, "severity", None) == "critical",
            "auto_assign_attempt_count_24h": state.auto_assign_attempt_count_24h,
            "auto_assign_failure_count_24h": state.auto_assign_failure_count_24h,
            "reassign_count_24h": state.reassign_count_24h,
            "assignment_flip_count_24h": state.assignment_flip_count_24h,
        }

    def _scope_matches(self, rule, item: Any) -> bool:
        if rule.scope_type == "global":
            return True
        if rule.scope_type == "severity":
            return str(getattr(item, "severity", None)) == str(rule.scope_value)
        if rule.scope_type == "provider":
            return str(getattr(item, "provider", None)) == str(rule.scope_value)
        if rule.scope_type == "project":
            return str(getattr(item, "project_id", None)) == str(rule.scope_value)
        if rule.scope_type == "item_type":
            return str(getattr(item, "item_type", None)) == str(rule.scope_value)
        return False

    def _conditions_match(self, condition_json: dict, context: dict) -> bool:
        for key, expected in condition_json.items():
            actual = context.get(key)

            if isinstance(expected, dict):
                if "gte" in expected and not (actual is not None and actual >= expected["gte"]):
                    return False
                if "gt" in expected and not (actual is not None and actual > expected["gt"]):
                    return False
                if "lte" in expected and not (actual is not None and actual <= expected["lte"]):
                    return False
                if "lt" in expected and not (actual is not None and actual < expected["lt"]):
                    return False
                if "eq" in expected and not (actual == expected["eq"]):
                    return False
            else:
                if actual != expected:
                    return False
        return True
7) BACKEND — SUPPRESSION / FAILURE / THRASH STATE SERVICE
backend/app/services/queue_assignment_guardrail_state_service.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.repositories.queue_assignment_guardrail_state_repository import QueueAssignmentGuardrailStateRepository


class QueueAssignmentGuardrailStateService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = QueueAssignmentGuardrailStateRepository(db)

    def record_auto_assign_attempt(self, *, queue_key: str, item_id: str) -> None:
        obj = self.repo.get_or_create(queue_key, item_id)
        obj.auto_assign_attempt_count_24h += 1
        obj.last_auto_assign_attempt_at = datetime.now(timezone.utc)
        self.db.flush()

    def record_auto_assign_failure(
        self,
        *,
        queue_key: str,
        item_id: str,
        reason: str,
        suppress_seconds: int | None = None,
    ) -> None:
        obj = self.repo.get_or_create(queue_key, item_id)
        obj.auto_assign_failure_count_24h += 1
        obj.last_auto_assign_failure_at = datetime.now(timezone.utc)

        if suppress_seconds and suppress_seconds > 0:
            obj.suppressed_until = datetime.now(timezone.utc) + timedelta(seconds=suppress_seconds)
            obj.suppression_reason = reason

        self.db.flush()

    def record_assignment(self, *, queue_key: str, item_id: str) -> None:
        obj = self.repo.get_or_create(queue_key, item_id)
        obj.last_assignment_at = datetime.now(timezone.utc)
        self.db.flush()

    def record_reassignment(self, *, queue_key: str, item_id: str) -> None:
        obj = self.repo.get_or_create(queue_key, item_id)
        obj.reassign_count_24h += 1
        obj.assignment_flip_count_24h += 1
        obj.last_reassignment_at = datetime.now(timezone.utc)
        self.db.flush()

    def require_human_review(self, *, queue_key: str, item_id: str, reason: str) -> None:
        obj = self.repo.get_or_create(queue_key, item_id)
        obj.human_review_required = True
        obj.human_review_reason = reason
        self.db.flush()

    def require_governance_approval(self, *, queue_key: str, item_id: str, reason: str) -> None:
        obj = self.repo.get_or_create(queue_key, item_id)
        obj.governance_approval_required = True
        obj.governance_approval_reason = reason
        self.db.flush()

    def clear_review_flags(self, *, queue_key: str, item_id: str) -> None:
        obj = self.repo.get_or_create(queue_key, item_id)
        obj.human_review_required = False
        obj.human_review_reason = None
        obj.governance_approval_required = False
        obj.governance_approval_reason = None
        self.db.flush()

    def apply_repeated_failure_guard(
        self,
        *,
        queue_key: str,
        item_id: str,
        failure_threshold: int = 3,
        suppress_seconds: int = 1800,
    ) -> bool:
        obj = self.repo.get_or_create(queue_key, item_id)
        if obj.auto_assign_failure_count_24h >= failure_threshold:
            obj.suppressed_until = datetime.now(timezone.utc) + timedelta(seconds=suppress_seconds)
            obj.suppression_reason = "repeated_auto_assign_failures"
            self.db.flush()
            return True
        return False
8) BACKEND — REASSIGN POLICY SERVICE
backend/app/services/queue_reassign_policy_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.queue_assignment_guardrail_state_repository import QueueAssignmentGuardrailStateRepository


@dataclass
class QueueReassignDecision:
    allowed: bool
    blocked: bool
    reasons: list[str]
    reassign_count_24h: int
    assignment_flip_count_24h: int
    min_seconds_since_last_assignment_required: int | None
    seconds_since_last_assignment: int | None


class QueueReassignPolicyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.guardrail_repo = QueueAssignmentGuardrailStateRepository(db)

    def evaluate(
        self,
        *,
        queue_key: str,
        item: Any,
        min_seconds_since_last_assignment: int = 300,
        max_reassign_count_24h: int = 3,
        max_assignment_flip_count_24h: int = 4,
    ) -> QueueReassignDecision:
        reasons: list[str] = []
        blocked = False

        state = self.guardrail_repo.get_or_create(queue_key, getattr(item, "id"))

        if state.governance_approval_required:
            blocked = True
            reasons.append(state.governance_approval_reason or "governance_approval_required")

        seconds_since_last_assignment = None
        if state.last_assignment_at is not None:
            seconds_since_last_assignment = int(
                (datetime.now(timezone.utc) - state.last_assignment_at).total_seconds()
            )
            if seconds_since_last_assignment < min_seconds_since_last_assignment:
                blocked = True
                reasons.append(f"min_assignment_age_not_met:{min_seconds_since_last_assignment}")

        if state.reassign_count_24h >= max_reassign_count_24h:
            blocked = True
            reasons.append(f"max_reassign_count_24h:{max_reassign_count_24h}")

        if state.assignment_flip_count_24h >= max_assignment_flip_count_24h:
            blocked = True
            reasons.append(f"assignment_flip_limit:{max_assignment_flip_count_24h}")

        allowed = not blocked

        return QueueReassignDecision(
            allowed=allowed,
            blocked=blocked,
            reasons=reasons,
            reassign_count_24h=state.reassign_count_24h,
            assignment_flip_count_24h=state.assignment_flip_count_24h,
            min_seconds_since_last_assignment_required=min_seconds_since_last_assignment,
            seconds_since_last_assignment=seconds_since_last_assignment,
        )
9) BACKEND — PATCH AUTO-ASSIGN SERVICE
Đây là điểm quan trọng nhất của bản này.
backend/app/services/queue_auto_assign_service.py
Patch service trước khi chọn candidate:
from app.repositories.queue_assignment_governance_decision_repository import (
    QueueAssignmentGovernanceDecisionRepository,
)
from app.services.queue_assignment_guardrail_state_service import QueueAssignmentGuardrailStateService
from app.services.queue_assignment_policy_service import QueueAssignmentPolicyService
Trong __init__ thêm:
self.guardrail_state_service = QueueAssignmentGuardrailStateService(db)
self.policy_service = QueueAssignmentPolicyService(db)
self.governance_decision_repo = QueueAssignmentGovernanceDecisionRepository(db)
Patch execute(...) như sau:
def execute(
    self,
    *,
    queue_key: str,
    item_id: str,
    actor_id: str,
    expected_version: int | None = None,
    persist_recommendation: bool = True,
    suppress_seconds_on_no_candidate: int = 300,
):
    item = self.queue_repository.get_item(queue_key, item_id)
    if item is None:
        raise ValueError("queue item not found")

    self.guardrail_state_service.record_auto_assign_attempt(queue_key=queue_key, item_id=item_id)

    policy_decision = self.policy_service.evaluate_auto_assign(queue_key=queue_key, item=item)

    if policy_decision.requires_governance_approval:
        self.governance_decision_repo.create(
            queue_key=queue_key,
            item_id=item_id,
            decision_type="governance_approval_required",
            decision_status="pending_approval",
            reason="; ".join(policy_decision.reasons) if policy_decision.reasons else "governance_approval_required",
            actor_id=actor_id,
            metadata_json=policy_decision.policy_snapshot_json,
        )
        self.db.commit()
        return QueueAutoAssignExecuteOut(
            queue_key=queue_key,
            item_id=item_id,
            assigned=False,
            assignee_id=None,
            recommendation_id=None,
            action_id=None,
            reason="governance_approval_required",
            guardrails_applied=policy_decision.applied_rule_keys,
            executed_at=datetime.now(timezone.utc),
        )

    if policy_decision.blocked:
        self.guardrail_state_service.record_auto_assign_failure(
            queue_key=queue_key,
            item_id=item_id,
            reason="blocked_by_policy",
            suppress_seconds=suppress_seconds_on_no_candidate,
        )
        self.governance_decision_repo.create(
            queue_key=queue_key,
            item_id=item_id,
            decision_type="auto_assign_allowed",
            decision_status="blocked",
            reason="; ".join(policy_decision.reasons) if policy_decision.reasons else "blocked_by_policy",
            actor_id=actor_id,
            metadata_json=policy_decision.policy_snapshot_json,
        )
        self.db.commit()
        return QueueAutoAssignExecuteOut(
            queue_key=queue_key,
            item_id=item_id,
            assigned=False,
            assignee_id=None,
            recommendation_id=None,
            action_id=None,
            reason="blocked_by_policy",
            guardrails_applied=policy_decision.applied_rule_keys,
            executed_at=datetime.now(timezone.utc),
        )

    candidates = self._rank_candidates(queue_key=queue_key, item=item)
    guardrails = self._build_guardrails(candidates) + policy_decision.applied_rule_keys

    selected = candidates[0] if candidates else None
    if selected is None or selected.capacity_blocked or selected.score <= 0:
        self.guardrail_state_service.record_auto_assign_failure(
            queue_key=queue_key,
            item_id=item_id,
            reason="no_eligible_candidate",
            suppress_seconds=suppress_seconds_on_no_candidate,
        )
        self.guardrail_state_service.apply_repeated_failure_guard(
            queue_key=queue_key,
            item_id=item_id,
            failure_threshold=3,
            suppress_seconds=1800,
        )

        action = self.assignment_action_repo.create(
            queue_key=queue_key,
            item_id=item_id,
            item_version=int(getattr(item, "version", 1)),
            action_type="suppress",
            actor_id=actor_id,
            previous_assignee_id=getattr(item, "assignee_id", None),
            new_assignee_id=None,
            confidence_score=None,
            impact_score=None,
            reason="no_eligible_candidate",
            metadata_json={"suppress_seconds": suppress_seconds_on_no_candidate},
        )
        self.db.commit()
        return QueueAutoAssignExecuteOut(
            queue_key=queue_key,
            item_id=item_id,
            assigned=False,
            assignee_id=None,
            recommendation_id=None,
            action_id=str(action.id),
            reason="no_eligible_candidate",
            guardrails_applied=guardrails,
            executed_at=datetime.now(timezone.utc),
        )

    # giữ nguyên phần recommendation + assign cũ
    # sau assign thành công nhớ record assignment
    ...
Sau khi assign thành công, thêm:
self.guardrail_state_service.record_assignment(queue_key=queue_key, item_id=item_id)
Nếu policy yêu cầu human review mềm nhưng không block hoàn toàn, có thể thêm metadata:
if policy_decision.requires_human_review:
    # mềm: vẫn preview được, execute thật thì có thể tuỳ policy chặn hoặc gắn cờ
    pass
10) BACKEND — REASSIGN SERVICE
backend/app/services/queue_reassign_service.py
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.repositories.queue_assignment_action_repository import QueueAssignmentActionRepository
from app.services.interfaces.queue_repository import QueueRepositoryProtocol
from app.services.queue_assignment_guardrail_state_service import QueueAssignmentGuardrailStateService
from app.services.queue_reassign_policy_service import QueueReassignPolicyService
from app.schemas.queue_assignment_policy import QueueReassignExecuteOut, QueueReassignPreviewOut


class QueueReassignService:
    def __init__(
        self,
        db: Session,
        *,
        queue_repository: QueueRepositoryProtocol,
        audit_log_service=None,
        notification_service=None,
    ) -> None:
        self.db = db
        self.queue_repository = queue_repository
        self.audit_log_service = audit_log_service
        self.notification_service = notification_service

        self.action_repo = QueueAssignmentActionRepository(db)
        self.guardrail_state_service = QueueAssignmentGuardrailStateService(db)
        self.reassign_policy_service = QueueReassignPolicyService(db)

    def preview(self, *, queue_key: str, item_id: str) -> QueueReassignPreviewOut:
        item = self.queue_repository.get_item(queue_key, item_id)
        if item is None:
            raise ValueError("queue item not found")

        decision = self.reassign_policy_service.evaluate(queue_key=queue_key, item=item)

        return QueueReassignPreviewOut(
            queue_key=queue_key,
            item_id=item_id,
            allowed=decision.allowed,
            blocked=decision.blocked,
            reasons=decision.reasons,
            current_assignee_id=getattr(item, "assignee_id", None),
            reassign_count_24h=decision.reassign_count_24h,
            assignment_flip_count_24h=decision.assignment_flip_count_24h,
            min_seconds_since_last_assignment_required=decision.min_seconds_since_last_assignment_required,
            seconds_since_last_assignment=decision.seconds_since_last_assignment,
        )

    def execute(
        self,
        *,
        queue_key: str,
        item_id: str,
        new_assignee_id: str,
        actor_id: str,
        expected_version: int | None = None,
        reason: str | None = None,
    ) -> QueueReassignExecuteOut:
        item = self.queue_repository.get_item(queue_key, item_id)
        if item is None:
            raise ValueError("queue item not found")

        decision = self.reassign_policy_service.evaluate(queue_key=queue_key, item=item)
        if decision.blocked:
            return QueueReassignExecuteOut(
                queue_key=queue_key,
                item_id=item_id,
                reassigned=False,
                previous_assignee_id=getattr(item, "assignee_id", None),
                new_assignee_id=None,
                action_id=None,
                reason="; ".join(decision.reasons) if decision.reasons else "reassign_blocked",
                guardrails_applied=decision.reasons,
                executed_at=datetime.now(timezone.utc),
            )

        previous_assignee_id = getattr(item, "assignee_id", None)

        updated_item = self.queue_repository.assign(
            queue_key=queue_key,
            item_id=item_id,
            assignee_id=new_assignee_id,
            actor_id=actor_id,
            expected_version=expected_version,
            reason=reason or "manual_reassign",
            metadata={"reassign": True},
        )

        action = self.action_repo.create(
            queue_key=queue_key,
            item_id=item_id,
            item_version=int(getattr(updated_item, "version", getattr(item, "version", 1))),
            action_type="reassign",
            actor_id=actor_id,
            previous_assignee_id=previous_assignee_id,
            new_assignee_id=new_assignee_id,
            reason=reason or "manual_reassign",
            metadata_json={"policy_reasons": decision.reasons},
        )

        self.guardrail_state_service.record_reassignment(queue_key=queue_key, item_id=item_id)

        if self.audit_log_service:
            self.audit_log_service.log(
                event_type="queue.reassign.executed",
                actor_id=actor_id,
                entity_type="queue_item",
                entity_id=item_id,
                payload={
                    "queue_key": queue_key,
                    "previous_assignee_id": previous_assignee_id,
                    "new_assignee_id": new_assignee_id,
                },
            )

        if self.notification_service:
            self.notification_service.emit(
                event_type="queue.assignment.reassigned",
                payload={
                    "queue_key": queue_key,
                    "item_id": item_id,
                    "previous_assignee_id": previous_assignee_id,
                    "new_assignee_id": new_assignee_id,
                    "actor_id": actor_id,
                },
            )

        self.db.commit()

        return QueueReassignExecuteOut(
            queue_key=queue_key,
            item_id=item_id,
            reassigned=True,
            previous_assignee_id=previous_assignee_id,
            new_assignee_id=new_assignee_id,
            action_id=str(action.id),
            reason="reassigned",
            guardrails_applied=decision.reasons,
            executed_at=datetime.now(timezone.utc),
        )
11) BACKEND — ROUTES
backend/app/api/routes/queue_assignment_policy.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.queue_assignment_policy_rule_repository import QueueAssignmentPolicyRuleRepository
from app.schemas.queue_assignment_policy import (
    QueueAssignmentPolicyRuleIn,
    QueueAssignmentPolicyRuleOut,
    QueueReassignExecuteIn,
)
from app.services.queue_assignment_policy_service import QueueAssignmentPolicyService
from app.services.queue_reassign_service import QueueReassignService

router = APIRouter(prefix="/queue/assignment-policy", tags=["queue-assignment-policy"])


def get_queue_repository():
    from app.dependencies.queue_runtime import get_queue_repository
    return get_queue_repository()


@router.post("/rules", response_model=QueueAssignmentPolicyRuleOut)
def create_policy_rule(
    payload: QueueAssignmentPolicyRuleIn,
    db: Session = Depends(get_db),
):
    repo = QueueAssignmentPolicyRuleRepository(db)
    obj = repo.create(
        queue_key=payload.queue_key,
        rule_key=payload.rule_key,
        enabled=payload.enabled,
        priority=payload.priority,
        scope_type=payload.scope_type,
        scope_value=payload.scope_value,
        action_type=payload.action_type,
        condition_json=payload.condition_json,
        effect_json=payload.effect_json,
        reason_template=payload.reason_template,
        created_by=payload.created_by,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/evaluate-auto-assign")
def evaluate_auto_assign(
    queue_key: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    queue_repository = get_queue_repository()
    item = queue_repository.get_item(queue_key, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="queue item not found")

    service = QueueAssignmentPolicyService(db)
    decision = service.evaluate_auto_assign(queue_key=queue_key, item=item)
    return {
        "allowed": decision.allowed,
        "blocked": decision.blocked,
        "requires_human_review": decision.requires_human_review,
        "requires_governance_approval": decision.requires_governance_approval,
        "suppression_active": decision.suppression_active,
        "suppressed_until": decision.suppressed_until,
        "reasons": decision.reasons,
        "applied_rule_keys": decision.applied_rule_keys,
        "policy_snapshot_json": decision.policy_snapshot_json,
    }


@router.get("/reassign/preview")
def preview_reassign(
    queue_key: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    service = QueueReassignService(
        db,
        queue_repository=get_queue_repository(),
    )
    try:
        return service.preview(queue_key=queue_key, item_id=item_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reassign/execute")
def execute_reassign(
    payload: QueueReassignExecuteIn,
    db: Session = Depends(get_db),
):
    service = QueueReassignService(
        db,
        queue_repository=get_queue_repository(),
    )
    try:
        return service.execute(
            queue_key=payload.queue_key,
            item_id=payload.item_id,
            new_assignee_id=payload.new_assignee_id,
            actor_id=payload.actor_id,
            expected_version=payload.expected_version,
            reason=payload.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        message = str(e).lower()
        if "version" in message or "conflict" in message:
            raise HTTPException(status_code=409, detail=str(e))
        raise
12) BACKEND — ROUTER WIRING
backend/app/api/api_v1/api.py
from app.api.routes import queue_assignment_policy
và:
api_router.include_router(queue_assignment_policy.router)
13) BACKEND — MIGRATION
backend/alembic/versions/004_phase3_assignment_guardrails.py
"""phase3 assignment guardrails

Revision ID: 004_phase3_assignment_guardrails
Revises: 003_phase3_auto_assign
Create Date: 2026-04-12 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "004_phase3_assignment_guardrails"
down_revision = "003_phase3_auto_assign"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "queue_assignment_guardrail_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("suppressed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suppression_reason", sa.Text(), nullable=True),
        sa.Column("auto_assign_attempt_count_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_assign_failure_count_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reassign_count_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assignment_flip_count_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_auto_assign_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_auto_assign_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_assignment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reassignment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("human_review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("human_review_reason", sa.Text(), nullable=True),
        sa.Column("governance_approval_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("governance_approval_reason", sa.Text(), nullable=True),
        sa.Column("policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("item_id"),
    )
    op.create_index("ix_queue_assignment_guardrail_state_queue_key", "queue_assignment_guardrail_state", ["queue_key"])
    op.create_index("ix_queue_assignment_guardrail_state_item_id", "queue_assignment_guardrail_state", ["item_id"])
    op.create_index(
        "ix_queue_assignment_guardrail_state_suppressed_until",
        "queue_assignment_guardrail_state",
        ["suppressed_until"],
    )

    op.create_table(
        "queue_assignment_policy_rule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("rule_key", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("scope_type", sa.String(length=50), nullable=False, server_default="global"),
        sa.Column("scope_value", sa.String(length=120), nullable=True),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("condition_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effect_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason_template", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("rule_key"),
    )
    op.create_index("ix_queue_assignment_policy_rule_queue_key", "queue_assignment_policy_rule", ["queue_key"])
    op.create_index("ix_queue_assignment_policy_rule_rule_key", "queue_assignment_policy_rule", ["rule_key"])
    op.create_index("ix_queue_assignment_policy_rule_scope_value", "queue_assignment_policy_rule", ["scope_value"])

    op.create_table(
        "queue_assignment_governance_decision",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("decision_type", sa.String(length=80), nullable=False),
        sa.Column("decision_status", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("policy_rule_key", sa.String(length=120), nullable=True),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_queue_assignment_governance_decision_queue_key",
        "queue_assignment_governance_decision",
        ["queue_key"],
    )
    op.create_index(
        "ix_queue_assignment_governance_decision_item_id",
        "queue_assignment_governance_decision",
        ["item_id"],
    )
    op.create_index(
        "ix_queue_assignment_governance_decision_decision_type",
        "queue_assignment_governance_decision",
        ["decision_type"],
    )
    op.create_index(
        "ix_queue_assignment_governance_decision_decision_status",
        "queue_assignment_governance_decision",
        ["decision_status"],
    )
    op.create_index(
        "ix_queue_assignment_governance_decision_policy_rule_key",
        "queue_assignment_governance_decision",
        ["policy_rule_key"],
    )


def downgrade():
    op.drop_index("ix_queue_assignment_governance_decision_policy_rule_key", table_name="queue_assignment_governance_decision")
    op.drop_index("ix_queue_assignment_governance_decision_decision_status", table_name="queue_assignment_governance_decision")
    op.drop_index("ix_queue_assignment_governance_decision_decision_type", table_name="queue_assignment_governance_decision")
    op.drop_index("ix_queue_assignment_governance_decision_item_id", table_name="queue_assignment_governance_decision")
    op.drop_index("ix_queue_assignment_governance_decision_queue_key", table_name="queue_assignment_governance_decision")
    op.drop_table("queue_assignment_governance_decision")

    op.drop_index("ix_queue_assignment_policy_rule_scope_value", table_name="queue_assignment_policy_rule")
    op.drop_index("ix_queue_assignment_policy_rule_rule_key", table_name="queue_assignment_policy_rule")
    op.drop_index("ix_queue_assignment_policy_rule_queue_key", table_name="queue_assignment_policy_rule")
    op.drop_table("queue_assignment_policy_rule")

    op.drop_index("ix_queue_assignment_guardrail_state_suppressed_until", table_name="queue_assignment_guardrail_state")
    op.drop_index("ix_queue_assignment_guardrail_state_item_id", table_name="queue_assignment_guardrail_state")
    op.drop_index("ix_queue_assignment_guardrail_state_queue_key", table_name="queue_assignment_guardrail_state")
    op.drop_table("queue_assignment_guardrail_state")
14) BACKEND — TESTS
backend/tests/services/test_queue_assignment_policy_service.py
from app.repositories.queue_assignment_policy_rule_repository import QueueAssignmentPolicyRuleRepository
from app.services.queue_assignment_policy_service import QueueAssignmentPolicyService


class Item:
    id = "item_critical_1"
    severity = "critical"
    provider = "veo"
    project_id = "project_a"
    item_type = "render_job"


def test_critical_item_requires_governance_approval(db_session):
    repo = QueueAssignmentPolicyRuleRepository(db_session)
    repo.create(
        queue_key="render_ops",
        rule_key="critical_requires_governance",
        enabled=True,
        priority=10,
        scope_type="severity",
        scope_value="critical",
        action_type="require_governance_approval",
        condition_json={"severity": "critical"},
        effect_json={"block_auto_assign": True},
        reason_template="critical severity requires governance approval",
        created_by="test",
    )
    db_session.commit()

    service = QueueAssignmentPolicyService(db_session)
    decision = service.evaluate_auto_assign(queue_key="render_ops", item=Item())

    assert decision.requires_governance_approval is True
    assert decision.blocked is True
    assert decision.allowed is False
backend/tests/services/test_queue_reassign_policy_service.py
from datetime import datetime, timedelta, timezone

from app.services.queue_reassign_policy_service import QueueReassignPolicyService
from app.repositories.queue_assignment_guardrail_state_repository import QueueAssignmentGuardrailStateRepository


class Item:
    id = "item_1"


def test_reassign_blocked_when_recent_assignment(db_session):
    repo = QueueAssignmentGuardrailStateRepository(db_session)
    state = repo.get_or_create("render_ops", "item_1")
    state.last_assignment_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    db_session.commit()

    service = QueueReassignPolicyService(db_session)
    decision = service.evaluate(queue_key="render_ops", item=Item(), min_seconds_since_last_assignment=300)

    assert decision.blocked is True
    assert any("min_assignment_age_not_met" in r for r in decision.reasons)
backend/tests/services/test_queue_assignment_guardrail_state_service.py
from app.repositories.queue_assignment_guardrail_state_repository import QueueAssignmentGuardrailStateRepository
from app.services.queue_assignment_guardrail_state_service import QueueAssignmentGuardrailStateService


def test_repeated_failure_guard_sets_suppression(db_session):
    service = QueueAssignmentGuardrailStateService(db_session)

    service.record_auto_assign_failure(
        queue_key="render_ops",
        item_id="item_1",
        reason="no_candidate",
        suppress_seconds=60,
    )
    service.record_auto_assign_failure(
        queue_key="render_ops",
        item_id="item_1",
        reason="no_candidate",
        suppress_seconds=60,
    )
    service.record_auto_assign_failure(
        queue_key="render_ops",
        item_id="item_1",
        reason="no_candidate",
        suppress_seconds=60,
    )

    applied = service.apply_repeated_failure_guard(
        queue_key="render_ops",
        item_id="item_1",
        failure_threshold=3,
        suppress_seconds=1800,
    )

    repo = QueueAssignmentGuardrailStateRepository(db_session)
    state = repo.get("render_ops", "item_1")

    assert applied is True
    assert state is not None
    assert state.suppressed_until is not None
    assert state.suppression_reason == "repeated_auto_assign_failures"
15) FRONTEND — TYPES
frontend/src/types/queueAssignmentPolicy.ts
export type QueueGuardrailDecision = {
  allowed: boolean;
  blocked: boolean;
  requires_human_review: boolean;
  requires_governance_approval: boolean;
  suppression_active: boolean;
  suppressed_until: string | null;
  reasons: string[];
  applied_rule_keys: string[];
  policy_snapshot_json?: Record<string, unknown> | null;
};

export type QueueReassignPreview = {
  queue_key: string;
  item_id: string;
  allowed: boolean;
  blocked: boolean;
  reasons: string[];
  current_assignee_id: string | null;
  reassign_count_24h: number;
  assignment_flip_count_24h: number;
  min_seconds_since_last_assignment_required?: number | null;
  seconds_since_last_assignment?: number | null;
};

export type QueueReassignExecuteRequest = {
  queue_key: string;
  item_id: string;
  new_assignee_id: string;
  actor_id: string;
  expected_version?: number | null;
  reason?: string | null;
};

export type QueueReassignExecuteResponse = {
  queue_key: string;
  item_id: string;
  reassigned: boolean;
  previous_assignee_id: string | null;
  new_assignee_id: string | null;
  action_id: string | null;
  reason: string | null;
  guardrails_applied: string[];
  executed_at: string;
};
16) FRONTEND — API
frontend/src/api/queueAssignmentPolicy.ts
import { apiClient } from "./client";
import {
  QueueGuardrailDecision,
  QueueReassignExecuteRequest,
  QueueReassignExecuteResponse,
  QueueReassignPreview,
} from "../types/queueAssignmentPolicy";

export async function evaluateAutoAssignPolicy(queueKey: string, itemId: string) {
  const res = await apiClient.get<QueueGuardrailDecision>("/queue/assignment-policy/evaluate-auto-assign", {
    params: { queue_key: queueKey, item_id: itemId },
  });
  return res.data;
}

export async function previewReassign(queueKey: string, itemId: string) {
  const res = await apiClient.get<QueueReassignPreview>("/queue/assignment-policy/reassign/preview", {
    params: { queue_key: queueKey, item_id: itemId },
  });
  return res.data;
}

export async function executeReassign(payload: QueueReassignExecuteRequest) {
  const res = await apiClient.post<QueueReassignExecuteResponse>(
    "/queue/assignment-policy/reassign/execute",
    payload,
  );
  return res.data;
}
17) FRONTEND — GUARDRAIL PANEL
frontend/src/components/queue/AssignmentGuardrailPanel.tsx
import React, { useEffect, useState } from "react";
import { evaluateAutoAssignPolicy } from "../../api/queueAssignmentPolicy";
import { QueueGuardrailDecision } from "../../types/queueAssignmentPolicy";

type Props = {
  queueKey: string;
  itemId: string;
  onToast: (input: { title: string; description?: string; variant?: "default" | "destructive" }) => void;
};

export function AssignmentGuardrailPanel({ queueKey, itemId, onToast }: Props) {
  const [decision, setDecision] = useState<QueueGuardrailDecision | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await evaluateAutoAssignPolicy(queueKey, itemId);
      setDecision(data);
    } catch (err: any) {
      onToast({
        title: "Không tải được policy guardrails",
        description: err?.response?.data?.detail || "Unknown error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [queueKey, itemId]);

  if (loading && !decision) {
    return <div className="rounded-xl border p-4">Loading guardrails...</div>;
  }

  if (!decision) {
    return <div className="rounded-xl border p-4">No guardrail decision.</div>;
  }

  return (
    <div className="rounded-xl border p-4 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Assignment Guardrails</h3>
        <button className="border rounded px-3 py-1" onClick={load}>Refresh</button>
      </div>

      <div className="text-sm space-y-1">
        <div><strong>Allowed:</strong> {String(decision.allowed)}</div>
        <div><strong>Blocked:</strong> {String(decision.blocked)}</div>
        <div><strong>Human review:</strong> {String(decision.requires_human_review)}</div>
        <div><strong>Governance approval:</strong> {String(decision.requires_governance_approval)}</div>
        <div><strong>Suppression active:</strong> {String(decision.suppression_active)}</div>
        <div><strong>Suppressed until:</strong> {decision.suppressed_until || "-"}</div>
      </div>

      {decision.reasons.length > 0 && (
        <div className="text-xs text-gray-600">
          {decision.reasons.join(" | ")}
        </div>
      )}

      {decision.applied_rule_keys.length > 0 && (
        <div className="text-xs text-gray-500">
          Rules: {decision.applied_rule_keys.join(", ")}
        </div>
      )}
    </div>
  );
}
18) FRONTEND — REASSIGN PANEL
frontend/src/components/queue/ReassignActionPanel.tsx
import React, { useEffect, useState } from "react";
import { executeReassign, previewReassign } from "../../api/queueAssignmentPolicy";
import { QueueReassignPreview } from "../../types/queueAssignmentPolicy";

type Props = {
  queueKey: string;
  itemId: string;
  itemVersion?: number;
  actorId: string;
  onToast: (input: { title: string; description?: string; variant?: "default" | "destructive" }) => void;
  onDone?: () => void;
};

export function ReassignActionPanel({
  queueKey,
  itemId,
  itemVersion,
  actorId,
  onToast,
  onDone,
}: Props) {
  const [preview, setPreview] = useState<QueueReassignPreview | null>(null);
  const [newAssigneeId, setNewAssigneeId] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await previewReassign(queueKey, itemId);
      setPreview(data);
    } catch (err: any) {
      onToast({
        title: "Không tải được preview reassign",
        description: err?.response?.data?.detail || "Unknown error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }

  async function submit() {
    if (!newAssigneeId.trim()) {
      onToast({
        title: "Thiếu assignee",
        description: "Nhập new assignee id",
        variant: "destructive",
      });
      return;
    }

    setSubmitting(true);
    try {
      const res = await executeReassign({
        queue_key: queueKey,
        item_id: itemId,
        new_assignee_id: newAssigneeId.trim(),
        actor_id: actorId,
        expected_version: itemVersion ?? null,
        reason: "manual_reassign_from_ui",
      });

      if (res.reassigned) {
        onToast({
          title: "Reassign thành công",
          description: `${res.previous_assignee_id || "-"} → ${res.new_assignee_id || "-"}`,
        });
        onDone?.();
        await load();
      } else {
        onToast({
          title: "Reassign bị chặn",
          description: res.reason || "reassign_blocked",
        });
      }
    } catch (err: any) {
      onToast({
        title: "Reassign thất bại",
        description: err?.response?.data?.detail || "Unknown error",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    load();
  }, [queueKey, itemId]);

  return (
    <div className="rounded-xl border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Reassign</h3>
        <button className="border rounded px-3 py-1" onClick={load} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {preview && (
        <div className="text-sm space-y-1">
          <div><strong>Allowed:</strong> {String(preview.allowed)}</div>
          <div><strong>Current assignee:</strong> {preview.current_assignee_id || "-"}</div>
          <div><strong>Reassign count 24h:</strong> {preview.reassign_count_24h}</div>
          <div><strong>Flip count 24h:</strong> {preview.assignment_flip_count_24h}</div>
          <div><strong>Reasons:</strong> {preview.reasons.join(" | ") || "-"}</div>
        </div>
      )}

      <input
        className="w-full border rounded px-3 py-2"
        placeholder="New assignee id"
        value={newAssigneeId}
        onChange={(e) => setNewAssigneeId(e.target.value)}
      />

      <button
        className="rounded bg-black text-white px-4 py-2 disabled:opacity-50"
        onClick={submit}
        disabled={submitting}
      >
        {submitting ? "Đang reassign..." : "Run Reassign"}
      </button>
    </div>
  );
}
19) FRONTEND — PATCH QUEUE PANEL
frontend/src/components/queue/OperatorQueuePanel.tsx
Thêm import:
import { AssignmentGuardrailPanel } from "./AssignmentGuardrailPanel";
import { ReassignActionPanel } from "./ReassignActionPanel";
Trong phần detail/action sidebar của item:
<AssignmentGuardrailPanel
  queueKey={selectedItem.queue_key}
  itemId={selectedItem.item_id}
  onToast={onToast}
/>

<ReassignActionPanel
  queueKey={selectedItem.queue_key}
  itemId={selectedItem.item_id}
  itemVersion={selectedItem.version}
  actorId={currentActorId}
  onToast={onToast}
  onDone={() => {
    refetchQueue();
    refetchItemDetail?.();
  }}
/>
20) MAP RẤT NGẮN KHI GẮN VÀO REPO THẬT
Đây là phần quan trọng nhất để patch chạy sạch trong repo production.
A. Guardrail state phải map vào item lifecycle thật
Nếu repo của bạn đã có item state/read model rồi, nên map thêm các field:
suppressed_until
suppression_reason
human_review_required
governance_approval_required
last_assignment_at
last_reassignment_at
Nếu không muốn nhét trực tiếp vào queue item chính thì giữ bảng riêng như patch này.
B. Rule engine nên ưu tiên deterministic trước
Bản này dùng:
scope_type
condition_json
effect_json
Đủ để chạy production sớm.
Chưa cần DSL quá phức tạp.
Ví dụ rule rất thực dụng:
critical severity cần approval
{
  "queue_key": "render_ops",
  "rule_key": "critical_requires_governance",
  "enabled": true,
  "priority": 10,
  "scope_type": "severity",
  "scope_value": "critical",
  "action_type": "require_governance_approval",
  "condition_json": {"severity": "critical"},
  "effect_json": {"block_auto_assign": true},
  "reason_template": "critical severity requires governance approval"
}
fail 3 lần thì suppress
{
  "queue_key": "render_ops",
  "rule_key": "repeated_failure_suppress",
  "enabled": true,
  "priority": 20,
  "scope_type": "global",
  "scope_value": null,
  "action_type": "suppress",
  "condition_json": {"auto_assign_failure_count_24h": {"gte": 3}},
  "effect_json": {"suppress_seconds": 1800},
  "reason_template": "repeated auto assign failures"
}
C. Reassign policy nên map thêm actor permission
Trong production thật, trước khi reassign nên kiểm tra:
actor có quyền reassign không
actor có quyền vượt guardrail không
actor có quyền force reassign cho critical item không
Bản patch này chưa ép RBAC sâu để giữ file gọn.
D. Governance integration thật
Nếu repo Phase 3 governance của bạn đã có:
change_request
approval
execution attempt
thì item bị requires_governance_approval nên nối thành:
tạo governance change request
item chuyển trạng thái pending_assignment_approval
chỉ khi approved mới gọi auto_assign.execute(...) hoặc reassign.execute(...)
E. No-thrash policy thật nên dựa trên assignment action history
Hiện patch dùng counter trong guardrail state.
Production hơn nên derive thêm từ:
queue_assignment_action
audit log
queue assign events
operator actions timeline
Mục tiêu là phát hiện:
cùng 1 item đổi người quá nhiều
cùng 2 operator bị ping-pong
item quay lại assignee cũ trong thời gian rất ngắn
F. Counter 24h hiện là materialized state đơn giản
Bản này giữ ngắn để paste nhanh.
Production chuẩn hơn:
worker reset counters theo rolling window
hoặc query từ event store/materialized rollups thật
hoặc refresh mỗi 5–15 phút
21) KẾT QUẢ SAU PATCH NÀY
Sau bản này queue tăng thêm 5 lớp rất mạnh:
1. Suppression windows
Hệ biết:
item nào đang bị suppress
đến khi nào mới được auto-assign lại
vì sao đang bị suppress
2. Reassign policy
Hệ biết:
item nào được reassign
item nào vừa mới assign nên chưa được đổi
item nào đã flip quá nhiều nên phải dừng
3. Governance guardrails
Hệ biết:
item critical/sensitive/governance-bound không được auto-assign thẳng
item nào cần pending approval trước
4. Repeated-failure guard
Hệ biết:
item đã fail auto-assign nhiều lần thì không tiếp tục spam
chuyển sang suppress hoặc escalate
5. No-thrash control
Hệ tránh:
assignment churn
ping-pong reassign
queue automation gây nhiễu vận hành
Tức là queue chuyển từ:
controlled execution
sang:
policy-governed controlled execution
22) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
add 3 models
register imports vào base
add 3 repositories
add schemas
add assignment policy service
add guardrail state service
add reassign policy service
patch auto-assign service
add reassign service
add routes
wire router
add migration
add tests
Frontend
add types
add APIs
add AssignmentGuardrailPanel
add ReassignActionPanel
patch queue panel
23) BƯỚC MẠNH NHẤT NGAY SAU BẢN NÀY
Bước tiếp theo mạnh nhất là:
PHASE 3 — HUMAN REVIEW QUEUE + APPROVAL WORKFLOW FOR ASSIGNMENT DECISIONS + POLICY OVERRIDE AUDIT
Vì lúc đó hệ sẽ đi tiếp từ:
biết item nào cần review / approval
sang:
có queue riêng cho human review
có approve / reject / override cho assignment decision
có policy override bởi supervisor
có full audit vì sao override
có escalation SLA cho pending review / pending approval
Tức là lúc đó queue chuyển từ:
policy-governed controlled execution
sang:
human-in-the-loop governed execution
Tôi có thể viết tiếp ngay bản đó cũng theo đúng format file-by-file paste-ready.
PHASE 3 — HUMAN REVIEW QUEUE + APPROVAL WORKFLOW FOR ASSIGNMENT DECISIONS + POLICY OVERRIDE AUDIT Vì lúc đó hệ sẽ đi tiếp từ: biết item nào cần review / approval sang: có queue riêng cho human review có approve / reject / override cho assignment decision có policy override bởi supervisor có full audit vì sao override có escalation SLA cho pending review / pending approval Tức là lúc đó queue chuyển từ: policy-governed controlled execution sang: human-in-the-loop governed execution Tôi có thể viết tiếp ngay bản đó cũng theo đúng format file-by-file paste-ready.
Đã suy nghĩ trong vài giây
Dưới đây là bản:
PHASE 3 — HUMAN REVIEW QUEUE + APPROVAL WORKFLOW FOR ASSIGNMENT DECISIONS + POLICY OVERRIDE AUDIT
Mục tiêu của bản này là nâng queue từ:
biết item nào cần review / approval
sang:
có queue riêng cho human review
có approve / reject / override cho assignment decision
có policy override bởi supervisor
có full audit vì sao override
có escalation SLA cho pending review / pending approval
Tức là queue chuyển từ:
policy-governed controlled execution
sang:
human-in-the-loop governed execution
Tôi viết theo đúng kiểu file-by-file paste-ready, bám repo production, không tái cấu trúc vô cớ.
1) THIẾT KẾ NGẮN GỌN
Bản này thêm 5 lớp:
A. Human review queue
Một item khi bị guardrail chặn hoặc cần human review sẽ được đưa vào hàng đợi riêng:
pending_review
pending_approval
escalated
resolved
B. Approval workflow
Supervisor/reviewer có thể:
approve
reject
request_changes
override_policy_and_assign
override_policy_and_reassign
C. Policy override audit
Mọi override phải có:
actor
reason
rule keys bị vượt
before / after decision
target assignee nếu có
D. Escalation SLA
Nếu item pending review quá lâu thì:
đánh dấu breach
tăng escalation level
emit notification
đưa vào queue ưu tiên
E. Review resolution bridge
Sau khi approve:
gọi lại auto-assign
hoặc assign/reassign trực tiếp theo quyết định reviewer
đồng bộ guardrail state + audit trail
2) BACKEND — MODELS
backend/app/models/queue_assignment_review_case.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueAssignmentReviewCase(Base):
    __tablename__ = "queue_assignment_review_case"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    case_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # human_review | governance_approval | override_review

    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="pending_review")
    # pending_review | pending_approval | approved | rejected | changes_requested | overridden | resolved | escalated

    source_decision_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    source_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    priority_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    assigned_reviewer_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    requested_by: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    resolved_by: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    requires_supervisor_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    first_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
backend/app/models/queue_assignment_review_action.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueAssignmentReviewAction(Base):
    __tablename__ = "queue_assignment_review_action"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    review_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    action_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # approve | reject | request_changes | assign | reassign | override_policy | escalate | comment

    actor_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    previous_assignee_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    new_assignee_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
backend/app/models/queue_policy_override_audit.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueuePolicyOverrideAudit(Base):
    __tablename__ = "queue_policy_override_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    queue_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    review_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    override_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # override_auto_assign_block | override_reassign_block | override_human_review | override_governance_requirement

    actor_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(100), nullable=True)

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    overridden_rule_keys_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    before_decision_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_decision_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    execution_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
3) BACKEND — REGISTER IMPORTS
backend/app/db/base.py
Thêm import:
from app.models.queue_assignment_review_case import QueueAssignmentReviewCase
from app.models.queue_assignment_review_action import QueueAssignmentReviewAction
from app.models.queue_policy_override_audit import QueuePolicyOverrideAudit
4) BACKEND — REPOSITORIES
backend/app/repositories/queue_assignment_review_case_repository.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.models.queue_assignment_review_case import QueueAssignmentReviewCase


class QueueAssignmentReviewCaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        queue_key: str,
        item_id: str,
        case_type: str,
        status: str,
        source_decision_type: str | None = None,
        source_reason: str | None = None,
        priority_score: int = 50,
        escalation_level: int = 0,
        assigned_reviewer_id: str | None = None,
        requested_by: str | None = None,
        requires_supervisor_override: bool = False,
        sla_due_at: datetime | None = None,
        metadata_json: dict | None = None,
    ) -> QueueAssignmentReviewCase:
        obj = QueueAssignmentReviewCase(
            queue_key=queue_key,
            item_id=item_id,
            case_type=case_type,
            status=status,
            source_decision_type=source_decision_type,
            source_reason=source_reason,
            priority_score=priority_score,
            escalation_level=escalation_level,
            assigned_reviewer_id=assigned_reviewer_id,
            requested_by=requested_by,
            requires_supervisor_override=requires_supervisor_override,
            sla_due_at=sla_due_at,
            metadata_json=metadata_json,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def get(self, review_case_id: str) -> QueueAssignmentReviewCase | None:
        stmt = select(QueueAssignmentReviewCase).where(QueueAssignmentReviewCase.id == review_case_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def find_open_for_item(self, queue_key: str, item_id: str) -> QueueAssignmentReviewCase | None:
        stmt = (
            select(QueueAssignmentReviewCase)
            .where(
                QueueAssignmentReviewCase.queue_key == queue_key,
                QueueAssignmentReviewCase.item_id == item_id,
                QueueAssignmentReviewCase.status.in_(
                    ["pending_review", "pending_approval", "escalated", "changes_requested"]
                ),
            )
            .order_by(desc(QueueAssignmentReviewCase.created_at))
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_pending(
        self,
        *,
        queue_key: str | None = None,
        assigned_reviewer_id: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 100,
    ) -> list[QueueAssignmentReviewCase]:
        stmt = select(QueueAssignmentReviewCase)

        if queue_key:
            stmt = stmt.where(QueueAssignmentReviewCase.queue_key == queue_key)
        if assigned_reviewer_id:
            stmt = stmt.where(QueueAssignmentReviewCase.assigned_reviewer_id == assigned_reviewer_id)
        if statuses:
            stmt = stmt.where(QueueAssignmentReviewCase.status.in_(statuses))

        stmt = stmt.order_by(
            desc(QueueAssignmentReviewCase.escalation_level),
            desc(QueueAssignmentReviewCase.priority_score),
            asc(QueueAssignmentReviewCase.created_at),
        ).limit(limit)

        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/queue_assignment_review_action_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.queue_assignment_review_action import QueueAssignmentReviewAction


class QueueAssignmentReviewActionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        review_case_id,
        queue_key: str,
        item_id: str,
        action_type: str,
        actor_id: str,
        reason: str | None = None,
        from_status: str | None = None,
        to_status: str | None = None,
        previous_assignee_id: str | None = None,
        new_assignee_id: str | None = None,
        metadata_json: dict | None = None,
    ) -> QueueAssignmentReviewAction:
        obj = QueueAssignmentReviewAction(
            review_case_id=review_case_id,
            queue_key=queue_key,
            item_id=item_id,
            action_type=action_type,
            actor_id=actor_id,
            reason=reason,
            from_status=from_status,
            to_status=to_status,
            previous_assignee_id=previous_assignee_id,
            new_assignee_id=new_assignee_id,
            metadata_json=metadata_json,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_for_case(self, review_case_id: str, limit: int = 100) -> list[QueueAssignmentReviewAction]:
        stmt = (
            select(QueueAssignmentReviewAction)
            .where(QueueAssignmentReviewAction.review_case_id == review_case_id)
            .order_by(desc(QueueAssignmentReviewAction.created_at))
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/queue_policy_override_audit_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.queue_policy_override_audit import QueuePolicyOverrideAudit


class QueuePolicyOverrideAuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        queue_key: str,
        item_id: str,
        review_case_id=None,
        override_type: str,
        actor_id: str,
        actor_role: str | None,
        reason: str,
        overridden_rule_keys_json: list | None = None,
        before_decision_json: dict | None = None,
        after_decision_json: dict | None = None,
        execution_payload_json: dict | None = None,
    ) -> QueuePolicyOverrideAudit:
        obj = QueuePolicyOverrideAudit(
            queue_key=queue_key,
            item_id=item_id,
            review_case_id=review_case_id,
            override_type=override_type,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
            overridden_rule_keys_json=overridden_rule_keys_json,
            before_decision_json=before_decision_json,
            after_decision_json=after_decision_json,
            execution_payload_json=execution_payload_json,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def list_for_item(self, queue_key: str, item_id: str, limit: int = 50) -> list[QueuePolicyOverrideAudit]:
        stmt = (
            select(QueuePolicyOverrideAudit)
            .where(
                QueuePolicyOverrideAudit.queue_key == queue_key,
                QueuePolicyOverrideAudit.item_id == item_id,
            )
            .order_by(desc(QueuePolicyOverrideAudit.created_at))
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
5) BACKEND — SCHEMAS
backend/app/schemas/queue_assignment_review.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class QueueAssignmentReviewCaseOut(BaseModel):
    id: str
    queue_key: str
    item_id: str
    case_type: str
    status: str
    source_decision_type: str | None
    source_reason: str | None
    priority_score: int
    escalation_level: int
    assigned_reviewer_id: str | None
    requested_by: str | None
    resolved_by: str | None
    requires_supervisor_override: bool
    sla_due_at: datetime | None
    first_review_at: datetime | None
    resolved_at: datetime | None
    metadata_json: dict | None

    class Config:
        from_attributes = True


class QueueAssignmentReviewActionOut(BaseModel):
    id: str
    review_case_id: str
    queue_key: str
    item_id: str
    action_type: str
    actor_id: str
    reason: str | None
    from_status: str | None
    to_status: str | None
    previous_assignee_id: str | None
    new_assignee_id: str | None
    metadata_json: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class QueueCreateReviewCaseIn(BaseModel):
    queue_key: str
    item_id: str
    case_type: str = "human_review"
    status: str = "pending_review"
    source_decision_type: str | None = None
    source_reason: str | None = None
    priority_score: int = 50
    assigned_reviewer_id: str | None = None
    requested_by: str | None = None
    requires_supervisor_override: bool = False
    sla_due_at: datetime | None = None
    metadata_json: dict | None = None


class QueueReviewDecisionIn(BaseModel):
    actor_id: str
    actor_role: str | None = None
    decision: str
    # approve | reject | request_changes | override_policy_and_assign | override_policy_and_reassign
    reason: str = Field(min_length=3)
    target_assignee_id: str | None = None
    expected_item_version: int | None = None
    metadata_json: dict | None = None


class QueuePolicyOverrideAuditOut(BaseModel):
    id: str
    queue_key: str
    item_id: str
    review_case_id: str | None
    override_type: str
    actor_id: str
    actor_role: str | None
    reason: str
    overridden_rule_keys_json: list | None
    before_decision_json: dict | None
    after_decision_json: dict | None
    execution_payload_json: dict | None
    created_at: datetime

    class Config:
        from_attributes = True
6) BACKEND — REVIEW QUEUE SERVICE
backend/app/services/queue_assignment_review_queue_service.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.repositories.queue_assignment_review_case_repository import QueueAssignmentReviewCaseRepository
from app.repositories.queue_assignment_review_action_repository import QueueAssignmentReviewActionRepository
from app.services.queue_assignment_guardrail_state_service import QueueAssignmentGuardrailStateService


class QueueAssignmentReviewQueueService:
    def __init__(
        self,
        db: Session,
        *,
        notification_service=None,
        audit_log_service=None,
    ) -> None:
        self.db = db
        self.notification_service = notification_service
        self.audit_log_service = audit_log_service
        self.case_repo = QueueAssignmentReviewCaseRepository(db)
        self.action_repo = QueueAssignmentReviewActionRepository(db)
        self.guardrail_state_service = QueueAssignmentGuardrailStateService(db)

    def create_from_guardrail_decision(
        self,
        *,
        queue_key: str,
        item_id: str,
        requested_by: str | None,
        source_decision_type: str,
        source_reason: str | None,
        requires_supervisor_override: bool = False,
        priority_score: int = 50,
        assigned_reviewer_id: str | None = None,
        sla_minutes: int = 30,
        metadata_json: dict | None = None,
    ):
        existing = self.case_repo.find_open_for_item(queue_key, item_id)
        if existing is not None:
            return existing

        case_type = "governance_approval" if source_decision_type == "governance_approval_required" else "human_review"
        status = "pending_approval" if case_type == "governance_approval" else "pending_review"

        case = self.case_repo.create(
            queue_key=queue_key,
            item_id=item_id,
            case_type=case_type,
            status=status,
            source_decision_type=source_decision_type,
            source_reason=source_reason,
            priority_score=priority_score,
            assigned_reviewer_id=assigned_reviewer_id,
            requested_by=requested_by,
            requires_supervisor_override=requires_supervisor_override,
            sla_due_at=datetime.now(timezone.utc) + timedelta(minutes=sla_minutes),
            metadata_json=metadata_json,
        )

        self.action_repo.create(
            review_case_id=case.id,
            queue_key=queue_key,
            item_id=item_id,
            action_type="comment",
            actor_id=requested_by or "system",
            reason=source_reason or "review case created",
            from_status=None,
            to_status=status,
            metadata_json={"source_decision_type": source_decision_type},
        )

        if self.notification_service:
            self.notification_service.emit(
                event_type="queue.review_case.created",
                payload={
                    "review_case_id": str(case.id),
                    "queue_key": queue_key,
                    "item_id": item_id,
                    "status": status,
                    "assigned_reviewer_id": assigned_reviewer_id,
                },
            )

        if self.audit_log_service:
            self.audit_log_service.log(
                event_type="queue.review_case.created",
                actor_id=requested_by or "system",
                entity_type="queue_item",
                entity_id=item_id,
                payload={
                    "review_case_id": str(case.id),
                    "queue_key": queue_key,
                    "source_decision_type": source_decision_type,
                    "status": status,
                },
            )

        self.db.flush()
        return case
7) BACKEND — REVIEW DECISION / OVERRIDE WORKFLOW SERVICE
backend/app/services/queue_assignment_review_workflow_service.py
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.repositories.queue_assignment_review_case_repository import QueueAssignmentReviewCaseRepository
from app.repositories.queue_assignment_review_action_repository import QueueAssignmentReviewActionRepository
from app.repositories.queue_policy_override_audit_repository import QueuePolicyOverrideAuditRepository
from app.services.interfaces.queue_repository import QueueRepositoryProtocol
from app.services.queue_assignment_guardrail_state_service import QueueAssignmentGuardrailStateService
from app.services.queue_assignment_policy_service import QueueAssignmentPolicyService
from app.services.queue_reassign_service import QueueReassignService


class QueueAssignmentReviewWorkflowService:
    def __init__(
        self,
        db: Session,
        *,
        queue_repository: QueueRepositoryProtocol,
        audit_log_service=None,
        notification_service=None,
        auto_assign_service=None,
    ) -> None:
        self.db = db
        self.queue_repository = queue_repository
        self.audit_log_service = audit_log_service
        self.notification_service = notification_service
        self.auto_assign_service = auto_assign_service

        self.case_repo = QueueAssignmentReviewCaseRepository(db)
        self.action_repo = QueueAssignmentReviewActionRepository(db)
        self.override_repo = QueuePolicyOverrideAuditRepository(db)
        self.guardrail_state_service = QueueAssignmentGuardrailStateService(db)
        self.policy_service = QueueAssignmentPolicyService(db)
        self.reassign_service = QueueReassignService(
            db,
            queue_repository=queue_repository,
            audit_log_service=audit_log_service,
            notification_service=notification_service,
        )

    def decide(
        self,
        *,
        review_case_id: str,
        actor_id: str,
        actor_role: str | None,
        decision: str,
        reason: str,
        target_assignee_id: str | None = None,
        expected_item_version: int | None = None,
        metadata_json: dict | None = None,
    ):
        case = self.case_repo.get(review_case_id)
        if case is None:
            raise ValueError("review case not found")

        item = self.queue_repository.get_item(case.queue_key, case.item_id)
        if item is None:
            raise ValueError("queue item not found")

        old_status = case.status
        previous_assignee_id = getattr(item, "assignee_id", None)

        if case.first_review_at is None:
            case.first_review_at = datetime.now(timezone.utc)

        if decision == "approve":
            case.status = "approved"
            case.resolved_by = actor_id
            case.resolved_at = datetime.now(timezone.utc)

            self.guardrail_state_service.clear_review_flags(queue_key=case.queue_key, item_id=case.item_id)

            self.action_repo.create(
                review_case_id=case.id,
                queue_key=case.queue_key,
                item_id=case.item_id,
                action_type="approve",
                actor_id=actor_id,
                reason=reason,
                from_status=old_status,
                to_status=case.status,
                metadata_json=metadata_json,
            )

        elif decision == "reject":
            case.status = "rejected"
            case.resolved_by = actor_id
            case.resolved_at = datetime.now(timezone.utc)

            self.action_repo.create(
                review_case_id=case.id,
                queue_key=case.queue_key,
                item_id=case.item_id,
                action_type="reject",
                actor_id=actor_id,
                reason=reason,
                from_status=old_status,
                to_status=case.status,
                metadata_json=metadata_json,
            )

        elif decision == "request_changes":
            case.status = "changes_requested"

            self.action_repo.create(
                review_case_id=case.id,
                queue_key=case.queue_key,
                item_id=case.item_id,
                action_type="request_changes",
                actor_id=actor_id,
                reason=reason,
                from_status=old_status,
                to_status=case.status,
                metadata_json=metadata_json,
            )

        elif decision == "override_policy_and_assign":
            if not target_assignee_id:
                raise ValueError("target_assignee_id is required")

            before_decision = self.policy_service.evaluate_auto_assign(queue_key=case.queue_key, item=item)

            updated_item = self.queue_repository.assign(
                queue_key=case.queue_key,
                item_id=case.item_id,
                assignee_id=target_assignee_id,
                actor_id=actor_id,
                expected_version=expected_item_version,
                reason="policy_override_assign",
                metadata={
                    "review_case_id": str(case.id),
                    "override": True,
                    "reason": reason,
                },
            )

            self.guardrail_state_service.clear_review_flags(queue_key=case.queue_key, item_id=case.item_id)
            self.guardrail_state_service.record_assignment(queue_key=case.queue_key, item_id=case.item_id)

            case.status = "overridden"
            case.resolved_by = actor_id
            case.resolved_at = datetime.now(timezone.utc)

            self.action_repo.create(
                review_case_id=case.id,
                queue_key=case.queue_key,
                item_id=case.item_id,
                action_type="override_policy",
                actor_id=actor_id,
                reason=reason,
                from_status=old_status,
                to_status=case.status,
                previous_assignee_id=previous_assignee_id,
                new_assignee_id=target_assignee_id,
                metadata_json=metadata_json,
            )

            self.override_repo.create(
                queue_key=case.queue_key,
                item_id=case.item_id,
                review_case_id=case.id,
                override_type="override_auto_assign_block",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
                overridden_rule_keys_json=before_decision.applied_rule_keys,
                before_decision_json={
                    "allowed": before_decision.allowed,
                    "blocked": before_decision.blocked,
                    "requires_human_review": before_decision.requires_human_review,
                    "requires_governance_approval": before_decision.requires_governance_approval,
                    "reasons": before_decision.reasons,
                },
                after_decision_json={
                    "allowed": True,
                    "blocked": False,
                    "overridden": True,
                },
                execution_payload_json={
                    "target_assignee_id": target_assignee_id,
                    "updated_item_version": getattr(updated_item, "version", None),
                },
            )

        elif decision == "override_policy_and_reassign":
            if not target_assignee_id:
                raise ValueError("target_assignee_id is required")

            before_decision = self.policy_service.evaluate_auto_assign(queue_key=case.queue_key, item=item)

            result = self.reassign_service.execute(
                queue_key=case.queue_key,
                item_id=case.item_id,
                new_assignee_id=target_assignee_id,
                actor_id=actor_id,
                expected_version=expected_item_version,
                reason="policy_override_reassign",
            )

            case.status = "overridden"
            case.resolved_by = actor_id
            case.resolved_at = datetime.now(timezone.utc)

            self.action_repo.create(
                review_case_id=case.id,
                queue_key=case.queue_key,
                item_id=case.item_id,
                action_type="override_policy",
                actor_id=actor_id,
                reason=reason,
                from_status=old_status,
                to_status=case.status,
                previous_assignee_id=previous_assignee_id,
                new_assignee_id=target_assignee_id,
                metadata_json=metadata_json,
            )

            self.override_repo.create(
                queue_key=case.queue_key,
                item_id=case.item_id,
                review_case_id=case.id,
                override_type="override_reassign_block",
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
                overridden_rule_keys_json=before_decision.applied_rule_keys,
                before_decision_json={
                    "allowed": before_decision.allowed,
                    "blocked": before_decision.blocked,
                    "reasons": before_decision.reasons,
                },
                after_decision_json={
                    "allowed": True,
                    "blocked": False,
                    "overridden": True,
                },
                execution_payload_json={
                    "target_assignee_id": target_assignee_id,
                    "reassign_result": result.model_dump() if hasattr(result, "model_dump") else None,
                },
            )

        else:
            raise ValueError("unsupported decision")

        if self.notification_service:
            self.notification_service.emit(
                event_type="queue.review_case.updated",
                payload={
                    "review_case_id": str(case.id),
                    "queue_key": case.queue_key,
                    "item_id": case.item_id,
                    "status": case.status,
                    "actor_id": actor_id,
                    "decision": decision,
                },
            )

        if self.audit_log_service:
            self.audit_log_service.log(
                event_type="queue.review_case.decision",
                actor_id=actor_id,
                entity_type="queue_item",
                entity_id=case.item_id,
                payload={
                    "review_case_id": str(case.id),
                    "queue_key": case.queue_key,
                    "decision": decision,
                    "old_status": old_status,
                    "new_status": case.status,
                    "reason": reason,
                    "target_assignee_id": target_assignee_id,
                },
            )

        self.db.commit()
        return case
8) BACKEND — ESCALATION SLA SERVICE
backend/app/services/queue_assignment_review_escalation_service.py
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.queue_assignment_review_case import QueueAssignmentReviewCase
from app.repositories.queue_assignment_review_action_repository import QueueAssignmentReviewActionRepository


class QueueAssignmentReviewEscalationService:
    def __init__(self, db: Session, *, notification_service=None, audit_log_service=None) -> None:
        self.db = db
        self.notification_service = notification_service
        self.audit_log_service = audit_log_service
        self.action_repo = QueueAssignmentReviewActionRepository(db)

    def run(self) -> dict:
        now = datetime.now(timezone.utc)

        stmt = select(QueueAssignmentReviewCase).where(
            QueueAssignmentReviewCase.status.in_(["pending_review", "pending_approval", "changes_requested"]),
            QueueAssignmentReviewCase.sla_due_at.is_not(None),
            QueueAssignmentReviewCase.sla_due_at < now,
        )
        cases = list(self.db.execute(stmt).scalars().all())

        escalated = 0
        for case in cases:
            old_status = case.status
            case.status = "escalated"
            case.escalation_level += 1

            self.action_repo.create(
                review_case_id=case.id,
                queue_key=case.queue_key,
                item_id=case.item_id,
                action_type="escalate",
                actor_id="system:review_escalation",
                reason="review_sla_breached",
                from_status=old_status,
                to_status="escalated",
                metadata_json={"sla_due_at": case.sla_due_at.isoformat() if case.sla_due_at else None},
            )
            escalated += 1

            if self.notification_service:
                self.notification_service.emit(
                    event_type="queue.review_case.escalated",
                    payload={
                        "review_case_id": str(case.id),
                        "queue_key": case.queue_key,
                        "item_id": case.item_id,
                        "escalation_level": case.escalation_level,
                    },
                )

            if self.audit_log_service:
                self.audit_log_service.log(
                    event_type="queue.review_case.escalated",
                    actor_id="system:review_escalation",
                    entity_type="queue_item",
                    entity_id=case.item_id,
                    payload={
                        "review_case_id": str(case.id),
                        "queue_key": case.queue_key,
                        "escalation_level": case.escalation_level,
                    },
                )

        self.db.commit()
        return {"escalated_count": escalated}
9) BACKEND — PATCH AUTO-ASSIGN FLOW ĐỂ TẠO REVIEW CASE
backend/app/services/queue_auto_assign_service.py
Trong __init__ thêm:
from app.services.queue_assignment_review_queue_service import QueueAssignmentReviewQueueService
và:
self.review_queue_service = QueueAssignmentReviewQueueService(
    db,
    notification_service=notification_service,
    audit_log_service=audit_log_service,
)
Trong execute(...), ở nhánh:
khi requires_governance_approval
thêm tạo case:
review_case = self.review_queue_service.create_from_guardrail_decision(
    queue_key=queue_key,
    item_id=item_id,
    requested_by=actor_id,
    source_decision_type="governance_approval_required",
    source_reason="; ".join(policy_decision.reasons) if policy_decision.reasons else "governance_approval_required",
    requires_supervisor_override=True,
    priority_score=90,
    metadata_json=policy_decision.policy_snapshot_json,
)
và trả thêm review_case_id nếu schema của bạn muốn mở rộng.
khi policy_decision.blocked
thêm:
review_case = self.review_queue_service.create_from_guardrail_decision(
    queue_key=queue_key,
    item_id=item_id,
    requested_by=actor_id,
    source_decision_type="human_review_required",
    source_reason="; ".join(policy_decision.reasons) if policy_decision.reasons else "blocked_by_policy",
    requires_supervisor_override=policy_decision.requires_human_review,
    priority_score=70,
    metadata_json=policy_decision.policy_snapshot_json,
)
Điểm này giúp từ guardrail state đi thẳng vào human review queue.
10) BACKEND — ROUTES
backend/app/api/routes/queue_assignment_review.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.queue_assignment_review import (
    QueueAssignmentReviewCaseOut,
    QueueAssignmentReviewActionOut,
    QueueCreateReviewCaseIn,
    QueuePolicyOverrideAuditOut,
    QueueReviewDecisionIn,
)
from app.repositories.queue_assignment_review_case_repository import QueueAssignmentReviewCaseRepository
from app.repositories.queue_assignment_review_action_repository import QueueAssignmentReviewActionRepository
from app.repositories.queue_policy_override_audit_repository import QueuePolicyOverrideAuditRepository
from app.services.queue_assignment_review_queue_service import QueueAssignmentReviewQueueService
from app.services.queue_assignment_review_workflow_service import QueueAssignmentReviewWorkflowService


router = APIRouter(prefix="/queue/review-cases", tags=["queue-assignment-review"])


def get_queue_repository():
    from app.dependencies.queue_runtime import get_queue_repository
    return get_queue_repository()


def get_audit_log_service():
    from app.dependencies.queue_runtime import get_audit_log_service
    return get_audit_log_service()


def get_notification_service():
    from app.dependencies.queue_runtime import get_notification_service
    return get_notification_service()


@router.post("", response_model=QueueAssignmentReviewCaseOut)
def create_review_case(
    payload: QueueCreateReviewCaseIn,
    db: Session = Depends(get_db),
):
    service = QueueAssignmentReviewQueueService(
        db,
        notification_service=get_notification_service(),
        audit_log_service=get_audit_log_service(),
    )
    case = service.create_from_guardrail_decision(
        queue_key=payload.queue_key,
        item_id=payload.item_id,
        requested_by=payload.requested_by,
        source_decision_type=payload.source_decision_type or payload.case_type,
        source_reason=payload.source_reason,
        requires_supervisor_override=payload.requires_supervisor_override,
        priority_score=payload.priority_score,
        assigned_reviewer_id=payload.assigned_reviewer_id,
        sla_minutes=30,
        metadata_json=payload.metadata_json,
    )
    db.commit()
    db.refresh(case)
    return case


@router.get("", response_model=list[QueueAssignmentReviewCaseOut])
def list_review_cases(
    queue_key: str | None = None,
    assigned_reviewer_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    repo = QueueAssignmentReviewCaseRepository(db)
    statuses = [status] if status else ["pending_review", "pending_approval", "changes_requested", "escalated"]
    return repo.list_pending(
        queue_key=queue_key,
        assigned_reviewer_id=assigned_reviewer_id,
        statuses=statuses,
        limit=100,
    )


@router.get("/{review_case_id}", response_model=QueueAssignmentReviewCaseOut)
def get_review_case(
    review_case_id: str,
    db: Session = Depends(get_db),
):
    repo = QueueAssignmentReviewCaseRepository(db)
    case = repo.get(review_case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="review case not found")
    return case


@router.get("/{review_case_id}/actions", response_model=list[QueueAssignmentReviewActionOut])
def list_review_case_actions(
    review_case_id: str,
    db: Session = Depends(get_db),
):
    repo = QueueAssignmentReviewActionRepository(db)
    return repo.list_for_case(review_case_id, limit=100)


@router.post("/{review_case_id}/decision", response_model=QueueAssignmentReviewCaseOut)
def decide_review_case(
    review_case_id: str,
    payload: QueueReviewDecisionIn,
    db: Session = Depends(get_db),
):
    service = QueueAssignmentReviewWorkflowService(
        db,
        queue_repository=get_queue_repository(),
        audit_log_service=get_audit_log_service(),
        notification_service=get_notification_service(),
    )
    try:
        case = service.decide(
            review_case_id=review_case_id,
            actor_id=payload.actor_id,
            actor_role=payload.actor_role,
            decision=payload.decision,
            reason=payload.reason,
            target_assignee_id=payload.target_assignee_id,
            expected_item_version=payload.expected_item_version,
            metadata_json=payload.metadata_json,
        )
        db.refresh(case)
        return case
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        message = str(e).lower()
        if "version" in message or "conflict" in message:
            raise HTTPException(status_code=409, detail=str(e))
        raise


@router.get("/items/{queue_key}/{item_id}/override-audits", response_model=list[QueuePolicyOverrideAuditOut])
def list_override_audits(
    queue_key: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    repo = QueuePolicyOverrideAuditRepository(db)
    return repo.list_for_item(queue_key=queue_key, item_id=item_id, limit=100)
11) BACKEND — ROUTER WIRING
backend/app/api/api_v1/api.py
from app.api.routes import queue_assignment_review
và:
api_router.include_router(queue_assignment_review.router)
12) BACKEND — MIGRATION
backend/alembic/versions/005_phase3_review_queue_and_override_audit.py
"""phase3 review queue and override audit

Revision ID: 005_phase3_review_queue_and_override_audit
Revises: 004_phase3_assignment_guardrails
Create Date: 2026-04-12 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "005_phase3_review_queue_and_override_audit"
down_revision = "004_phase3_assignment_guardrails"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "queue_assignment_review_case",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("case_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending_review"),
        sa.Column("source_decision_type", sa.String(length=80), nullable=True),
        sa.Column("source_reason", sa.Text(), nullable=True),
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assigned_reviewer_id", sa.String(length=100), nullable=True),
        sa.Column("requested_by", sa.String(length=100), nullable=True),
        sa.Column("resolved_by", sa.String(length=100), nullable=True),
        sa.Column("requires_supervisor_override", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_queue_assignment_review_case_queue_key", "queue_assignment_review_case", ["queue_key"])
    op.create_index("ix_queue_assignment_review_case_item_id", "queue_assignment_review_case", ["item_id"])
    op.create_index("ix_queue_assignment_review_case_case_type", "queue_assignment_review_case", ["case_type"])
    op.create_index("ix_queue_assignment_review_case_status", "queue_assignment_review_case", ["status"])
    op.create_index("ix_queue_assignment_review_case_assigned_reviewer_id", "queue_assignment_review_case", ["assigned_reviewer_id"])
    op.create_index("ix_queue_assignment_review_case_requested_by", "queue_assignment_review_case", ["requested_by"])
    op.create_index("ix_queue_assignment_review_case_resolved_by", "queue_assignment_review_case", ["resolved_by"])
    op.create_index("ix_queue_assignment_review_case_sla_due_at", "queue_assignment_review_case", ["sla_due_at"])

    op.create_table(
        "queue_assignment_review_action",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("review_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=True),
        sa.Column("previous_assignee_id", sa.String(length=100), nullable=True),
        sa.Column("new_assignee_id", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_queue_assignment_review_action_review_case_id", "queue_assignment_review_action", ["review_case_id"])
    op.create_index("ix_queue_assignment_review_action_queue_key", "queue_assignment_review_action", ["queue_key"])
    op.create_index("ix_queue_assignment_review_action_item_id", "queue_assignment_review_action", ["item_id"])
    op.create_index("ix_queue_assignment_review_action_action_type", "queue_assignment_review_action", ["action_type"])
    op.create_index("ix_queue_assignment_review_action_actor_id", "queue_assignment_review_action", ["actor_id"])

    op.create_table(
        "queue_policy_override_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("queue_key", sa.String(length=100), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("review_case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("override_type", sa.String(length=80), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("actor_role", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("overridden_rule_keys_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("before_decision_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_decision_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("execution_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_queue_policy_override_audit_queue_key", "queue_policy_override_audit", ["queue_key"])
    op.create_index("ix_queue_policy_override_audit_item_id", "queue_policy_override_audit", ["item_id"])
    op.create_index("ix_queue_policy_override_audit_review_case_id", "queue_policy_override_audit", ["review_case_id"])
    op.create_index("ix_queue_policy_override_audit_override_type", "queue_policy_override_audit", ["override_type"])
    op.create_index("ix_queue_policy_override_audit_actor_id", "queue_policy_override_audit", ["actor_id"])


def downgrade():
    op.drop_index("ix_queue_policy_override_audit_actor_id", table_name="queue_policy_override_audit")
    op.drop_index("ix_queue_policy_override_audit_override_type", table_name="queue_policy_override_audit")
    op.drop_index("ix_queue_policy_override_audit_review_case_id", table_name="queue_policy_override_audit")
    op.drop_index("ix_queue_policy_override_audit_item_id", table_name="queue_policy_override_audit")
    op.drop_index("ix_queue_policy_override_audit_queue_key", table_name="queue_policy_override_audit")
    op.drop_table("queue_policy_override_audit")

    op.drop_index("ix_queue_assignment_review_action_actor_id", table_name="queue_assignment_review_action")
    op.drop_index("ix_queue_assignment_review_action_action_type", table_name="queue_assignment_review_action")
    op.drop_index("ix_queue_assignment_review_action_item_id", table_name="queue_assignment_review_action")
    op.drop_index("ix_queue_assignment_review_action_queue_key", table_name="queue_assignment_review_action")
    op.drop_index("ix_queue_assignment_review_action_review_case_id", table_name="queue_assignment_review_action")
    op.drop_table("queue_assignment_review_action")

    op.drop_index("ix_queue_assignment_review_case_sla_due_at", table_name="queue_assignment_review_case")
    op.drop_index("ix_queue_assignment_review_case_resolved_by", table_name="queue_assignment_review_case")
    op.drop_index("ix_queue_assignment_review_case_requested_by", table_name="queue_assignment_review_case")
    op.drop_index("ix_queue_assignment_review_case_assigned_reviewer_id", table_name="queue_assignment_review_case")
    op.drop_index("ix_queue_assignment_review_case_status", table_name="queue_assignment_review_case")
    op.drop_index("ix_queue_assignment_review_case_case_type", table_name="queue_assignment_review_case")
    op.drop_index("ix_queue_assignment_review_case_item_id", table_name="queue_assignment_review_case")
    op.drop_index("ix_queue_assignment_review_case_queue_key", table_name="queue_assignment_review_case")
    op.drop_table("queue_assignment_review_case")
13) BACKEND — WORKER / SCHEDULE
backend/app/workers/queue_assignment_review_escalation_worker.py
from __future__ import annotations

from celery import shared_task
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.queue_assignment_review_escalation_service import QueueAssignmentReviewEscalationService


@shared_task(name="queue.review_case.escalation_scan")
def queue_review_case_escalation_scan() -> dict:
    db: Session = SessionLocal()
    try:
        service = QueueAssignmentReviewEscalationService(db)
        return service.run()
    finally:
        db.close()
14) BACKEND — TESTS
backend/tests/services/test_queue_assignment_review_queue_service.py
from app.services.queue_assignment_review_queue_service import QueueAssignmentReviewQueueService


def test_create_review_case_from_guardrail_decision(db_session):
    service = QueueAssignmentReviewQueueService(db_session)

    case = service.create_from_guardrail_decision(
        queue_key="render_ops",
        item_id="item_1",
        requested_by="system:auto_assign",
        source_decision_type="human_review_required",
        source_reason="blocked_by_policy",
        requires_supervisor_override=False,
        priority_score=70,
        metadata_json={"foo": "bar"},
    )

    assert case.queue_key == "render_ops"
    assert case.item_id == "item_1"
    assert case.status == "pending_review"
backend/tests/services/test_queue_assignment_review_workflow_service.py
from app.services.queue_assignment_review_queue_service import QueueAssignmentReviewQueueService
from app.services.queue_assignment_review_workflow_service import QueueAssignmentReviewWorkflowService


class FakeItem:
    id = "item_1"
    version = 3
    assignee_id = None
    severity = "high"
    provider = "veo"
    project_id = "project_a"
    item_type = "render_job"


class FakeQueueRepository:
    def __init__(self):
        self.item = FakeItem()

    def get_item(self, queue_key, item_id):
        return self.item

    def list_open_items_for_assignee(self, queue_key, assignee_id):
        return []

    def assign(self, *, queue_key, item_id, assignee_id, actor_id, expected_version=None, reason=None, metadata=None):
        if expected_version is not None and expected_version != self.item.version:
            raise RuntimeError("version conflict")
        self.item.assignee_id = assignee_id
        self.item.version += 1
        return self.item


def test_override_policy_and_assign_creates_override_audit(db_session):
    queue_repo = FakeQueueRepository()
    create_service = QueueAssignmentReviewQueueService(db_session)
    case = create_service.create_from_guardrail_decision(
        queue_key="render_ops",
        item_id="item_1",
        requested_by="system:auto_assign",
        source_decision_type="human_review_required",
        source_reason="blocked_by_policy",
    )
    db_session.commit()

    workflow = QueueAssignmentReviewWorkflowService(
        db_session,
        queue_repository=queue_repo,
    )

    updated_case = workflow.decide(
        review_case_id=str(case.id),
        actor_id="supervisor_1",
        actor_role="supervisor",
        decision="override_policy_and_assign",
        reason="business critical item",
        target_assignee_id="op_a",
        expected_item_version=3,
    )

    assert updated_case.status == "overridden"
    assert queue_repo.item.assignee_id == "op_a"
backend/tests/services/test_queue_assignment_review_escalation_service.py
from datetime import datetime, timedelta, timezone

from app.repositories.queue_assignment_review_case_repository import QueueAssignmentReviewCaseRepository
from app.services.queue_assignment_review_escalation_service import QueueAssignmentReviewEscalationService


def test_review_case_escalates_when_sla_breached(db_session):
    repo = QueueAssignmentReviewCaseRepository(db_session)
    case = repo.create(
        queue_key="render_ops",
        item_id="item_1",
        case_type="human_review",
        status="pending_review",
        source_decision_type="human_review_required",
        source_reason="blocked_by_policy",
        sla_due_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db_session.commit()

    service = QueueAssignmentReviewEscalationService(db_session)
    result = service.run()

    db_session.refresh(case)

    assert result["escalated_count"] >= 1
    assert case.status == "escalated"
    assert case.escalation_level == 1
15) FRONTEND — TYPES
frontend/src/types/queueAssignmentReview.ts
export type QueueAssignmentReviewCase = {
  id: string;
  queue_key: string;
  item_id: string;
  case_type: string;
  status: string;
  source_decision_type: string | null;
  source_reason: string | null;
  priority_score: number;
  escalation_level: number;
  assigned_reviewer_id: string | null;
  requested_by: string | null;
  resolved_by: string | null;
  requires_supervisor_override: boolean;
  sla_due_at: string | null;
  first_review_at: string | null;
  resolved_at: string | null;
  metadata_json?: Record<string, unknown> | null;
};

export type QueueAssignmentReviewAction = {
  id: string;
  review_case_id: string;
  queue_key: string;
  item_id: string;
  action_type: string;
  actor_id: string;
  reason: string | null;
  from_status: string | null;
  to_status: string | null;
  previous_assignee_id: string | null;
  new_assignee_id: string | null;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
};

export type QueueReviewDecisionRequest = {
  actor_id: string;
  actor_role?: string | null;
  decision: string;
  reason: string;
  target_assignee_id?: string | null;
  expected_item_version?: number | null;
  metadata_json?: Record<string, unknown> | null;
};

export type QueuePolicyOverrideAudit = {
  id: string;
  queue_key: string;
  item_id: string;
  review_case_id: string | null;
  override_type: string;
  actor_id: string;
  actor_role: string | null;
  reason: string;
  overridden_rule_keys_json: unknown[] | null;
  before_decision_json?: Record<string, unknown> | null;
  after_decision_json?: Record<string, unknown> | null;
  execution_payload_json?: Record<string, unknown> | null;
  created_at: string;
};
16) FRONTEND — API
frontend/src/api/queueAssignmentReview.ts
import { apiClient } from "./client";
import {
  QueueAssignmentReviewAction,
  QueueAssignmentReviewCase,
  QueuePolicyOverrideAudit,
  QueueReviewDecisionRequest,
} from "../types/queueAssignmentReview";

export async function fetchReviewCases(params?: {
  queue_key?: string;
  assigned_reviewer_id?: string;
  status?: string;
}) {
  const res = await apiClient.get<QueueAssignmentReviewCase[]>("/queue/review-cases", {
    params,
  });
  return res.data;
}

export async function fetchReviewCase(reviewCaseId: string) {
  const res = await apiClient.get<QueueAssignmentReviewCase>(`/queue/review-cases/${reviewCaseId}`);
  return res.data;
}

export async function fetchReviewCaseActions(reviewCaseId: string) {
  const res = await apiClient.get<QueueAssignmentReviewAction[]>(
    `/queue/review-cases/${reviewCaseId}/actions`,
  );
  return res.data;
}

export async function decideReviewCase(reviewCaseId: string, payload: QueueReviewDecisionRequest) {
  const res = await apiClient.post<QueueAssignmentReviewCase>(
    `/queue/review-cases/${reviewCaseId}/decision`,
    payload,
  );
  return res.data;
}

export async function fetchOverrideAudits(queueKey: string, itemId: string) {
  const res = await apiClient.get<QueuePolicyOverrideAudit[]>(
    `/queue/review-cases/items/${queueKey}/${itemId}/override-audits`,
  );
  return res.data;
}
17) FRONTEND — HUMAN REVIEW QUEUE PANEL
frontend/src/components/queue/HumanReviewQueuePanel.tsx
import React, { useEffect, useState } from "react";
import { fetchReviewCases } from "../../api/queueAssignmentReview";
import { QueueAssignmentReviewCase } from "../../types/queueAssignmentReview";

type Props = {
  queueKey?: string;
  reviewerId?: string;
  onSelectCase?: (reviewCase: QueueAssignmentReviewCase) => void;
  onToast: (input: { title: string; description?: string; variant?: "default" | "destructive" }) => void;
};

export function HumanReviewQueuePanel({ queueKey, reviewerId, onSelectCase, onToast }: Props) {
  const [cases, setCases] = useState<QueueAssignmentReviewCase[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchReviewCases({
        queue_key: queueKey,
        assigned_reviewer_id: reviewerId,
      });
      setCases(data);
    } catch (err: any) {
      onToast({
        title: "Không tải được human review queue",
        description: err?.response?.data?.detail || "Unknown error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [queueKey, reviewerId]);

  return (
    <div className="rounded-xl border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Human Review Queue</h3>
        <button className="border rounded px-3 py-1" onClick={load}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      <div className="space-y-2">
        {cases.map((c) => (
          <button
            key={c.id}
            className="w-full text-left rounded border p-3 hover:bg-gray-50"
            onClick={() => onSelectCase?.(c)}
          >
            <div className="flex items-center justify-between">
              <strong>{c.item_id}</strong>
              <span>{c.status}</span>
            </div>
            <div className="text-sm mt-1">
              queue={c.queue_key} | type={c.case_type} | priority={c.priority_score} | escalation={c.escalation_level}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {c.source_reason || "-"}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
18) FRONTEND — REVIEW DECISION PANEL
frontend/src/components/queue/ReviewDecisionPanel.tsx
import React, { useEffect, useState } from "react";
import {
  decideReviewCase,
  fetchOverrideAudits,
  fetchReviewCaseActions,
} from "../../api/queueAssignmentReview";
import {
  QueueAssignmentReviewAction,
  QueueAssignmentReviewCase,
  QueuePolicyOverrideAudit,
} from "../../types/queueAssignmentReview";

type Props = {
  reviewCase: QueueAssignmentReviewCase | null;
  actorId: string;
  actorRole?: string;
  itemVersion?: number;
  onToast: (input: { title: string; description?: string; variant?: "default" | "destructive" }) => void;
  onDone?: () => void;
};

export function ReviewDecisionPanel({
  reviewCase,
  actorId,
  actorRole,
  itemVersion,
  onToast,
  onDone,
}: Props) {
  const [reason, setReason] = useState("");
  const [targetAssigneeId, setTargetAssigneeId] = useState("");
  const [actions, setActions] = useState<QueueAssignmentReviewAction[]>([]);
  const [audits, setAudits] = useState<QueuePolicyOverrideAudit[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    if (!reviewCase) return;
    setLoading(true);
    try {
      const [actionsData, auditsData] = await Promise.all([
        fetchReviewCaseActions(reviewCase.id),
        fetchOverrideAudits(reviewCase.queue_key, reviewCase.item_id),
      ]);
      setActions(actionsData);
      setAudits(auditsData);
    } catch (err: any) {
      onToast({
        title: "Không tải được review detail",
        description: err?.response?.data?.detail || "Unknown error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }

  async function submit(decision: string) {
    if (!reviewCase) return;
    if (!reason.trim()) {
      onToast({
        title: "Thiếu lý do",
        description: "Nhập reason trước khi quyết định",
        variant: "destructive",
      });
      return;
    }

    setSubmitting(true);
    try {
      await decideReviewCase(reviewCase.id, {
        actor_id: actorId,
        actor_role: actorRole,
        decision,
        reason,
        target_assignee_id: targetAssigneeId || null,
        expected_item_version: itemVersion ?? null,
      });

      onToast({
        title: "Đã cập nhật review case",
        description: decision,
      });
      setReason("");
      setTargetAssigneeId("");
      await load();
      onDone?.();
    } catch (err: any) {
      onToast({
        title: "Review decision thất bại",
        description: err?.response?.data?.detail || "Unknown error",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    load();
  }, [reviewCase?.id]);

  if (!reviewCase) {
    return <div className="rounded-xl border p-4">Chọn một review case.</div>;
  }

  return (
    <div className="rounded-xl border p-4 space-y-4">
      <div>
        <h3 className="font-semibold">Review Decision</h3>
        <div className="text-sm mt-1">
          item={reviewCase.item_id} | status={reviewCase.status} | type={reviewCase.case_type}
        </div>
      </div>

      <textarea
        className="w-full border rounded px-3 py-2 min-h-[96px]"
        placeholder="Reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />

      <input
        className="w-full border rounded px-3 py-2"
        placeholder="Target assignee id (cho override assign/reassign)"
        value={targetAssigneeId}
        onChange={(e) => setTargetAssigneeId(e.target.value)}
      />

      <div className="flex flex-wrap gap-2">
        <button className="border rounded px-3 py-2" disabled={submitting} onClick={() => submit("approve")}>
          Approve
        </button>
        <button className="border rounded px-3 py-2" disabled={submitting} onClick={() => submit("reject")}>
          Reject
        </button>
        <button className="border rounded px-3 py-2" disabled={submitting} onClick={() => submit("request_changes")}>
          Request Changes
        </button>
        <button className="border rounded px-3 py-2" disabled={submitting} onClick={() => submit("override_policy_and_assign")}>
          Override + Assign
        </button>
        <button className="border rounded px-3 py-2" disabled={submitting} onClick={() => submit("override_policy_and_reassign")}>
          Override + Reassign
        </button>
      </div>

      <div className="space-y-2">
        <h4 className="font-medium">Actions</h4>
        {loading ? (
          <div className="text-sm text-gray-500">Loading...</div>
        ) : (
          actions.map((a) => (
            <div key={a.id} className="rounded border p-2 text-sm">
              <div><strong>{a.action_type}</strong> by {a.actor_id}</div>
              <div>{a.reason || "-"}</div>
            </div>
          ))
        )}
      </div>

      <div className="space-y-2">
        <h4 className="font-medium">Override Audits</h4>
        {audits.map((a) => (
          <div key={a.id} className="rounded border p-2 text-sm">
            <div><strong>{a.override_type}</strong> by {a.actor_id}</div>
            <div>{a.reason}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
19) FRONTEND — PATCH QUEUE PANEL
frontend/src/components/queue/OperatorQueuePanel.tsx
Thêm import:
import { HumanReviewQueuePanel } from "./HumanReviewQueuePanel";
import { ReviewDecisionPanel } from "./ReviewDecisionPanel";
Trong parent component thêm state:
const [selectedReviewCase, setSelectedReviewCase] = useState<QueueAssignmentReviewCase | null>(null);
Render thêm block:
<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
  <HumanReviewQueuePanel
    queueKey={selectedQueueKey}
    reviewerId={currentActorId}
    onSelectCase={setSelectedReviewCase}
    onToast={onToast}
  />

  <ReviewDecisionPanel
    reviewCase={selectedReviewCase}
    actorId={currentActorId}
    actorRole={currentActorRole}
    itemVersion={selectedItem?.version}
    onToast={onToast}
    onDone={() => {
      refetchQueue();
      refetchItemDetail?.();
    }}
  />
</div>
20) MAP RẤT NGẮN KHI GẮN VÀO REPO THẬT
Đây là phần quan trọng nhất để patch sạch khi map production.
A. Review queue phải là read surface riêng
Đừng trộn chung hoàn toàn vào operator queue chính.
Nên có:
review cases pending
approval cases pending
escalated cases
resolved history
Như vậy reviewer/supervisor có workspace riêng.
B. Override phải khóa bằng RBAC thật
Bản patch này chỉ nhận actor_role.
Production thật phải map thêm:
supervisor mới được override_policy_and_assign
manager/supervisor mới được override_policy_and_reassign
reviewer thường chỉ được approve/reject/request_changes
một số override đặc biệt cần 2-person rule nếu muốn siết
C. Approval workflow nên nối vào governance hiện có
Nếu repo của bạn đã có Phase 3 governance:
governance_change_request
governance_approval
governance_execution_attempt
thì pending_approval tốt nhất nên map 1-1 hoặc bridge với governance approval object thật, thay vì tồn tại độc lập lâu dài.
D. Escalation SLA nên materialize
Hiện worker scan dựa trên sla_due_at.
Production mạnh hơn nên có thêm:
review_sla_state materialized
breach count theo queue/reviewer
escalation latency
first response latency
overdue buckets
E. Review decision sau approve
Hiện patch approve chỉ kết review case và clear flags.
Trong production bạn có 2 mode rõ ràng:
Mode 1 — approve only
chỉ bỏ cờ
operator/system tự chạy lại auto-assign
Mode 2 — approve and continue
approve xong gọi ngay auto-assign service
hoặc assign luôn nếu reviewer đã chỉ định target assignee
Nếu muốn production mượt hơn, nên thêm approve_and_execute.
F. Override audit phải là immutable
Không update record override audit.
Chỉ append-only để đảm bảo:
forensic trace
compliance
postmortem
explainability
21) KẾT QUẢ SAU PATCH NÀY
Sau bản này queue tăng thêm 5 lớp rất mạnh:
1. Human review queue
Hệ có hàng đợi riêng cho:
pending review
pending approval
escalated review cases
2. Approval workflow
Reviewer/supervisor có thể:
approve
reject
request changes
override policy and assign
override policy and reassign
3. Full policy override audit
Hệ ghi rõ:
ai override
override cái gì
override rule nào
vì sao override
execution result sau override
4. Escalation SLA
Hệ biết:
case nào quá hạn review
case nào phải escalated
escalation level tăng ra sao
5. Human-in-the-loop bridge
Hệ chuyển từ:
policy chặn cứng
sang:
policy chặn nhưng có human supervisory path rõ ràng
Tức là queue chuyển từ:
policy-governed controlled execution
sang:
human-in-the-loop governed execution
22) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
add 3 models
register imports vào base
add 3 repositories
add schemas
add review queue service
add review workflow service
add escalation service
patch auto-assign service tạo review case
add routes
wire router
add migration
add worker
add tests
Frontend
add types
add APIs
add HumanReviewQueuePanel
add ReviewDecisionPanel
patch queue panel
Đây là bước mạnh nhất tiếp theo.
Vì sau khi đã có:
human review queue
approve / reject / override workflow
escalation
audit timeline
thì lớp kế tiếp phải là:
PHASE 3 — REVIEWER WORKLOAD BALANCING + REVIEW SLA ANALYTICS + OVERRIDE EFFECTIVENESS ATTRIBUTION
Mục tiêu của phase này là nâng hệ từ:
human-in-the-loop governed execution
thành:
measurable supervised governance
tức là hệ không chỉ biết “có review”, mà còn biết:
review case nên giao cho reviewer nào
reviewer nào đang quá tải
reviewer nào xử lý nhanh/chậm
queue nào đang vi phạm SLA
override nào giúp hệ tốt hơn
override nào làm tăng churn/conflict/rework
supervisor nào đang override hợp lý hay không hợp lý
1) PHẠM VI PHASE NÀY
Backend thêm
reviewer workload snapshot/read model
reviewer assignment policy service
review SLA analytics service
override effectiveness attribution service
endpoints cho:
workload
rebalance recommendations
reviewer leaderboard
SLA breakdown
override effectiveness
worker materialize workload + SLA rollups
tests
Frontend thêm
ReviewerWorkloadPanel
ReviewSLAAnalyticsPanel
OverrideEffectivenessPanel
patch HumanReviewQueuePanel để hiện suggested reviewer / overload / rebalance
patch ReviewDecisionPanel để hiện history + supervisor effectiveness hints
2) CÁC KHÁI NIỆM CHÍNH
A. Reviewer workload balancing
Hệ phải biết cho từng reviewer:
open review cases
pending approval cases
overdue cases
avg first response time
avg resolution time
active overrides touched
current capacity score
workload score
Từ đó gợi ý:
ai nên nhận case mới
ai không nên nhận thêm
case nào cần reassign
B. Review SLA analytics
Phải đo được:
time_to_first_review
time_to_decision
approval turnaround
escalation turnaround
overdue count
breach rate
queue-by-queue SLA health
reviewer-by-reviewer SLA health
C. Override effectiveness attribution
Supervisor override không chỉ log lại, mà phải đo outcome:
override có giảm total resolution time không
override có cứu SLA breach không
override có làm tăng rework không
override có dẫn đến conflict/version mismatch không
override có làm execution fail không
Từ đó sinh:
effective override
neutral override
harmful override
3) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
add 3 analytics models / read models
register imports vào base
add repositories
add schemas
add reviewer workload balancing service
add review SLA analytics service
add override effectiveness attribution service
patch review workflow service để emit analytics events / fields
patch escalation service
add routes
wire router
add migration
add worker
add tests
Frontend
add types
add APIs
add ReviewerWorkloadPanel
add ReviewSLAAnalyticsPanel
add OverrideEffectivenessPanel
patch HumanReviewQueuePanel
patch ReviewDecisionPanel
4) FILE-BY-FILE PATCH PLAN
Dưới đây là format monorepo production bám theo các phase trước.
BACKEND
4.1 Models
backend/app/models/reviewer_workload_snapshot.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ReviewerWorkloadSnapshot(Base):
    __tablename__ = "reviewer_workload_snapshot"

    reviewer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    open_review_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_approval_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overdue_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    escalated_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    avg_first_response_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_resolution_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    capacity_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    workload_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    availability_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    last_case_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/review_sla_rollup.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ReviewSlaRollup(Base):
    __tablename__ = "review_sla_rollup"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)  # global|queue|reviewer|project
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)

    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overridden_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overdue_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    breached_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    avg_first_review_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_decision_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_escalation_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    sla_breach_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    on_time_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/override_effectiveness_rollup.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class OverrideEffectivenessRollup(Base):
    __tablename__ = "override_effectiveness_rollup"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    total_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    neutral_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    harmful_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sla_saved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_increase_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rework_trigger_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    effectiveness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
4.2 Register imports vào base
backend/app/db/base.py
from app.models.reviewer_workload_snapshot import ReviewerWorkloadSnapshot
from app.models.review_sla_rollup import ReviewSlaRollup
from app.models.override_effectiveness_rollup import OverrideEffectivenessRollup
4.3 Repositories
backend/app/repositories/reviewer_workload_repository.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reviewer_workload_snapshot import ReviewerWorkloadSnapshot


class ReviewerWorkloadRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert(self, snapshot: ReviewerWorkloadSnapshot) -> ReviewerWorkloadSnapshot:
        existing = self.db.get(ReviewerWorkloadSnapshot, snapshot.reviewer_id)
        if existing:
            for field in [
                "reviewer_name",
                "open_review_cases",
                "pending_approval_cases",
                "overdue_cases",
                "escalated_cases",
                "avg_first_response_minutes",
                "avg_resolution_minutes",
                "capacity_limit",
                "workload_score",
                "availability_score",
                "last_case_assigned_at",
                "snapshot_at",
            ]:
                setattr(existing, field, getattr(snapshot, field))
            self.db.add(existing)
            return existing

        self.db.add(snapshot)
        return snapshot

    def get(self, reviewer_id: str) -> ReviewerWorkloadSnapshot | None:
        return self.db.get(ReviewerWorkloadSnapshot, reviewer_id)

    def list_all(self) -> list[ReviewerWorkloadSnapshot]:
        stmt = select(ReviewerWorkloadSnapshot).order_by(
            ReviewerWorkloadSnapshot.workload_score.asc(),
            ReviewerWorkloadSnapshot.overdue_cases.asc(),
        )
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/review_sla_rollup_repository.py
from __future__ import annotations

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.models.review_sla_rollup import ReviewSlaRollup


class ReviewSlaRollupRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: ReviewSlaRollup) -> ReviewSlaRollup:
        self.db.add(model)
        return model

    def list_latest_by_scope_type(self, scope_type: str) -> list[ReviewSlaRollup]:
        stmt = (
            select(ReviewSlaRollup)
            .where(ReviewSlaRollup.scope_type == scope_type)
            .order_by(desc(ReviewSlaRollup.computed_at))
        )
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/override_effectiveness_rollup_repository.py
from __future__ import annotations

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.models.override_effectiveness_rollup import OverrideEffectivenessRollup


class OverrideEffectivenessRollupRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: OverrideEffectivenessRollup) -> OverrideEffectivenessRollup:
        self.db.add(model)
        return model

    def list_latest(self) -> list[OverrideEffectivenessRollup]:
        stmt = select(OverrideEffectivenessRollup).order_by(
            desc(OverrideEffectivenessRollup.effectiveness_score),
            desc(OverrideEffectivenessRollup.computed_at),
        )
        return list(self.db.execute(stmt).scalars().all())
4.4 Schemas
backend/app/schemas/reviewer_workload.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class ReviewerWorkloadRead(BaseModel):
    reviewer_id: str
    reviewer_name: str | None = None
    open_review_cases: int
    pending_approval_cases: int
    overdue_cases: int
    escalated_cases: int
    avg_first_response_minutes: float | None = None
    avg_resolution_minutes: float | None = None
    capacity_limit: int
    workload_score: float
    availability_score: float
    last_case_assigned_at: datetime | None = None
    snapshot_at: datetime

    class Config:
        from_attributes = True


class ReviewerAssignmentRecommendation(BaseModel):
    reviewer_id: str
    reviewer_name: str | None = None
    recommendation_score: float
    reason_codes: list[str]
backend/app/schemas/review_sla.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class ReviewSlaRollupRead(BaseModel):
    id: str
    scope_type: str
    scope_key: str
    total_cases: int
    reviewed_cases: int
    approved_cases: int
    rejected_cases: int
    overridden_cases: int
    overdue_cases: int
    breached_cases: int
    avg_first_review_minutes: float | None = None
    avg_decision_minutes: float | None = None
    avg_escalation_minutes: float | None = None
    sla_breach_rate: float
    on_time_rate: float
    window_start: datetime
    window_end: datetime
    computed_at: datetime

    class Config:
        from_attributes = True
backend/app/schemas/override_effectiveness.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class OverrideEffectivenessRollupRead(BaseModel):
    id: str
    actor_id: str
    actor_name: str | None = None
    total_overrides: int
    effective_overrides: int
    neutral_overrides: int
    harmful_overrides: int
    sla_saved_count: int
    conflict_increase_count: int
    rework_trigger_count: int
    failed_execution_count: int
    effectiveness_score: float
    window_start: datetime
    window_end: datetime
    computed_at: datetime

    class Config:
        from_attributes = True
4.5 Reviewer workload balancing service
backend/app/services/reviewer_workload_balancing_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.reviewer_workload_snapshot import ReviewerWorkloadSnapshot
from app.repositories.reviewer_workload_repository import ReviewerWorkloadRepository
from app.schemas.reviewer_workload import ReviewerAssignmentRecommendation


@dataclass
class ReviewerCandidate:
    reviewer_id: str
    reviewer_name: str | None
    capacity_limit: int
    open_review_cases: int
    overdue_cases: int
    availability_score: float
    avg_resolution_minutes: float | None


class ReviewerWorkloadBalancingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReviewerWorkloadRepository(db)

    def compute_workload_score(self, c: ReviewerCandidate) -> float:
        base_load = c.open_review_cases / max(c.capacity_limit, 1)
        overdue_penalty = c.overdue_cases * 0.25
        speed_bonus = 0.0
        if c.avg_resolution_minutes is not None:
            speed_bonus = min(0.25, 240.0 / max(c.avg_resolution_minutes, 1.0) / 10.0)
        availability_bonus = c.availability_score * 0.5
        return max(0.0, base_load + overdue_penalty - speed_bonus - availability_bonus)

    def suggest_reviewer_for_case(self) -> list[ReviewerAssignmentRecommendation]:
        snapshots = self.repo.list_all()
        recommendations: list[ReviewerAssignmentRecommendation] = []

        for s in snapshots:
            score = max(0.0, 10.0 - s.workload_score)
            reasons = []
            if s.overdue_cases == 0:
                reasons.append("no_overdue")
            if s.open_review_cases < s.capacity_limit:
                reasons.append("under_capacity")
            if s.availability_score >= 0.8:
                reasons.append("high_availability")

            recommendations.append(
                ReviewerAssignmentRecommendation(
                    reviewer_id=s.reviewer_id,
                    reviewer_name=s.reviewer_name,
                    recommendation_score=score,
                    reason_codes=reasons,
                )
            )

        recommendations.sort(key=lambda x: x.recommendation_score, reverse=True)
        return recommendations

    def materialize_snapshot(
        self,
        reviewer_id: str,
        reviewer_name: str | None,
        open_review_cases: int,
        pending_approval_cases: int,
        overdue_cases: int,
        escalated_cases: int,
        avg_first_response_minutes: float | None,
        avg_resolution_minutes: float | None,
        capacity_limit: int = 10,
        availability_score: float = 1.0,
    ) -> ReviewerWorkloadSnapshot:
        candidate = ReviewerCandidate(
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            capacity_limit=capacity_limit,
            open_review_cases=open_review_cases,
            overdue_cases=overdue_cases,
            availability_score=availability_score,
            avg_resolution_minutes=avg_resolution_minutes,
        )
        workload_score = self.compute_workload_score(candidate)

        snapshot = ReviewerWorkloadSnapshot(
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            open_review_cases=open_review_cases,
            pending_approval_cases=pending_approval_cases,
            overdue_cases=overdue_cases,
            escalated_cases=escalated_cases,
            avg_first_response_minutes=avg_first_response_minutes,
            avg_resolution_minutes=avg_resolution_minutes,
            capacity_limit=capacity_limit,
            workload_score=workload_score,
            availability_score=availability_score,
            snapshot_at=datetime.utcnow(),
        )
        return self.repo.upsert(snapshot)
4.6 Review SLA analytics service
backend/app/services/review_sla_analytics_service.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.review_sla_rollup import ReviewSlaRollup
from app.repositories.review_sla_rollup_repository import ReviewSlaRollupRepository


class ReviewSlaAnalyticsService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReviewSlaRollupRepository(db)

    def build_rollup(
        self,
        *,
        rollup_id: str,
        scope_type: str,
        scope_key: str,
        total_cases: int,
        reviewed_cases: int,
        approved_cases: int,
        rejected_cases: int,
        overridden_cases: int,
        overdue_cases: int,
        breached_cases: int,
        avg_first_review_minutes: float | None,
        avg_decision_minutes: float | None,
        avg_escalation_minutes: float | None,
        window_start: datetime,
        window_end: datetime,
    ) -> ReviewSlaRollup:
        on_time_cases = max(total_cases - breached_cases, 0)
        on_time_rate = (on_time_cases / total_cases) if total_cases > 0 else 1.0
        breach_rate = (breached_cases / total_cases) if total_cases > 0 else 0.0

        model = ReviewSlaRollup(
            id=rollup_id,
            scope_type=scope_type,
            scope_key=scope_key,
            total_cases=total_cases,
            reviewed_cases=reviewed_cases,
            approved_cases=approved_cases,
            rejected_cases=rejected_cases,
            overridden_cases=overridden_cases,
            overdue_cases=overdue_cases,
            breached_cases=breached_cases,
            avg_first_review_minutes=avg_first_review_minutes,
            avg_decision_minutes=avg_decision_minutes,
            avg_escalation_minutes=avg_escalation_minutes,
            sla_breach_rate=breach_rate,
            on_time_rate=on_time_rate,
            window_start=window_start,
            window_end=window_end,
            computed_at=datetime.utcnow(),
        )
        return self.repo.create(model)
4.7 Override effectiveness attribution service
backend/app/services/override_effectiveness_attribution_service.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.override_effectiveness_rollup import OverrideEffectivenessRollup
from app.repositories.override_effectiveness_rollup_repository import OverrideEffectivenessRollupRepository


class OverrideEffectivenessAttributionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OverrideEffectivenessRollupRepository(db)

    def classify_override(
        self,
        *,
        sla_saved: bool,
        conflict_increased: bool,
        rework_triggered: bool,
        execution_failed: bool,
    ) -> str:
        if execution_failed or conflict_increased or rework_triggered:
            return "harmful"
        if sla_saved:
            return "effective"
        return "neutral"

    def build_rollup(
        self,
        *,
        rollup_id: str,
        actor_id: str,
        actor_name: str | None,
        total_overrides: int,
        effective_overrides: int,
        neutral_overrides: int,
        harmful_overrides: int,
        sla_saved_count: int,
        conflict_increase_count: int,
        rework_trigger_count: int,
        failed_execution_count: int,
        window_start: datetime,
        window_end: datetime,
    ) -> OverrideEffectivenessRollup:
        score = 0.0
        if total_overrides > 0:
            score = (
                (effective_overrides * 1.0)
                + (neutral_overrides * 0.2)
                - (harmful_overrides * 1.25)
            ) / total_overrides

        model = OverrideEffectivenessRollup(
            id=rollup_id,
            actor_id=actor_id,
            actor_name=actor_name,
            total_overrides=total_overrides,
            effective_overrides=effective_overrides,
            neutral_overrides=neutral_overrides,
            harmful_overrides=harmful_overrides,
            sla_saved_count=sla_saved_count,
            conflict_increase_count=conflict_increase_count,
            rework_trigger_count=rework_trigger_count,
            failed_execution_count=failed_execution_count,
            effectiveness_score=score,
            window_start=window_start,
            window_end=window_end,
            computed_at=datetime.utcnow(),
        )
        return self.repo.create(model)
4.8 Patch review workflow service
backend/app/services/review_workflow_service.py
Thêm các điểm sau:
# khi assign reviewer
review_case.assigned_reviewer_id = chosen_reviewer_id
review_case.assigned_at = now

# khi first review action xảy ra
if review_case.first_reviewed_at is None:
    review_case.first_reviewed_at = now

# khi decision final
review_case.decided_at = now

# khi supervisor override
review_case.overridden_by = actor_id
review_case.overridden_at = now
review_case.override_reason = override_reason
Và bảo đảm model review case đang có đủ field hoặc patch model tương ứng:
assigned_reviewer_id
assigned_at
first_reviewed_at
decided_at
overridden_by
overridden_at
override_reason
4.9 Patch escalation service
backend/app/services/review_escalation_service.py
Thêm logic:
def should_escalate_due_to_reviewer_overload(
    self,
    reviewer_open_cases: int,
    reviewer_capacity_limit: int,
    overdue_cases: int,
) -> bool:
    if reviewer_open_cases > reviewer_capacity_limit:
        return True
    if overdue_cases >= 3:
        return True
    return False
Và emit reason code:
reviewer_over_capacity
reviewer_overdue_backlog
queue_sla_breach_risk
4.10 Routes
backend/app/api/routes/review_analytics.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.reviewer_workload_repository import ReviewerWorkloadRepository
from app.repositories.review_sla_rollup_repository import ReviewSlaRollupRepository
from app.repositories.override_effectiveness_rollup_repository import OverrideEffectivenessRollupRepository
from app.schemas.reviewer_workload import ReviewerWorkloadRead, ReviewerAssignmentRecommendation
from app.schemas.review_sla import ReviewSlaRollupRead
from app.schemas.override_effectiveness import OverrideEffectivenessRollupRead
from app.services.reviewer_workload_balancing_service import ReviewerWorkloadBalancingService

router = APIRouter(prefix="/review-analytics", tags=["review-analytics"])


@router.get("/reviewers/workload", response_model=list[ReviewerWorkloadRead])
def list_reviewer_workload(db: Session = Depends(get_db)):
    repo = ReviewerWorkloadRepository(db)
    return repo.list_all()


@router.get("/reviewers/recommendations", response_model=list[ReviewerAssignmentRecommendation])
def list_reviewer_recommendations(db: Session = Depends(get_db)):
    svc = ReviewerWorkloadBalancingService(db)
    return svc.suggest_reviewer_for_case()


@router.get("/sla/{scope_type}", response_model=list[ReviewSlaRollupRead])
def list_sla_rollups(scope_type: str, db: Session = Depends(get_db)):
    repo = ReviewSlaRollupRepository(db)
    return repo.list_latest_by_scope_type(scope_type)


@router.get("/overrides/effectiveness", response_model=list[OverrideEffectivenessRollupRead])
def list_override_effectiveness(db: Session = Depends(get_db)):
    repo = OverrideEffectivenessRollupRepository(db)
    return repo.list_latest()
4.11 Wire router
backend/app/api/api_v1/api.py
from app.api.routes import review_analytics

api_router.include_router(review_analytics.router)
4.12 Migration
backend/alembic/versions/phase3_reviewer_balancing_and_analytics.py
from alembic import op
import sqlalchemy as sa


revision = "phase3_reviewer_balancing_and_analytics"
down_revision = "phase3_human_review_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reviewer_workload_snapshot",
        sa.Column("reviewer_id", sa.String(length=64), primary_key=True),
        sa.Column("reviewer_name", sa.String(length=255), nullable=True),
        sa.Column("open_review_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_approval_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overdue_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("escalated_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_first_response_minutes", sa.Float(), nullable=True),
        sa.Column("avg_resolution_minutes", sa.Float(), nullable=True),
        sa.Column("capacity_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("workload_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("availability_score", sa.Float(), nullable=False, server_default="1"),
        sa.Column("last_case_assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "review_sla_rollup",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviewed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approved_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overridden_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overdue_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("breached_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_first_review_minutes", sa.Float(), nullable=True),
        sa.Column("avg_decision_minutes", sa.Float(), nullable=True),
        sa.Column("avg_escalation_minutes", sa.Float(), nullable=True),
        sa.Column("sla_breach_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("on_time_rate", sa.Float(), nullable=False, server_default="1"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_sla_rollup_scope_type", "review_sla_rollup", ["scope_type"])

    op.create_table(
        "override_effectiveness_rollup",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("actor_name", sa.String(length=255), nullable=True),
        sa.Column("total_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("neutral_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("harmful_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sla_saved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflict_increase_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rework_trigger_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_execution_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effectiveness_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_override_effectiveness_actor_id", "override_effectiveness_rollup", ["actor_id"])


def downgrade():
    op.drop_index("ix_override_effectiveness_actor_id", table_name="override_effectiveness_rollup")
    op.drop_table("override_effectiveness_rollup")

    op.drop_index("ix_review_sla_rollup_scope_type", table_name="review_sla_rollup")
    op.drop_table("review_sla_rollup")

    op.drop_table("reviewer_workload_snapshot")
4.13 Worker
backend/app/workers/review_analytics_worker.py
from __future__ import annotations

from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.reviewer_workload_balancing_service import ReviewerWorkloadBalancingService
from app.services.review_sla_analytics_service import ReviewSlaAnalyticsService
from app.services.override_effectiveness_attribution_service import OverrideEffectivenessAttributionService


@celery_app.task(name="review_analytics.refresh")
def refresh_review_analytics():
    db = SessionLocal()
    try:
        workload_svc = ReviewerWorkloadBalancingService(db)
        sla_svc = ReviewSlaAnalyticsService(db)
        override_svc = OverrideEffectivenessAttributionService(db)

        # TODO: thay mock aggregation bằng query thật từ review_case / approval / escalation tables
        workload_svc.materialize_snapshot(
            reviewer_id="reviewer_1",
            reviewer_name="Reviewer 1",
            open_review_cases=3,
            pending_approval_cases=1,
            overdue_cases=0,
            escalated_cases=0,
            avg_first_response_minutes=20.0,
            avg_resolution_minutes=90.0,
            capacity_limit=10,
            availability_score=0.9,
        )

        now = datetime.utcnow()
        window_start = now - timedelta(days=7)

        sla_svc.build_rollup(
            rollup_id=f"global:{now.date()}",
            scope_type="global",
            scope_key="all",
            total_cases=100,
            reviewed_cases=95,
            approved_cases=70,
            rejected_cases=20,
            overridden_cases=5,
            overdue_cases=7,
            breached_cases=8,
            avg_first_review_minutes=35.0,
            avg_decision_minutes=110.0,
            avg_escalation_minutes=55.0,
            window_start=window_start,
            window_end=now,
        )

        override_svc.build_rollup(
            rollup_id=f"supervisor_1:{now.date()}",
            actor_id="supervisor_1",
            actor_name="Supervisor 1",
            total_overrides=8,
            effective_overrides=5,
            neutral_overrides=2,
            harmful_overrides=1,
            sla_saved_count=4,
            conflict_increase_count=1,
            rework_trigger_count=1,
            failed_execution_count=0,
            window_start=window_start,
            window_end=now,
        )

        db.commit()
    finally:
        db.close()
4.14 Tests
backend/tests/services/test_reviewer_workload_balancing_service.py
from app.services.reviewer_workload_balancing_service import ReviewerWorkloadBalancingService, ReviewerCandidate


def test_compute_workload_score_penalizes_overdue(db_session):
    svc = ReviewerWorkloadBalancingService(db_session)

    low = ReviewerCandidate(
        reviewer_id="r1",
        reviewer_name="R1",
        capacity_limit=10,
        open_review_cases=2,
        overdue_cases=0,
        availability_score=1.0,
        avg_resolution_minutes=60.0,
    )
    high = ReviewerCandidate(
        reviewer_id="r2",
        reviewer_name="R2",
        capacity_limit=10,
        open_review_cases=8,
        overdue_cases=3,
        availability_score=0.5,
        avg_resolution_minutes=240.0,
    )

    assert svc.compute_workload_score(high) > svc.compute_workload_score(low)
backend/tests/services/test_review_sla_analytics_service.py
from datetime import datetime, timedelta

from app.services.review_sla_analytics_service import ReviewSlaAnalyticsService


def test_build_rollup_computes_rates(db_session):
    svc = ReviewSlaAnalyticsService(db_session)
    now = datetime.utcnow()

    rollup = svc.build_rollup(
        rollup_id="test",
        scope_type="global",
        scope_key="all",
        total_cases=10,
        reviewed_cases=9,
        approved_cases=6,
        rejected_cases=2,
        overridden_cases=1,
        overdue_cases=2,
        breached_cases=3,
        avg_first_review_minutes=10.0,
        avg_decision_minutes=30.0,
        avg_escalation_minutes=15.0,
        window_start=now - timedelta(days=1),
        window_end=now,
    )

    assert round(rollup.sla_breach_rate, 2) == 0.30
    assert round(rollup.on_time_rate, 2) == 0.70
backend/tests/services/test_override_effectiveness_attribution_service.py
from app.services.override_effectiveness_attribution_service import OverrideEffectivenessAttributionService


def test_classify_override(db_session):
    svc = OverrideEffectivenessAttributionService(db_session)

    assert svc.classify_override(
        sla_saved=True,
        conflict_increased=False,
        rework_triggered=False,
        execution_failed=False,
    ) == "effective"

    assert svc.classify_override(
        sla_saved=False,
        conflict_increased=True,
        rework_triggered=False,
        execution_failed=False,
    ) == "harmful"
FRONTEND
5.1 Types
frontend/src/types/reviewAnalytics.ts
export type ReviewerWorkload = {
  reviewer_id: string;
  reviewer_name?: string | null;
  open_review_cases: number;
  pending_approval_cases: number;
  overdue_cases: number;
  escalated_cases: number;
  avg_first_response_minutes?: number | null;
  avg_resolution_minutes?: number | null;
  capacity_limit: number;
  workload_score: number;
  availability_score: number;
  last_case_assigned_at?: string | null;
  snapshot_at: string;
};

export type ReviewerAssignmentRecommendation = {
  reviewer_id: string;
  reviewer_name?: string | null;
  recommendation_score: number;
  reason_codes: string[];
};

export type ReviewSlaRollup = {
  id: string;
  scope_type: string;
  scope_key: string;
  total_cases: number;
  reviewed_cases: number;
  approved_cases: number;
  rejected_cases: number;
  overridden_cases: number;
  overdue_cases: number;
  breached_cases: number;
  avg_first_review_minutes?: number | null;
  avg_decision_minutes?: number | null;
  avg_escalation_minutes?: number | null;
  sla_breach_rate: number;
  on_time_rate: number;
  window_start: string;
  window_end: string;
  computed_at: string;
};

export type OverrideEffectivenessRollup = {
  id: string;
  actor_id: string;
  actor_name?: string | null;
  total_overrides: number;
  effective_overrides: number;
  neutral_overrides: number;
  harmful_overrides: number;
  sla_saved_count: number;
  conflict_increase_count: number;
  rework_trigger_count: number;
  failed_execution_count: number;
  effectiveness_score: number;
  window_start: string;
  window_end: string;
  computed_at: string;
};
5.2 APIs
frontend/src/api/reviewAnalytics.ts
import { api } from "./client";
import {
  ReviewerWorkload,
  ReviewerAssignmentRecommendation,
  ReviewSlaRollup,
  OverrideEffectivenessRollup,
} from "../types/reviewAnalytics";

export async function fetchReviewerWorkload(): Promise<ReviewerWorkload[]> {
  const res = await api.get("/review-analytics/reviewers/workload");
  return res.data;
}

export async function fetchReviewerRecommendations(): Promise<ReviewerAssignmentRecommendation[]> {
  const res = await api.get("/review-analytics/reviewers/recommendations");
  return res.data;
}

export async function fetchReviewSla(scopeType: string): Promise<ReviewSlaRollup[]> {
  const res = await api.get(`/review-analytics/sla/${scopeType}`);
  return res.data;
}

export async function fetchOverrideEffectiveness(): Promise<OverrideEffectivenessRollup[]> {
  const res = await api.get("/review-analytics/overrides/effectiveness");
  return res.data;
}
5.3 ReviewerWorkloadPanel
frontend/src/components/review/ReviewerWorkloadPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchReviewerWorkload, fetchReviewerRecommendations } from "../../api/reviewAnalytics";
import { ReviewerWorkload, ReviewerAssignmentRecommendation } from "../../types/reviewAnalytics";

export function ReviewerWorkloadPanel() {
  const [workload, setWorkload] = useState<ReviewerWorkload[]>([]);
  const [recommendations, setRecommendations] = useState<ReviewerAssignmentRecommendation[]>([]);

  useEffect(() => {
    void (async () => {
      setWorkload(await fetchReviewerWorkload());
      setRecommendations(await fetchReviewerRecommendations());
    })();
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">Reviewer Workload</h3>
        <div className="mt-2 rounded border">
          {workload.map((r) => (
            <div key={r.reviewer_id} className="border-b p-3">
              <div className="font-medium">{r.reviewer_name || r.reviewer_id}</div>
              <div className="text-sm text-gray-600">
                Open: {r.open_review_cases} · Overdue: {r.overdue_cases} · Pending approval: {r.pending_approval_cases}
              </div>
              <div className="text-sm text-gray-600">
                Workload score: {r.workload_score.toFixed(2)} · Availability: {r.availability_score.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold">Suggested Reviewers</h3>
        <div className="mt-2 rounded border">
          {recommendations.map((r) => (
            <div key={r.reviewer_id} className="border-b p-3">
              <div className="font-medium">{r.reviewer_name || r.reviewer_id}</div>
              <div className="text-sm text-gray-600">
                Recommendation score: {r.recommendation_score.toFixed(2)}
              </div>
              <div className="text-xs text-gray-500">{r.reason_codes.join(", ")}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
5.4 ReviewSLAAnalyticsPanel
frontend/src/components/review/ReviewSLAAnalyticsPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchReviewSla } from "../../api/reviewAnalytics";
import { ReviewSlaRollup } from "../../types/reviewAnalytics";

export function ReviewSLAAnalyticsPanel() {
  const [rows, setRows] = useState<ReviewSlaRollup[]>([]);

  useEffect(() => {
    void (async () => {
      setRows(await fetchReviewSla("global"));
    })();
  }, []);

  return (
    <div>
      <h3 className="text-lg font-semibold">Review SLA Analytics</h3>
      <div className="mt-2 rounded border">
        {rows.map((r) => (
          <div key={r.id} className="border-b p-3">
            <div className="font-medium">{r.scope_key}</div>
            <div className="text-sm text-gray-600">
              Total: {r.total_cases} · Breached: {r.breached_cases} · Overdue: {r.overdue_cases}
            </div>
            <div className="text-sm text-gray-600">
              On-time rate: {(r.on_time_rate * 100).toFixed(1)}% · Breach rate: {(r.sla_breach_rate * 100).toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600">
              Avg first review: {r.avg_first_review_minutes ?? "-"} min · Avg decision: {r.avg_decision_minutes ?? "-"} min
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
5.5 OverrideEffectivenessPanel
frontend/src/components/review/OverrideEffectivenessPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchOverrideEffectiveness } from "../../api/reviewAnalytics";
import { OverrideEffectivenessRollup } from "../../types/reviewAnalytics";

export function OverrideEffectivenessPanel() {
  const [rows, setRows] = useState<OverrideEffectivenessRollup[]>([]);

  useEffect(() => {
    void (async () => {
      setRows(await fetchOverrideEffectiveness());
    })();
  }, []);

  return (
    <div>
      <h3 className="text-lg font-semibold">Override Effectiveness</h3>
      <div className="mt-2 rounded border">
        {rows.map((r) => (
          <div key={r.id} className="border-b p-3">
            <div className="font-medium">{r.actor_name || r.actor_id}</div>
            <div className="text-sm text-gray-600">
              Score: {r.effectiveness_score.toFixed(2)} · Total overrides: {r.total_overrides}
            </div>
            <div className="text-sm text-gray-600">
              Effective: {r.effective_overrides} · Neutral: {r.neutral_overrides} · Harmful: {r.harmful_overrides}
            </div>
            <div className="text-xs text-gray-500">
              SLA saved: {r.sla_saved_count} · Rework: {r.rework_trigger_count} · Failed execution: {r.failed_execution_count}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
5.6 Patch HumanReviewQueuePanel
frontend/src/components/review/HumanReviewQueuePanel.tsx
Bổ sung các điểm hiển thị:
<ReviewerWorkloadPanel />
Và trong từng review case row, thêm:
<div className="text-xs text-amber-600">
  Suggested reviewer: {caseItem.suggested_reviewer_id ?? "n/a"}
</div>
<div className="text-xs text-red-600">
  {caseItem.reviewer_overloaded ? "Reviewer overloaded" : ""}
</div>
5.7 Patch ReviewDecisionPanel
frontend/src/components/review/ReviewDecisionPanel.tsx
Thêm phần hint cho supervisor/operator:
<OverrideEffectivenessPanel />
Và trong block override:
<div className="text-xs text-gray-500">
  Historical override impact will be used to score supervisor effectiveness.
</div>
6) LOGIC THỰC TẾ NÊN DÙNG
Reviewer assignment score
Công thức production gợi ý:
assignment_score = availability_score * 0.35 + speed_score * 0.20 + quality_score * 0.20 - overload_penalty * 0.25
Trong đó:
availability_score: reviewer còn capacity
speed_score: xử lý nhanh
quality_score: ít rework / ít override harmful
overload_penalty: backlog + overdue + escalations
SLA classification
healthy
at_risk
breached
critically_breached
Ví dụ:
healthy: overdue rate < 5%
at_risk: 5–15%
breached: 15–30%
critically_breached: >30%
Override effectiveness scoring
Ví dụ:
effective override = cứu SLA, giảm resolution time, không tạo rework
neutral override = không cứu nhiều nhưng không gây hại
harmful override = conflict, rework, fail execution, churn tăng
7) ĐIỂM MAP RẤT NGẮN KHI PASTE VÀO REPO THẬT
Backend phải có sẵn
Review case model / repository
Phải có hoặc patch thêm các field:
assigned_reviewer_id
assigned_at
first_reviewed_at
decided_at
overridden_by
overridden_at
override_reason
Review workflow service
Phải có nơi ghi nhận:
assign event
first touch event
decision event
override event
Queue / escalation service
Phải có cách xác định:
overdue
breached
escalated
approval pending
Celery app
Phải có worker registry để thêm:
review_analytics.refresh
8) KẾT QUẢ SAU PATCH NÀY
Sau phase này, hệ của bạn sẽ có:
A. Human review không còn “mù tải”
Hệ biết reviewer nào rảnh, reviewer nào quá tải.
B. Auto-assign bắt đầu thông minh thật
Không chỉ “assign được”, mà assign đúng người hơn.
C. SLA governance đo được bằng số
Biết queue nào đang chậm, ai đang gây nghẽn.
D. Supervisor override bắt đầu measurable
Không chỉ log “ai override”, mà đo được override đó tốt hay xấu.
E. Hệ sẵn sàng cho bước tiếp theo
Sau lớp này, bước mạnh nhất tiếp theo sẽ là:
PHASE 3 — AUTO-REBALANCE ACTIONS + REVIEW CAPACITY PLANNING + SUPERVISOR QUALITY SCORING
Vì lúc đó hệ sẽ đi tiếp từ:
biết reviewer nào quá tải
biết override nào hiệu quả
sang:
tự động reassign khi overload
dự báo thiếu capacity theo queue / ca / reviewer
score supervisor theo chất lượng override dài hạn
đề xuất staffing / reviewer allocation
tạo closed-loop governance optimization
Nếu bạn muốn, mình sẽ viết tiếp ngay bản full code file-by-file paste-ready cho phase này, theo đúng format monorepo như các phase trước, gồm luôn các file đã patch hoàn chỉnh thay vì chỉ blueprint.
mình sẽ viết tiếp ngay bản full code file-by-file paste-ready cho phase này, theo đúng format monorepo như các phase trước, gồm luôn các file đã patch hoàn chỉnh thay vì chỉ blueprint.
Mình sẽ đi thẳng vào bản full code theo thứ tự backend trước rồi frontend sau, giữ nguyên kiểu phase trước: file mới nào ra file đó, file patch nào thì đưa đúng phần cần dán đè.
Đã suy nghĩ trong 5s
Dưới đây là bản full code file-by-file paste-ready cho:
PHASE 3 — REVIEWER WORKLOAD BALANCING + REVIEW SLA ANALYTICS + OVERRIDE EFFECTIVENESS ATTRIBUTION
Mình giữ đúng tinh thần:
không tái cấu trúc
bám monorepo production
file nào cần thêm thì thêm
file nào cần patch thì patch đúng điểm
paste-ready
1) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
add models
register imports vào base
add repositories
add schemas
add services
patch existing human review / workflow models nếu thiếu field
patch auto-assign service
patch escalation service
add routes
wire router
add migration
add worker
add tests
Frontend
add types
add APIs
add panels
patch HumanReviewQueuePanel
patch ReviewDecisionPanel
2) BACKEND — FULL FILES
backend/app/models/reviewer_workload_snapshot.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ReviewerWorkloadSnapshot(Base):
    __tablename__ = "reviewer_workload_snapshot"

    reviewer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    open_review_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_approval_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overdue_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    escalated_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    avg_first_response_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_resolution_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    capacity_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    workload_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    availability_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    last_case_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/review_sla_rollup.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ReviewSlaRollup(Base):
    __tablename__ = "review_sla_rollup"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)  # global|queue|reviewer|project
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)

    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overridden_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overdue_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    breached_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    avg_first_review_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_decision_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_escalation_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    sla_breach_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    on_time_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/override_effectiveness_rollup.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class OverrideEffectivenessRollup(Base):
    __tablename__ = "override_effectiveness_rollup"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    total_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    neutral_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    harmful_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sla_saved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_increase_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rework_trigger_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    effectiveness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/db/base.py — PATCH
Thêm imports này vào file base hiện có:
from app.models.reviewer_workload_snapshot import ReviewerWorkloadSnapshot
from app.models.review_sla_rollup import ReviewSlaRollup
from app.models.override_effectiveness_rollup import OverrideEffectivenessRollup
backend/app/repositories/reviewer_workload_repository.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reviewer_workload_snapshot import ReviewerWorkloadSnapshot


class ReviewerWorkloadRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert(self, snapshot: ReviewerWorkloadSnapshot) -> ReviewerWorkloadSnapshot:
        existing = self.db.get(ReviewerWorkloadSnapshot, snapshot.reviewer_id)
        if existing:
            existing.reviewer_name = snapshot.reviewer_name
            existing.open_review_cases = snapshot.open_review_cases
            existing.pending_approval_cases = snapshot.pending_approval_cases
            existing.overdue_cases = snapshot.overdue_cases
            existing.escalated_cases = snapshot.escalated_cases
            existing.avg_first_response_minutes = snapshot.avg_first_response_minutes
            existing.avg_resolution_minutes = snapshot.avg_resolution_minutes
            existing.capacity_limit = snapshot.capacity_limit
            existing.workload_score = snapshot.workload_score
            existing.availability_score = snapshot.availability_score
            existing.last_case_assigned_at = snapshot.last_case_assigned_at
            existing.snapshot_at = snapshot.snapshot_at
            self.db.add(existing)
            return existing

        self.db.add(snapshot)
        return snapshot

    def get(self, reviewer_id: str) -> ReviewerWorkloadSnapshot | None:
        return self.db.get(ReviewerWorkloadSnapshot, reviewer_id)

    def list_all(self) -> list[ReviewerWorkloadSnapshot]:
        stmt = select(ReviewerWorkloadSnapshot).order_by(
            ReviewerWorkloadSnapshot.workload_score.asc(),
            ReviewerWorkloadSnapshot.overdue_cases.asc(),
            ReviewerWorkloadSnapshot.open_review_cases.asc(),
        )
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/review_sla_rollup_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.review_sla_rollup import ReviewSlaRollup


class ReviewSlaRollupRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: ReviewSlaRollup) -> ReviewSlaRollup:
        self.db.add(model)
        return model

    def list_latest_by_scope_type(self, scope_type: str) -> list[ReviewSlaRollup]:
        stmt = (
            select(ReviewSlaRollup)
            .where(ReviewSlaRollup.scope_type == scope_type)
            .order_by(desc(ReviewSlaRollup.computed_at))
        )
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/override_effectiveness_rollup_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.override_effectiveness_rollup import OverrideEffectivenessRollup


class OverrideEffectivenessRollupRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: OverrideEffectivenessRollup) -> OverrideEffectivenessRollup:
        self.db.add(model)
        return model

    def list_latest(self) -> list[OverrideEffectivenessRollup]:
        stmt = select(OverrideEffectivenessRollup).order_by(
            desc(OverrideEffectivenessRollup.effectiveness_score),
            desc(OverrideEffectivenessRollup.computed_at),
        )
        return list(self.db.execute(stmt).scalars().all())
backend/app/schemas/reviewer_workload.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReviewerWorkloadRead(BaseModel):
    reviewer_id: str
    reviewer_name: str | None = None
    open_review_cases: int
    pending_approval_cases: int
    overdue_cases: int
    escalated_cases: int
    avg_first_response_minutes: float | None = None
    avg_resolution_minutes: float | None = None
    capacity_limit: int
    workload_score: float
    availability_score: float
    last_case_assigned_at: datetime | None = None
    snapshot_at: datetime

    class Config:
        from_attributes = True


class ReviewerAssignmentRecommendation(BaseModel):
    reviewer_id: str
    reviewer_name: str | None = None
    recommendation_score: float
    reason_codes: list[str]
backend/app/schemas/review_sla.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReviewSlaRollupRead(BaseModel):
    id: str
    scope_type: str
    scope_key: str
    total_cases: int
    reviewed_cases: int
    approved_cases: int
    rejected_cases: int
    overridden_cases: int
    overdue_cases: int
    breached_cases: int
    avg_first_review_minutes: float | None = None
    avg_decision_minutes: float | None = None
    avg_escalation_minutes: float | None = None
    sla_breach_rate: float
    on_time_rate: float
    window_start: datetime
    window_end: datetime
    computed_at: datetime

    class Config:
        from_attributes = True
backend/app/schemas/override_effectiveness.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OverrideEffectivenessRollupRead(BaseModel):
    id: str
    actor_id: str
    actor_name: str | None = None
    total_overrides: int
    effective_overrides: int
    neutral_overrides: int
    harmful_overrides: int
    sla_saved_count: int
    conflict_increase_count: int
    rework_trigger_count: int
    failed_execution_count: int
    effectiveness_score: float
    window_start: datetime
    window_end: datetime
    computed_at: datetime

    class Config:
        from_attributes = True
backend/app/services/reviewer_workload_balancing_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.reviewer_workload_snapshot import ReviewerWorkloadSnapshot
from app.repositories.reviewer_workload_repository import ReviewerWorkloadRepository
from app.schemas.reviewer_workload import ReviewerAssignmentRecommendation


@dataclass
class ReviewerCandidate:
    reviewer_id: str
    reviewer_name: str | None
    capacity_limit: int
    open_review_cases: int
    overdue_cases: int
    escalated_cases: int
    availability_score: float
    avg_resolution_minutes: float | None


class ReviewerWorkloadBalancingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReviewerWorkloadRepository(db)

    def compute_workload_score(self, c: ReviewerCandidate) -> float:
        load_ratio = c.open_review_cases / max(c.capacity_limit, 1)
        overdue_penalty = c.overdue_cases * 0.30
        escalated_penalty = c.escalated_cases * 0.20
        speed_bonus = 0.0
        if c.avg_resolution_minutes is not None:
            speed_bonus = min(0.25, 180.0 / max(c.avg_resolution_minutes, 1.0) / 10.0)
        availability_bonus = c.availability_score * 0.50
        score = load_ratio + overdue_penalty + escalated_penalty - speed_bonus - availability_bonus
        return max(0.0, score)

    def compute_recommendation_score(self, s: ReviewerWorkloadSnapshot) -> float:
        return max(0.0, 10.0 - s.workload_score)

    def suggest_reviewer_for_case(self) -> list[ReviewerAssignmentRecommendation]:
        snapshots = self.repo.list_all()
        out: list[ReviewerAssignmentRecommendation] = []

        for s in snapshots:
            reasons: list[str] = []
            if s.open_review_cases < s.capacity_limit:
                reasons.append("under_capacity")
            if s.overdue_cases == 0:
                reasons.append("no_overdue")
            if s.escalated_cases == 0:
                reasons.append("stable_queue")
            if s.availability_score >= 0.8:
                reasons.append("high_availability")

            out.append(
                ReviewerAssignmentRecommendation(
                    reviewer_id=s.reviewer_id,
                    reviewer_name=s.reviewer_name,
                    recommendation_score=self.compute_recommendation_score(s),
                    reason_codes=reasons,
                )
            )

        out.sort(key=lambda x: x.recommendation_score, reverse=True)
        return out

    def materialize_snapshot(
        self,
        *,
        reviewer_id: str,
        reviewer_name: str | None,
        open_review_cases: int,
        pending_approval_cases: int,
        overdue_cases: int,
        escalated_cases: int,
        avg_first_response_minutes: float | None,
        avg_resolution_minutes: float | None,
        capacity_limit: int = 10,
        availability_score: float = 1.0,
        last_case_assigned_at: datetime | None = None,
    ) -> ReviewerWorkloadSnapshot:
        candidate = ReviewerCandidate(
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            capacity_limit=capacity_limit,
            open_review_cases=open_review_cases,
            overdue_cases=overdue_cases,
            escalated_cases=escalated_cases,
            availability_score=availability_score,
            avg_resolution_minutes=avg_resolution_minutes,
        )
        workload_score = self.compute_workload_score(candidate)

        model = ReviewerWorkloadSnapshot(
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            open_review_cases=open_review_cases,
            pending_approval_cases=pending_approval_cases,
            overdue_cases=overdue_cases,
            escalated_cases=escalated_cases,
            avg_first_response_minutes=avg_first_response_minutes,
            avg_resolution_minutes=avg_resolution_minutes,
            capacity_limit=capacity_limit,
            workload_score=workload_score,
            availability_score=availability_score,
            last_case_assigned_at=last_case_assigned_at,
            snapshot_at=datetime.utcnow(),
        )
        return self.repo.upsert(model)
backend/app/services/review_sla_analytics_service.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.review_sla_rollup import ReviewSlaRollup
from app.repositories.review_sla_rollup_repository import ReviewSlaRollupRepository


class ReviewSlaAnalyticsService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReviewSlaRollupRepository(db)

    def build_rollup(
        self,
        *,
        rollup_id: str,
        scope_type: str,
        scope_key: str,
        total_cases: int,
        reviewed_cases: int,
        approved_cases: int,
        rejected_cases: int,
        overridden_cases: int,
        overdue_cases: int,
        breached_cases: int,
        avg_first_review_minutes: float | None,
        avg_decision_minutes: float | None,
        avg_escalation_minutes: float | None,
        window_start: datetime,
        window_end: datetime,
    ) -> ReviewSlaRollup:
        on_time_cases = max(total_cases - breached_cases, 0)
        on_time_rate = (on_time_cases / total_cases) if total_cases > 0 else 1.0
        sla_breach_rate = (breached_cases / total_cases) if total_cases > 0 else 0.0

        model = ReviewSlaRollup(
            id=rollup_id,
            scope_type=scope_type,
            scope_key=scope_key,
            total_cases=total_cases,
            reviewed_cases=reviewed_cases,
            approved_cases=approved_cases,
            rejected_cases=rejected_cases,
            overridden_cases=overridden_cases,
            overdue_cases=overdue_cases,
            breached_cases=breached_cases,
            avg_first_review_minutes=avg_first_review_minutes,
            avg_decision_minutes=avg_decision_minutes,
            avg_escalation_minutes=avg_escalation_minutes,
            sla_breach_rate=sla_breach_rate,
            on_time_rate=on_time_rate,
            window_start=window_start,
            window_end=window_end,
            computed_at=datetime.utcnow(),
        )
        return self.repo.create(model)
backend/app/services/override_effectiveness_attribution_service.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.override_effectiveness_rollup import OverrideEffectivenessRollup
from app.repositories.override_effectiveness_rollup_repository import OverrideEffectivenessRollupRepository


class OverrideEffectivenessAttributionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OverrideEffectivenessRollupRepository(db)

    def classify_override(
        self,
        *,
        sla_saved: bool,
        conflict_increased: bool,
        rework_triggered: bool,
        execution_failed: bool,
    ) -> str:
        if execution_failed or conflict_increased or rework_triggered:
            return "harmful"
        if sla_saved:
            return "effective"
        return "neutral"

    def compute_effectiveness_score(
        self,
        *,
        total_overrides: int,
        effective_overrides: int,
        neutral_overrides: int,
        harmful_overrides: int,
    ) -> float:
        if total_overrides <= 0:
            return 0.0

        weighted = (
            effective_overrides * 1.0
            + neutral_overrides * 0.20
            - harmful_overrides * 1.25
        )
        return weighted / total_overrides

    def build_rollup(
        self,
        *,
        rollup_id: str,
        actor_id: str,
        actor_name: str | None,
        total_overrides: int,
        effective_overrides: int,
        neutral_overrides: int,
        harmful_overrides: int,
        sla_saved_count: int,
        conflict_increase_count: int,
        rework_trigger_count: int,
        failed_execution_count: int,
        window_start: datetime,
        window_end: datetime,
    ) -> OverrideEffectivenessRollup:
        score = self.compute_effectiveness_score(
            total_overrides=total_overrides,
            effective_overrides=effective_overrides,
            neutral_overrides=neutral_overrides,
            harmful_overrides=harmful_overrides,
        )

        model = OverrideEffectivenessRollup(
            id=rollup_id,
            actor_id=actor_id,
            actor_name=actor_name,
            total_overrides=total_overrides,
            effective_overrides=effective_overrides,
            neutral_overrides=neutral_overrides,
            harmful_overrides=harmful_overrides,
            sla_saved_count=sla_saved_count,
            conflict_increase_count=conflict_increase_count,
            rework_trigger_count=rework_trigger_count,
            failed_execution_count=failed_execution_count,
            effectiveness_score=score,
            window_start=window_start,
            window_end=window_end,
            computed_at=datetime.utcnow(),
        )
        return self.repo.create(model)
3) BACKEND — PATCH CÁC FILE ĐANG CÓ
backend/app/models/human_review_case.py — PATCH
Nếu model review case hiện tại chưa có các field dưới đây thì thêm:
from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

assigned_reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

first_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

overridden_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
override_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

suggested_reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
reviewer_overloaded: Mapped[bool] = mapped_column(nullable=False, default=False)

time_to_first_review_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
time_to_decision_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
backend/app/services/review_workflow_service.py — PATCH
Thêm helper:
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
Trong logic assign reviewer:
now = _utcnow()
review_case.assigned_reviewer_id = reviewer_id
review_case.assigned_at = now
review_case.suggested_reviewer_id = reviewer_id
Trong logic first review action:
now = _utcnow()
if review_case.first_reviewed_at is None:
    review_case.first_reviewed_at = now
    if getattr(review_case, "created_at", None):
        delta = now - review_case.created_at
        review_case.time_to_first_review_minutes = round(delta.total_seconds() / 60.0, 2)
Trong logic approve / reject final decision:
now = _utcnow()
review_case.decided_at = now
if getattr(review_case, "created_at", None):
    delta = now - review_case.created_at
    review_case.time_to_decision_minutes = round(delta.total_seconds() / 60.0, 2)
Trong logic supervisor override:
now = _utcnow()
review_case.overridden_by = actor_id
review_case.overridden_at = now
review_case.override_reason = override_reason
backend/app/services/review_queue_service.py — PATCH
Thêm helper hoặc logic tương đương để mark overdue / breach risk:
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_case_overdue(case, sla_minutes: int) -> bool:
    if getattr(case, "status", None) in {"approved", "rejected", "closed"}:
        return False
    created_at = getattr(case, "created_at", None)
    if created_at is None:
        return False
    age_minutes = (_utcnow() - created_at).total_seconds() / 60.0
    return age_minutes > sla_minutes
backend/app/services/auto_assign_service.py — PATCH
Chỗ tạo review case hoặc assign case, thêm:
from app.services.reviewer_workload_balancing_service import ReviewerWorkloadBalancingService

balancing_service = ReviewerWorkloadBalancingService(self.db)
recommendations = balancing_service.suggest_reviewer_for_case()

if recommendations:
    best = recommendations[0]
    review_case.suggested_reviewer_id = best.reviewer_id
    review_case.assigned_reviewer_id = best.reviewer_id
    review_case.reviewer_overloaded = best.recommendation_score < 3.0
else:
    review_case.suggested_reviewer_id = None
    review_case.reviewer_overloaded = False
Nếu bạn đang có policy “human approval required before actual assign”, thì chỉ set:
review_case.suggested_reviewer_id = best.reviewer_id
review_case.reviewer_overloaded = best.recommendation_score < 3.0
backend/app/services/review_escalation_service.py — PATCH
def should_escalate_due_to_reviewer_overload(
    self,
    *,
    reviewer_open_cases: int,
    reviewer_capacity_limit: int,
    overdue_cases: int,
) -> bool:
    if reviewer_open_cases > reviewer_capacity_limit:
        return True
    if overdue_cases >= 3:
        return True
    return False


def build_escalation_reason_codes(
    self,
    *,
    reviewer_open_cases: int,
    reviewer_capacity_limit: int,
    overdue_cases: int,
    queue_sla_breach_risk: bool,
) -> list[str]:
    reasons: list[str] = []
    if reviewer_open_cases > reviewer_capacity_limit:
        reasons.append("reviewer_over_capacity")
    if overdue_cases >= 3:
        reasons.append("reviewer_overdue_backlog")
    if queue_sla_breach_risk:
        reasons.append("queue_sla_breach_risk")
    return reasons
4) BACKEND — ROUTES
backend/app/api/routes/review_analytics.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.override_effectiveness_rollup_repository import (
    OverrideEffectivenessRollupRepository,
)
from app.repositories.reviewer_workload_repository import ReviewerWorkloadRepository
from app.repositories.review_sla_rollup_repository import ReviewSlaRollupRepository
from app.schemas.override_effectiveness import OverrideEffectivenessRollupRead
from app.schemas.reviewer_workload import (
    ReviewerAssignmentRecommendation,
    ReviewerWorkloadRead,
)
from app.schemas.review_sla import ReviewSlaRollupRead
from app.services.reviewer_workload_balancing_service import ReviewerWorkloadBalancingService

router = APIRouter(prefix="/review-analytics", tags=["review-analytics"])


@router.get("/reviewers/workload", response_model=list[ReviewerWorkloadRead])
def list_reviewer_workload(db: Session = Depends(get_db)):
    repo = ReviewerWorkloadRepository(db)
    return repo.list_all()


@router.get("/reviewers/recommendations", response_model=list[ReviewerAssignmentRecommendation])
def list_reviewer_recommendations(db: Session = Depends(get_db)):
    svc = ReviewerWorkloadBalancingService(db)
    return svc.suggest_reviewer_for_case()


@router.get("/sla/{scope_type}", response_model=list[ReviewSlaRollupRead])
def list_sla_rollups(scope_type: str, db: Session = Depends(get_db)):
    repo = ReviewSlaRollupRepository(db)
    return repo.list_latest_by_scope_type(scope_type)


@router.get("/overrides/effectiveness", response_model=list[OverrideEffectivenessRollupRead])
def list_override_effectiveness(db: Session = Depends(get_db)):
    repo = OverrideEffectivenessRollupRepository(db)
    return repo.list_latest()
backend/app/api/api_v1/api.py — PATCH
Thêm:
from app.api.routes import review_analytics
Và include router:
api_router.include_router(review_analytics.router)
5) BACKEND — MIGRATION
backend/alembic/versions/phase3_reviewer_balancing_and_analytics.py
from alembic import op
import sqlalchemy as sa


revision = "phase3_reviewer_balancing_and_analytics"
down_revision = "phase3_human_review_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reviewer_workload_snapshot",
        sa.Column("reviewer_id", sa.String(length=64), primary_key=True),
        sa.Column("reviewer_name", sa.String(length=255), nullable=True),
        sa.Column("open_review_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_approval_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overdue_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("escalated_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_first_response_minutes", sa.Float(), nullable=True),
        sa.Column("avg_resolution_minutes", sa.Float(), nullable=True),
        sa.Column("capacity_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("workload_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("availability_score", sa.Float(), nullable=False, server_default="1"),
        sa.Column("last_case_assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "review_sla_rollup",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviewed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approved_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overridden_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overdue_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("breached_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_first_review_minutes", sa.Float(), nullable=True),
        sa.Column("avg_decision_minutes", sa.Float(), nullable=True),
        sa.Column("avg_escalation_minutes", sa.Float(), nullable=True),
        sa.Column("sla_breach_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("on_time_rate", sa.Float(), nullable=False, server_default="1"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_review_sla_rollup_scope_type",
        "review_sla_rollup",
        ["scope_type"],
    )

    op.create_table(
        "override_effectiveness_rollup",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("actor_name", sa.String(length=255), nullable=True),
        sa.Column("total_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("neutral_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("harmful_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sla_saved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflict_increase_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rework_trigger_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_execution_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effectiveness_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_override_effectiveness_actor_id",
        "override_effectiveness_rollup",
        ["actor_id"],
    )

    # Optional patch existing human_review_case table if fields are missing.
    # Uncomment only if your current repo does not already have them.
    #
    # op.add_column("human_review_case", sa.Column("assigned_reviewer_id", sa.String(length=64), nullable=True))
    # op.add_column("human_review_case", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
    # op.add_column("human_review_case", sa.Column("first_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    # op.add_column("human_review_case", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    # op.add_column("human_review_case", sa.Column("overridden_by", sa.String(length=64), nullable=True))
    # op.add_column("human_review_case", sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True))
    # op.add_column("human_review_case", sa.Column("override_reason", sa.String(length=1000), nullable=True))
    # op.add_column("human_review_case", sa.Column("suggested_reviewer_id", sa.String(length=64), nullable=True))
    # op.add_column("human_review_case", sa.Column("reviewer_overloaded", sa.Boolean(), nullable=False, server_default=sa.false()))
    # op.add_column("human_review_case", sa.Column("time_to_first_review_minutes", sa.Float(), nullable=True))
    # op.add_column("human_review_case", sa.Column("time_to_decision_minutes", sa.Float(), nullable=True))


def downgrade():
    op.drop_index("ix_override_effectiveness_actor_id", table_name="override_effectiveness_rollup")
    op.drop_table("override_effectiveness_rollup")

    op.drop_index("ix_review_sla_rollup_scope_type", table_name="review_sla_rollup")
    op.drop_table("review_sla_rollup")

    op.drop_table("reviewer_workload_snapshot")
6) BACKEND — WORKER
backend/app/workers/review_analytics_worker.py
from __future__ import annotations

from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.override_effectiveness_attribution_service import (
    OverrideEffectivenessAttributionService,
)
from app.services.reviewer_workload_balancing_service import (
    ReviewerWorkloadBalancingService,
)
from app.services.review_sla_analytics_service import ReviewSlaAnalyticsService


@celery_app.task(name="review_analytics.refresh")
def refresh_review_analytics():
    db = SessionLocal()
    try:
        workload_svc = ReviewerWorkloadBalancingService(db)
        sla_svc = ReviewSlaAnalyticsService(db)
        override_svc = OverrideEffectivenessAttributionService(db)

        # TODO:
        # Replace the mock aggregates below with real aggregation queries
        # from human_review_case / governance approval / escalation tables.

        workload_svc.materialize_snapshot(
            reviewer_id="reviewer_1",
            reviewer_name="Reviewer 1",
            open_review_cases=3,
            pending_approval_cases=1,
            overdue_cases=0,
            escalated_cases=0,
            avg_first_response_minutes=20.0,
            avg_resolution_minutes=90.0,
            capacity_limit=10,
            availability_score=0.95,
        )

        workload_svc.materialize_snapshot(
            reviewer_id="reviewer_2",
            reviewer_name="Reviewer 2",
            open_review_cases=9,
            pending_approval_cases=3,
            overdue_cases=2,
            escalated_cases=1,
            avg_first_response_minutes=55.0,
            avg_resolution_minutes=200.0,
            capacity_limit=10,
            availability_score=0.60,
        )

        now = datetime.utcnow()
        window_start = now - timedelta(days=7)

        sla_svc.build_rollup(
            rollup_id=f"global:{now.date()}",
            scope_type="global",
            scope_key="all",
            total_cases=100,
            reviewed_cases=94,
            approved_cases=66,
            rejected_cases=23,
            overridden_cases=5,
            overdue_cases=8,
            breached_cases=7,
            avg_first_review_minutes=32.0,
            avg_decision_minutes=105.0,
            avg_escalation_minutes=58.0,
            window_start=window_start,
            window_end=now,
        )

        sla_svc.build_rollup(
            rollup_id=f"queue:human_review:{now.date()}",
            scope_type="queue",
            scope_key="human_review",
            total_cases=61,
            reviewed_cases=56,
            approved_cases=38,
            rejected_cases=15,
            overridden_cases=3,
            overdue_cases=6,
            breached_cases=5,
            avg_first_review_minutes=36.0,
            avg_decision_minutes=112.0,
            avg_escalation_minutes=60.0,
            window_start=window_start,
            window_end=now,
        )

        override_svc.build_rollup(
            rollup_id=f"supervisor_1:{now.date()}",
            actor_id="supervisor_1",
            actor_name="Supervisor 1",
            total_overrides=8,
            effective_overrides=5,
            neutral_overrides=2,
            harmful_overrides=1,
            sla_saved_count=4,
            conflict_increase_count=1,
            rework_trigger_count=1,
            failed_execution_count=0,
            window_start=window_start,
            window_end=now,
        )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
7) BACKEND — TESTS
backend/tests/services/test_reviewer_workload_balancing_service.py
from app.services.reviewer_workload_balancing_service import (
    ReviewerCandidate,
    ReviewerWorkloadBalancingService,
)


def test_compute_workload_score_penalizes_overload_and_overdue(db_session):
    svc = ReviewerWorkloadBalancingService(db_session)

    low = ReviewerCandidate(
        reviewer_id="r1",
        reviewer_name="R1",
        capacity_limit=10,
        open_review_cases=2,
        overdue_cases=0,
        escalated_cases=0,
        availability_score=1.0,
        avg_resolution_minutes=60.0,
    )
    high = ReviewerCandidate(
        reviewer_id="r2",
        reviewer_name="R2",
        capacity_limit=10,
        open_review_cases=9,
        overdue_cases=3,
        escalated_cases=2,
        availability_score=0.5,
        avg_resolution_minutes=240.0,
    )

    assert svc.compute_workload_score(high) > svc.compute_workload_score(low)


def test_suggest_reviewer_orders_best_first(db_session):
    svc = ReviewerWorkloadBalancingService(db_session)

    svc.materialize_snapshot(
        reviewer_id="best",
        reviewer_name="Best",
        open_review_cases=1,
        pending_approval_cases=0,
        overdue_cases=0,
        escalated_cases=0,
        avg_first_response_minutes=10.0,
        avg_resolution_minutes=40.0,
        capacity_limit=10,
        availability_score=1.0,
    )
    svc.materialize_snapshot(
        reviewer_id="busy",
        reviewer_name="Busy",
        open_review_cases=9,
        pending_approval_cases=2,
        overdue_cases=2,
        escalated_cases=1,
        avg_first_response_minutes=60.0,
        avg_resolution_minutes=180.0,
        capacity_limit=10,
        availability_score=0.4,
    )

    rows = svc.suggest_reviewer_for_case()
    assert rows[0].reviewer_id == "best"
backend/tests/services/test_review_sla_analytics_service.py
from datetime import datetime, timedelta

from app.services.review_sla_analytics_service import ReviewSlaAnalyticsService


def test_build_rollup_computes_breach_and_on_time_rates(db_session):
    svc = ReviewSlaAnalyticsService(db_session)
    now = datetime.utcnow()

    row = svc.build_rollup(
        rollup_id="rollup_1",
        scope_type="global",
        scope_key="all",
        total_cases=10,
        reviewed_cases=9,
        approved_cases=6,
        rejected_cases=2,
        overridden_cases=1,
        overdue_cases=2,
        breached_cases=3,
        avg_first_review_minutes=15.0,
        avg_decision_minutes=30.0,
        avg_escalation_minutes=12.0,
        window_start=now - timedelta(days=1),
        window_end=now,
    )

    assert round(row.sla_breach_rate, 2) == 0.30
    assert round(row.on_time_rate, 2) == 0.70
backend/tests/services/test_override_effectiveness_attribution_service.py
from datetime import datetime, timedelta

from app.services.override_effectiveness_attribution_service import (
    OverrideEffectivenessAttributionService,
)


def test_classify_override(db_session):
    svc = OverrideEffectivenessAttributionService(db_session)

    assert svc.classify_override(
        sla_saved=True,
        conflict_increased=False,
        rework_triggered=False,
        execution_failed=False,
    ) == "effective"

    assert svc.classify_override(
        sla_saved=False,
        conflict_increased=True,
        rework_triggered=False,
        execution_failed=False,
    ) == "harmful"

    assert svc.classify_override(
        sla_saved=False,
        conflict_increased=False,
        rework_triggered=False,
        execution_failed=False,
    ) == "neutral"


def test_build_rollup_score(db_session):
    svc = OverrideEffectivenessAttributionService(db_session)
    now = datetime.utcnow()

    row = svc.build_rollup(
        rollup_id="ovr_1",
        actor_id="sup_1",
        actor_name="Supervisor 1",
        total_overrides=10,
        effective_overrides=6,
        neutral_overrides=2,
        harmful_overrides=2,
        sla_saved_count=4,
        conflict_increase_count=1,
        rework_trigger_count=1,
        failed_execution_count=0,
        window_start=now - timedelta(days=7),
        window_end=now,
    )

    assert row.effectiveness_score != 0.0
8) FRONTEND — FULL FILES
frontend/src/types/reviewAnalytics.ts
export type ReviewerWorkload = {
  reviewer_id: string;
  reviewer_name?: string | null;
  open_review_cases: number;
  pending_approval_cases: number;
  overdue_cases: number;
  escalated_cases: number;
  avg_first_response_minutes?: number | null;
  avg_resolution_minutes?: number | null;
  capacity_limit: number;
  workload_score: number;
  availability_score: number;
  last_case_assigned_at?: string | null;
  snapshot_at: string;
};

export type ReviewerAssignmentRecommendation = {
  reviewer_id: string;
  reviewer_name?: string | null;
  recommendation_score: number;
  reason_codes: string[];
};

export type ReviewSlaRollup = {
  id: string;
  scope_type: string;
  scope_key: string;
  total_cases: number;
  reviewed_cases: number;
  approved_cases: number;
  rejected_cases: number;
  overridden_cases: number;
  overdue_cases: number;
  breached_cases: number;
  avg_first_review_minutes?: number | null;
  avg_decision_minutes?: number | null;
  avg_escalation_minutes?: number | null;
  sla_breach_rate: number;
  on_time_rate: number;
  window_start: string;
  window_end: string;
  computed_at: string;
};

export type OverrideEffectivenessRollup = {
  id: string;
  actor_id: string;
  actor_name?: string | null;
  total_overrides: number;
  effective_overrides: number;
  neutral_overrides: number;
  harmful_overrides: number;
  sla_saved_count: number;
  conflict_increase_count: number;
  rework_trigger_count: number;
  failed_execution_count: number;
  effectiveness_score: number;
  window_start: string;
  window_end: string;
  computed_at: string;
};
frontend/src/api/reviewAnalytics.ts
import { api } from "./client";
import {
  OverrideEffectivenessRollup,
  ReviewerAssignmentRecommendation,
  ReviewerWorkload,
  ReviewSlaRollup,
} from "../types/reviewAnalytics";

export async function fetchReviewerWorkload(): Promise<ReviewerWorkload[]> {
  const res = await api.get("/review-analytics/reviewers/workload");
  return res.data;
}

export async function fetchReviewerRecommendations(): Promise<ReviewerAssignmentRecommendation[]> {
  const res = await api.get("/review-analytics/reviewers/recommendations");
  return res.data;
}

export async function fetchReviewSla(scopeType: string): Promise<ReviewSlaRollup[]> {
  const res = await api.get(`/review-analytics/sla/${scopeType}`);
  return res.data;
}

export async function fetchOverrideEffectiveness(): Promise<OverrideEffectivenessRollup[]> {
  const res = await api.get("/review-analytics/overrides/effectiveness");
  return res.data;
}
frontend/src/components/review/ReviewerWorkloadPanel.tsx
import React, { useEffect, useState } from "react";
import {
  fetchReviewerRecommendations,
  fetchReviewerWorkload,
} from "../../api/reviewAnalytics";
import {
  ReviewerAssignmentRecommendation,
  ReviewerWorkload,
} from "../../types/reviewAnalytics";

export function ReviewerWorkloadPanel() {
  const [rows, setRows] = useState<ReviewerWorkload[]>([]);
  const [recommendations, setRecommendations] = useState<ReviewerAssignmentRecommendation[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      const [workloadRows, recommendationRows] = await Promise.all([
        fetchReviewerWorkload(),
        fetchReviewerRecommendations(),
      ]);
      setRows(workloadRows);
      setRecommendations(recommendationRows);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Reviewer Workload</h3>
        <button
          className="rounded border px-3 py-1 text-sm"
          onClick={() => void load()}
          disabled={loading}
        >
          Refresh
        </button>
      </div>

      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.reviewer_id} className="rounded border p-3">
            <div className="font-medium">{r.reviewer_name || r.reviewer_id}</div>
            <div className="mt-1 text-sm text-gray-600">
              Open: {r.open_review_cases} · Pending approval: {r.pending_approval_cases} ·
              Overdue: {r.overdue_cases} · Escalated: {r.escalated_cases}
            </div>
            <div className="mt-1 text-sm text-gray-600">
              Capacity: {r.capacity_limit} · Workload score: {r.workload_score.toFixed(2)} ·
              Availability: {r.availability_score.toFixed(2)}
            </div>
            <div className="mt-1 text-xs text-gray-500">
              Avg first response: {r.avg_first_response_minutes ?? "-"} min · Avg resolution:{" "}
              {r.avg_resolution_minutes ?? "-"} min
            </div>
          </div>
        ))}
        {!rows.length && !loading && (
          <div className="text-sm text-gray-500">No workload data.</div>
        )}
      </div>

      <div>
        <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Suggested Reviewers
        </h4>
        <div className="space-y-2">
          {recommendations.map((r) => (
            <div key={r.reviewer_id} className="rounded border p-3">
              <div className="font-medium">{r.reviewer_name || r.reviewer_id}</div>
              <div className="text-sm text-gray-600">
                Recommendation score: {r.recommendation_score.toFixed(2)}
              </div>
              <div className="text-xs text-gray-500">{r.reason_codes.join(", ")}</div>
            </div>
          ))}
          {!recommendations.length && !loading && (
            <div className="text-sm text-gray-500">No recommendation data.</div>
          )}
        </div>
      </div>
    </div>
  );
}
frontend/src/components/review/ReviewSLAAnalyticsPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchReviewSla } from "../../api/reviewAnalytics";
import { ReviewSlaRollup } from "../../types/reviewAnalytics";

type Props = {
  scopeType?: string;
};

export function ReviewSLAAnalyticsPanel({ scopeType = "global" }: Props) {
  const [rows, setRows] = useState<ReviewSlaRollup[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load(scopeType);
  }, [scopeType]);

  async function load(nextScopeType: string) {
    setLoading(true);
    try {
      const data = await fetchReviewSla(nextScopeType);
      setRows(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Review SLA Analytics</h3>
        <button
          className="rounded border px-3 py-1 text-sm"
          onClick={() => void load(scopeType)}
          disabled={loading}
        >
          Refresh
        </button>
      </div>

      {rows.map((r) => (
        <div key={r.id} className="rounded border p-3">
          <div className="font-medium">
            {r.scope_type} / {r.scope_key}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Total: {r.total_cases} · Reviewed: {r.reviewed_cases} · Approved: {r.approved_cases} ·
            Rejected: {r.rejected_cases}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Overdue: {r.overdue_cases} · Breached: {r.breached_cases} · Overridden:{" "}
            {r.overridden_cases}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            On-time: {(r.on_time_rate * 100).toFixed(1)}% · Breach:{" "}
            {(r.sla_breach_rate * 100).toFixed(1)}%
          </div>
          <div className="mt-1 text-xs text-gray-500">
            Avg first review: {r.avg_first_review_minutes ?? "-"} min · Avg decision:{" "}
            {r.avg_decision_minutes ?? "-"} min · Avg escalation:{" "}
            {r.avg_escalation_minutes ?? "-"} min
          </div>
        </div>
      ))}

      {!rows.length && !loading && (
        <div className="text-sm text-gray-500">No SLA analytics data.</div>
      )}
    </div>
  );
}
frontend/src/components/review/OverrideEffectivenessPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchOverrideEffectiveness } from "../../api/reviewAnalytics";
import { OverrideEffectivenessRollup } from "../../types/reviewAnalytics";

export function OverrideEffectivenessPanel() {
  const [rows, setRows] = useState<OverrideEffectivenessRollup[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchOverrideEffectiveness();
      setRows(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Override Effectiveness</h3>
        <button
          className="rounded border px-3 py-1 text-sm"
          onClick={() => void load()}
          disabled={loading}
        >
          Refresh
        </button>
      </div>

      {rows.map((r) => (
        <div key={r.id} className="rounded border p-3">
          <div className="font-medium">{r.actor_name || r.actor_id}</div>
          <div className="mt-1 text-sm text-gray-600">
            Score: {r.effectiveness_score.toFixed(2)} · Total overrides: {r.total_overrides}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Effective: {r.effective_overrides} · Neutral: {r.neutral_overrides} · Harmful:{" "}
            {r.harmful_overrides}
          </div>
          <div className="mt-1 text-xs text-gray-500">
            SLA saved: {r.sla_saved_count} · Conflict increase: {r.conflict_increase_count} ·
            Rework: {r.rework_trigger_count} · Failed execution: {r.failed_execution_count}
          </div>
        </div>
      ))}

      {!rows.length && !loading && (
        <div className="text-sm text-gray-500">No override effectiveness data.</div>
      )}
    </div>
  );
}
9) FRONTEND — PATCH CÁC FILE ĐANG CÓ
frontend/src/components/review/HumanReviewQueuePanel.tsx — PATCH
Nếu panel hiện đang render danh sách case, patch thêm:
import { ReviewerWorkloadPanel } from "./ReviewerWorkloadPanel";
Trong JSX, thêm block trên đầu hoặc cạnh queue:
<ReviewerWorkloadPanel />
Trong từng row của review case, thêm:
<div className="mt-1 text-xs text-amber-700">
  Suggested reviewer: {caseItem.suggested_reviewer_id ?? "n/a"}
</div>

{caseItem.reviewer_overloaded ? (
  <div className="mt-1 text-xs text-red-600">Reviewer overloaded</div>
) : null}
Nếu row đã có assignee:
<div className="mt-1 text-xs text-gray-500">
  Assigned reviewer: {caseItem.assigned_reviewer_id ?? "unassigned"}
</div>
frontend/src/components/review/ReviewDecisionPanel.tsx — PATCH
Thêm import:
import { OverrideEffectivenessPanel } from "./OverrideEffectivenessPanel";
import { ReviewSLAAnalyticsPanel } from "./ReviewSLAAnalyticsPanel";
Trong JSX, thêm:
<ReviewSLAAnalyticsPanel scopeType="global" />
<OverrideEffectivenessPanel />
Trong block override info của case, thêm:
<div className="mt-2 text-xs text-gray-500">
  Historical override impact is tracked and used to score supervisor effectiveness.
</div>
Nếu case có override fields:
{caseItem.overridden_by ? (
  <div className="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
    Overridden by: {caseItem.overridden_by}
    <br />
    Reason: {caseItem.override_reason ?? "n/a"}
  </div>
) : null}
10) CÁC ĐIỂM MAP QUAN TRỌNG KHI DÁN VÀO REPO THẬT
A. Nếu repo đang dùng Base = declarative_base()
Giữ nguyên, chỉ cần import model vào db/base.py.
B. Nếu repo đang dùng repository naming khác
Bạn chỉ cần map đúng tên class, logic giữ nguyên.
C. Nếu repo đang có HumanReviewCase tên khác
Patch vào model tương ứng của queue review hiện tại.
D. Nếu repo đang có router tree khác
Chỉ cần include review_analytics.router ở root API hiện tại.
E. Nếu worker registry không auto-discover
Thêm import worker vào bootstrap Celery hoặc module startup hiện tại.
Ví dụ:
import app.workers.review_analytics_worker
11) ĐIỂM THẬT SỰ QUAN TRỌNG Ở BẢN NÀY
Bản này đã đưa hệ lên đúng lớp:
reviewer-aware governance
Cụ thể:
biết reviewer nào nhẹ tải
biết reviewer nào nặng tải
biết queue SLA có đang xấu hay không
biết override của supervisor có đáng tin hay không
Tức là từ đây trở đi, hệ có thể bước tiếp sang:
PHASE 3 — AUTO-REBALANCE ACTIONS + REVIEW CAPACITY PLANNING + SUPERVISOR QUALITY SCORING
khi đó hệ sẽ làm tiếp được:
auto reassign khi reviewer overload
capacity forecast theo queue
reviewer staffing recommendation
supervisor quality score dài hạn
governance optimization loop khép kín
12) BƯỚC DÁN THỰC TẾ NHANH NHẤT
Nếu bạn muốn paste vào repo thật theo cách ít lỗi nhất, hãy làm đúng thứ tự này:
tạo 3 model mới
import vào db/base.py
tạo 3 repository
tạo 3 schema
tạo 3 service
tạo route review_analytics.py
wire router
thêm worker
chạy migration
patch model review case
patch workflow/assign/escalation
patch frontend types/api/components
chạy tests
Ở lượt tiếp theo mình sẽ viết tiếp ngay PHASE 3 — AUTO-REBALANCE ACTIONS + REVIEW CAPACITY PLANNING + SUPERVISOR QUALITY SCORING cũng theo đúng format full code file-by-file paste-ready.
viết tiếp ngay PHASE 3 — AUTO-REBALANCE ACTIONS + REVIEW CAPACITY PLANNING + SUPERVISOR QUALITY SCORING cũng theo đúng format full code file-by-file paste-ready.
Mình nối tiếp ngay phase kế tiếp theo đúng trục phase trước: thêm action layer để tự rebalance, thêm capacity forecast, rồi khóa vòng bằng supervisor quality scoring.
Đã suy nghĩ trong 10s
Dưới đây là bản full code file-by-file paste-ready cho:
PHASE 3 — AUTO-REBALANCE ACTIONS + REVIEW CAPACITY PLANNING + SUPERVISOR QUALITY SCORING
Mục tiêu phase này là nâng hệ từ:
đo được workload reviewer
đo được review SLA
đo được override effectiveness
thành:
tự đề xuất rebalance reviewer
có action endpoint để reassign thật
dự báo thiếu capacity theo queue
chấm điểm supervisor dài hạn
đóng vòng optimization cho governed execution
Mình giữ đúng nguyên tắc:
không tái cấu trúc
file-by-file
paste-ready
bám monorepo phase trước
1) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
add 3 models
register imports vào base
add repositories
add schemas
add services
patch review queue / assignment / workflow services
add routes
wire router
add migration
add worker
add tests
Frontend
add types
add APIs
add panels
patch HumanReviewQueuePanel
patch ReviewDecisionPanel / analytics area
2) BACKEND — FULL FILES
backend/app/models/review_rebalance_action.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ReviewRebalanceAction(Base):
    __tablename__ = "review_rebalance_action"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    review_case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    from_reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_reviewer_id: Mapped[str] = mapped_column(String(64), nullable=False)

    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    recommendation_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    auto_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    # proposed | applied | skipped | rejected

    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
backend/app/models/review_capacity_plan_rollup.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ReviewCapacityPlanRollup(Base):
    __tablename__ = "review_capacity_plan_rollup"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    queue_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    forecast_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    projected_new_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    projected_total_load: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    active_reviewers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capacity_gap: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    overload_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    staffing_recommendation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/supervisor_quality_score.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class SupervisorQualityScore(Base):
    __tablename__ = "supervisor_quality_score"

    supervisor_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    supervisor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    total_reviews_touched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    harmful_overrides: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    approval_accuracy_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    override_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sla_rescue_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    churn_penalty_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    final_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_band: Mapped[str] = mapped_column(String(32), nullable=False, default="unrated")
    # elite | strong | stable | risky | critical | unrated

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/db/base.py — PATCH
Thêm imports:
from app.models.review_rebalance_action import ReviewRebalanceAction
from app.models.review_capacity_plan_rollup import ReviewCapacityPlanRollup
from app.models.supervisor_quality_score import SupervisorQualityScore
backend/app/repositories/review_rebalance_action_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.review_rebalance_action import ReviewRebalanceAction


class ReviewRebalanceActionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: ReviewRebalanceAction) -> ReviewRebalanceAction:
        self.db.add(model)
        return model

    def get(self, action_id: str) -> ReviewRebalanceAction | None:
        return self.db.get(ReviewRebalanceAction, action_id)

    def list_latest(self, limit: int = 100) -> list[ReviewRebalanceAction]:
        stmt = (
            select(ReviewRebalanceAction)
            .order_by(desc(ReviewRebalanceAction.created_at))
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/review_capacity_plan_rollup_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.review_capacity_plan_rollup import ReviewCapacityPlanRollup


class ReviewCapacityPlanRollupRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: ReviewCapacityPlanRollup) -> ReviewCapacityPlanRollup:
        self.db.add(model)
        return model

    def list_latest(self, queue_key: str | None = None) -> list[ReviewCapacityPlanRollup]:
        stmt = select(ReviewCapacityPlanRollup)
        if queue_key:
            stmt = stmt.where(ReviewCapacityPlanRollup.queue_key == queue_key)
        stmt = stmt.order_by(desc(ReviewCapacityPlanRollup.computed_at))
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/supervisor_quality_score_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.supervisor_quality_score import SupervisorQualityScore


class SupervisorQualityScoreRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert(self, model: SupervisorQualityScore) -> SupervisorQualityScore:
        existing = self.db.get(SupervisorQualityScore, model.supervisor_id)
        if existing:
            existing.supervisor_name = model.supervisor_name
            existing.total_reviews_touched = model.total_reviews_touched
            existing.total_overrides = model.total_overrides
            existing.effective_overrides = model.effective_overrides
            existing.harmful_overrides = model.harmful_overrides
            existing.approval_accuracy_score = model.approval_accuracy_score
            existing.override_quality_score = model.override_quality_score
            existing.sla_rescue_score = model.sla_rescue_score
            existing.churn_penalty_score = model.churn_penalty_score
            existing.final_quality_score = model.final_quality_score
            existing.quality_band = model.quality_band
            existing.computed_at = model.computed_at
            self.db.add(existing)
            return existing

        self.db.add(model)
        return model

    def list_all(self) -> list[SupervisorQualityScore]:
        stmt = select(SupervisorQualityScore).order_by(
            desc(SupervisorQualityScore.final_quality_score),
            desc(SupervisorQualityScore.computed_at),
        )
        return list(self.db.execute(stmt).scalars().all())
backend/app/schemas/rebalance_action.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReviewRebalanceActionRead(BaseModel):
    id: str
    review_case_id: str
    from_reviewer_id: str | None = None
    to_reviewer_id: str
    reason_code: str
    reason_detail: str | None = None
    recommendation_score: float
    auto_applied: bool
    status: str
    created_by: str
    created_at: datetime
    applied_at: datetime | None = None

    class Config:
        from_attributes = True


class ApplyRebalanceActionRequest(BaseModel):
    review_case_id: str
    to_reviewer_id: str
    reason_code: str
    reason_detail: str | None = None
    auto_applied: bool = False
backend/app/schemas/review_capacity_plan.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReviewCapacityPlanRollupRead(BaseModel):
    id: str
    queue_key: str
    forecast_window_hours: int
    projected_new_cases: int
    projected_total_load: int
    active_reviewers: int
    effective_capacity: int
    capacity_gap: int
    overload_risk_score: float
    staffing_recommendation_count: int
    window_start: datetime
    window_end: datetime
    computed_at: datetime

    class Config:
        from_attributes = True
backend/app/schemas/supervisor_quality.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SupervisorQualityScoreRead(BaseModel):
    supervisor_id: str
    supervisor_name: str | None = None
    total_reviews_touched: int
    total_overrides: int
    effective_overrides: int
    harmful_overrides: int
    approval_accuracy_score: float
    override_quality_score: float
    sla_rescue_score: float
    churn_penalty_score: float
    final_quality_score: float
    quality_band: str
    computed_at: datetime

    class Config:
        from_attributes = True
backend/app/services/review_auto_rebalance_service.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.review_rebalance_action import ReviewRebalanceAction
from app.repositories.review_rebalance_action_repository import (
    ReviewRebalanceActionRepository,
)
from app.services.reviewer_workload_balancing_service import (
    ReviewerWorkloadBalancingService,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReviewAutoRebalanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReviewRebalanceActionRepository(db)
        self.workload_service = ReviewerWorkloadBalancingService(db)

    def propose_rebalance_for_case(
        self,
        *,
        review_case_id: str,
        current_reviewer_id: str | None,
        queue_key: str | None = None,
    ) -> ReviewRebalanceAction | None:
        recommendations = self.workload_service.suggest_reviewer_for_case()
        if not recommendations:
            return None

        best = recommendations[0]
        if current_reviewer_id and best.reviewer_id == current_reviewer_id:
            return None

        reason_code = "rebalance_under_capacity_target"
        reason_detail = "Reassign to the reviewer with highest current recommendation score."

        action = ReviewRebalanceAction(
            id=str(uuid4()),
            review_case_id=review_case_id,
            from_reviewer_id=current_reviewer_id,
            to_reviewer_id=best.reviewer_id,
            reason_code=reason_code,
            reason_detail=reason_detail,
            recommendation_score=best.recommendation_score,
            auto_applied=False,
            status="proposed",
            created_by="system",
            created_at=_utcnow(),
        )
        return self.repo.create(action)

    def apply_rebalance_action(
        self,
        *,
        action: ReviewRebalanceAction,
        review_case,
        actor_id: str,
    ) -> ReviewRebalanceAction:
        review_case.assigned_reviewer_id = action.to_reviewer_id
        review_case.suggested_reviewer_id = action.to_reviewer_id
        review_case.reviewer_overloaded = False
        if hasattr(review_case, "assigned_at"):
            review_case.assigned_at = _utcnow()

        action.status = "applied"
        action.applied_at = _utcnow()
        action.created_by = actor_id or action.created_by
        self.db.add(review_case)
        self.db.add(action)
        return action
backend/app/services/review_capacity_planning_service.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.review_capacity_plan_rollup import ReviewCapacityPlanRollup
from app.repositories.review_capacity_plan_rollup_repository import (
    ReviewCapacityPlanRollupRepository,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReviewCapacityPlanningService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReviewCapacityPlanRollupRepository(db)

    def compute_overload_risk_score(
        self,
        *,
        projected_total_load: int,
        effective_capacity: int,
        capacity_gap: int,
    ) -> float:
        if effective_capacity <= 0:
            return 1.0
        load_ratio = projected_total_load / max(effective_capacity, 1)
        gap_penalty = max(capacity_gap, 0) / max(effective_capacity, 1)
        return max(0.0, min(1.0, (load_ratio * 0.7) + (gap_penalty * 0.3)))

    def build_rollup(
        self,
        *,
        queue_key: str,
        forecast_window_hours: int,
        projected_new_cases: int,
        current_open_cases: int,
        active_reviewers: int,
        average_capacity_per_reviewer: int,
        window_start: datetime,
        window_end: datetime,
    ) -> ReviewCapacityPlanRollup:
        projected_total_load = current_open_cases + projected_new_cases
        effective_capacity = active_reviewers * average_capacity_per_reviewer
        capacity_gap = projected_total_load - effective_capacity
        staffing_recommendation_count = 0
        if average_capacity_per_reviewer > 0 and capacity_gap > 0:
            staffing_recommendation_count = int(
                (capacity_gap + average_capacity_per_reviewer - 1)
                / average_capacity_per_reviewer
            )

        overload_risk_score = self.compute_overload_risk_score(
            projected_total_load=projected_total_load,
            effective_capacity=effective_capacity,
            capacity_gap=capacity_gap,
        )

        model = ReviewCapacityPlanRollup(
            id=str(uuid4()),
            queue_key=queue_key,
            forecast_window_hours=forecast_window_hours,
            projected_new_cases=projected_new_cases,
            projected_total_load=projected_total_load,
            active_reviewers=active_reviewers,
            effective_capacity=effective_capacity,
            capacity_gap=capacity_gap,
            overload_risk_score=overload_risk_score,
            staffing_recommendation_count=staffing_recommendation_count,
            window_start=window_start,
            window_end=window_end,
            computed_at=_utcnow(),
        )
        return self.repo.create(model)
backend/app/services/supervisor_quality_scoring_service.py
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.supervisor_quality_score import SupervisorQualityScore
from app.repositories.supervisor_quality_score_repository import (
    SupervisorQualityScoreRepository,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SupervisorQualityScoringService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SupervisorQualityScoreRepository(db)

    def classify_quality_band(self, final_quality_score: float) -> str:
        if final_quality_score >= 0.85:
            return "elite"
        if final_quality_score >= 0.70:
            return "strong"
        if final_quality_score >= 0.55:
            return "stable"
        if final_quality_score >= 0.35:
            return "risky"
        return "critical"

    def compute_final_score(
        self,
        *,
        approval_accuracy_score: float,
        override_quality_score: float,
        sla_rescue_score: float,
        churn_penalty_score: float,
    ) -> float:
        raw = (
            approval_accuracy_score * 0.35
            + override_quality_score * 0.35
            + sla_rescue_score * 0.20
            - churn_penalty_score * 0.10
        )
        return max(0.0, min(1.0, raw))

    def build_score(
        self,
        *,
        supervisor_id: str,
        supervisor_name: str | None,
        total_reviews_touched: int,
        total_overrides: int,
        effective_overrides: int,
        harmful_overrides: int,
        approval_accuracy_score: float,
        sla_rescue_score: float,
    ) -> SupervisorQualityScore:
        override_quality_score = 0.0
        if total_overrides > 0:
            override_quality_score = max(
                0.0,
                min(
                    1.0,
                    (effective_overrides - harmful_overrides) / total_overrides * 0.5 + 0.5,
                ),
            )

        churn_penalty_score = 0.0
        if total_overrides > 0:
            churn_penalty_score = min(1.0, harmful_overrides / total_overrides)

        final_quality_score = self.compute_final_score(
            approval_accuracy_score=approval_accuracy_score,
            override_quality_score=override_quality_score,
            sla_rescue_score=sla_rescue_score,
            churn_penalty_score=churn_penalty_score,
        )
        quality_band = self.classify_quality_band(final_quality_score)

        model = SupervisorQualityScore(
            supervisor_id=supervisor_id,
            supervisor_name=supervisor_name,
            total_reviews_touched=total_reviews_touched,
            total_overrides=total_overrides,
            effective_overrides=effective_overrides,
            harmful_overrides=harmful_overrides,
            approval_accuracy_score=approval_accuracy_score,
            override_quality_score=override_quality_score,
            sla_rescue_score=sla_rescue_score,
            churn_penalty_score=churn_penalty_score,
            final_quality_score=final_quality_score,
            quality_band=quality_band,
            computed_at=_utcnow(),
        )
        return self.repo.upsert(model)
3) BACKEND — PATCH CÁC FILE ĐANG CÓ
backend/app/models/human_review_case.py — PATCH
Nếu model review case hiện chưa có các field này thì thêm:
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

rebalancing_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
latest_rebalance_action_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
queue_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
backend/app/services/auto_assign_service.py — PATCH
Thêm logic trigger rebalance recommendation khi reviewer hiện tại overload:
from app.services.review_auto_rebalance_service import ReviewAutoRebalanceService

rebalance_service = ReviewAutoRebalanceService(self.db)

if getattr(review_case, "reviewer_overloaded", False):
    action = rebalance_service.propose_rebalance_for_case(
        review_case_id=review_case.id,
        current_reviewer_id=review_case.assigned_reviewer_id,
        queue_key=getattr(review_case, "queue_key", None),
    )
    if action:
        review_case.rebalancing_recommended = True
        review_case.latest_rebalance_action_id = action.id
backend/app/services/review_workflow_service.py — PATCH
Thêm khi manual reassignment xảy ra:
def reassign_review_case(self, review_case, to_reviewer_id: str, actor_id: str):
    previous = getattr(review_case, "assigned_reviewer_id", None)
    review_case.assigned_reviewer_id = to_reviewer_id
    review_case.suggested_reviewer_id = to_reviewer_id
    review_case.reviewer_overloaded = False
    review_case.rebalancing_recommended = False
    if hasattr(review_case, "assigned_at"):
        review_case.assigned_at = _utcnow()

    # optional audit fields
    if hasattr(review_case, "last_reassigned_by"):
        review_case.last_reassigned_by = actor_id
    if hasattr(review_case, "last_reassigned_from"):
        review_case.last_reassigned_from = previous

    self.db.add(review_case)
    return review_case
backend/app/services/review_queue_service.py — PATCH
Thêm helper priority cho rebalance:
def should_rebalance_case(
    self,
    *,
    reviewer_overloaded: bool,
    overdue: bool,
    pending_approval: bool,
) -> bool:
    if reviewer_overloaded and overdue:
        return True
    if reviewer_overloaded and pending_approval:
        return True
    return False
4) BACKEND — ROUTES
backend/app/api/routes/review_optimization.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.review_capacity_plan_rollup_repository import (
    ReviewCapacityPlanRollupRepository,
)
from app.repositories.review_rebalance_action_repository import (
    ReviewRebalanceActionRepository,
)
from app.repositories.supervisor_quality_score_repository import (
    SupervisorQualityScoreRepository,
)
from app.schemas.rebalance_action import (
    ApplyRebalanceActionRequest,
    ReviewRebalanceActionRead,
)
from app.schemas.review_capacity_plan import ReviewCapacityPlanRollupRead
from app.schemas.supervisor_quality import SupervisorQualityScoreRead
from app.services.review_auto_rebalance_service import ReviewAutoRebalanceService

router = APIRouter(prefix="/review-optimization", tags=["review-optimization"])


@router.get("/rebalance-actions", response_model=list[ReviewRebalanceActionRead])
def list_rebalance_actions(db: Session = Depends(get_db)):
    repo = ReviewRebalanceActionRepository(db)
    return repo.list_latest()


@router.post("/rebalance-actions/apply", response_model=ReviewRebalanceActionRead)
def apply_rebalance_action(
    payload: ApplyRebalanceActionRequest,
    db: Session = Depends(get_db),
):
    # NOTE:
    # Replace this lookup with your actual review case repository.
    review_case = None
    if hasattr(db, "review_case_repo_placeholder"):
        review_case = db.review_case_repo_placeholder.get(payload.review_case_id)

    if review_case is None:
        raise HTTPException(status_code=404, detail="Review case not found")

    service = ReviewAutoRebalanceService(db)
    action = service.propose_rebalance_for_case(
        review_case_id=payload.review_case_id,
        current_reviewer_id=getattr(review_case, "assigned_reviewer_id", None),
        queue_key=getattr(review_case, "queue_key", None),
    )
    if action is None:
        raise HTTPException(status_code=409, detail="No rebalance action available")

    action.to_reviewer_id = payload.to_reviewer_id
    action.reason_code = payload.reason_code
    action.reason_detail = payload.reason_detail
    action.auto_applied = payload.auto_applied

    service.apply_rebalance_action(
        action=action,
        review_case=review_case,
        actor_id="system_api",
    )
    db.commit()
    db.refresh(action)
    return action


@router.get("/capacity-plans", response_model=list[ReviewCapacityPlanRollupRead])
def list_capacity_plans(queue_key: str | None = None, db: Session = Depends(get_db)):
    repo = ReviewCapacityPlanRollupRepository(db)
    return repo.list_latest(queue_key=queue_key)


@router.get("/supervisors/quality", response_model=list[SupervisorQualityScoreRead])
def list_supervisor_quality_scores(db: Session = Depends(get_db)):
    repo = SupervisorQualityScoreRepository(db)
    return repo.list_all()
backend/app/api/api_v1/api.py — PATCH
Thêm import:
from app.api.routes import review_optimization
Và include:
api_router.include_router(review_optimization.router)
5) BACKEND — MIGRATION
backend/alembic/versions/phase3_rebalance_capacity_supervisor_quality.py
from alembic import op
import sqlalchemy as sa


revision = "phase3_rebalance_capacity_supervisor_quality"
down_revision = "phase3_reviewer_balancing_and_analytics"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_rebalance_action",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("review_case_id", sa.String(length=64), nullable=False),
        sa.Column("from_reviewer_id", sa.String(length=64), nullable=True),
        sa.Column("to_reviewer_id", sa.String(length=64), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column("reason_detail", sa.Text(), nullable=True),
        sa.Column("recommendation_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("auto_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="proposed"),
        sa.Column("created_by", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_review_rebalance_action_review_case_id",
        "review_rebalance_action",
        ["review_case_id"],
    )

    op.create_table(
        "review_capacity_plan_rollup",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("queue_key", sa.String(length=128), nullable=False),
        sa.Column("forecast_window_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("projected_new_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("projected_total_load", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_reviewers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capacity_gap", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overload_risk_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("staffing_recommendation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_review_capacity_plan_rollup_queue_key",
        "review_capacity_plan_rollup",
        ["queue_key"],
    )

    op.create_table(
        "supervisor_quality_score",
        sa.Column("supervisor_id", sa.String(length=64), primary_key=True),
        sa.Column("supervisor_name", sa.String(length=255), nullable=True),
        sa.Column("total_reviews_touched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("harmful_overrides", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approval_accuracy_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("override_quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sla_rescue_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("churn_penalty_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("final_quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_band", sa.String(length=32), nullable=False, server_default="unrated"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Optional patch existing human_review_case if needed.
    # Uncomment only if the current repo does not already contain these fields.
    #
    # op.add_column("human_review_case", sa.Column("rebalancing_recommended", sa.Boolean(), nullable=False, server_default=sa.false()))
    # op.add_column("human_review_case", sa.Column("latest_rebalance_action_id", sa.String(length=64), nullable=True))
    # op.add_column("human_review_case", sa.Column("queue_key", sa.String(length=128), nullable=True))


def downgrade():
    op.drop_table("supervisor_quality_score")

    op.drop_index("ix_review_capacity_plan_rollup_queue_key", table_name="review_capacity_plan_rollup")
    op.drop_table("review_capacity_plan_rollup")

    op.drop_index("ix_review_rebalance_action_review_case_id", table_name="review_rebalance_action")
    op.drop_table("review_rebalance_action")
6) BACKEND — WORKER
backend/app/workers/review_optimization_worker.py
from __future__ import annotations

from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.review_auto_rebalance_service import ReviewAutoRebalanceService
from app.services.review_capacity_planning_service import ReviewCapacityPlanningService
from app.services.supervisor_quality_scoring_service import (
    SupervisorQualityScoringService,
)


@celery_app.task(name="review_optimization.refresh")
def refresh_review_optimization():
    db = SessionLocal()
    try:
        capacity_service = ReviewCapacityPlanningService(db)
        quality_service = SupervisorQualityScoringService(db)
        rebalance_service = ReviewAutoRebalanceService(db)

        now = datetime.utcnow()
        window_start = now
        window_end = now + timedelta(hours=24)

        capacity_service.build_rollup(
            queue_key="human_review",
            forecast_window_hours=24,
            projected_new_cases=18,
            current_open_cases=27,
            active_reviewers=4,
            average_capacity_per_reviewer=10,
            window_start=window_start,
            window_end=window_end,
        )

        quality_service.build_score(
            supervisor_id="supervisor_1",
            supervisor_name="Supervisor 1",
            total_reviews_touched=120,
            total_overrides=16,
            effective_overrides=11,
            harmful_overrides=2,
            approval_accuracy_score=0.82,
            sla_rescue_score=0.74,
        )

        # Example proposal only. Replace with real review case query if available.
        rebalance_service.propose_rebalance_for_case(
            review_case_id="sample_review_case_1",
            current_reviewer_id="reviewer_2",
            queue_key="human_review",
        )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
7) BACKEND — TESTS
backend/tests/services/test_review_auto_rebalance_service.py
from app.services.review_auto_rebalance_service import ReviewAutoRebalanceService
from app.services.reviewer_workload_balancing_service import ReviewerWorkloadBalancingService


def test_propose_rebalance_for_case_returns_action_when_better_reviewer_exists(db_session):
    workload = ReviewerWorkloadBalancingService(db_session)
    workload.materialize_snapshot(
        reviewer_id="reviewer_best",
        reviewer_name="Best",
        open_review_cases=1,
        pending_approval_cases=0,
        overdue_cases=0,
        escalated_cases=0,
        avg_first_response_minutes=10.0,
        avg_resolution_minutes=30.0,
        capacity_limit=10,
        availability_score=1.0,
    )
    workload.materialize_snapshot(
        reviewer_id="reviewer_busy",
        reviewer_name="Busy",
        open_review_cases=9,
        pending_approval_cases=2,
        overdue_cases=2,
        escalated_cases=1,
        avg_first_response_minutes=60.0,
        avg_resolution_minutes=180.0,
        capacity_limit=10,
        availability_score=0.3,
    )

    svc = ReviewAutoRebalanceService(db_session)
    action = svc.propose_rebalance_for_case(
        review_case_id="case_1",
        current_reviewer_id="reviewer_busy",
        queue_key="human_review",
    )

    assert action is not None
    assert action.to_reviewer_id == "reviewer_best"
    assert action.status == "proposed"
backend/tests/services/test_review_capacity_planning_service.py
from datetime import datetime, timedelta

from app.services.review_capacity_planning_service import ReviewCapacityPlanningService


def test_build_rollup_computes_capacity_gap_and_staffing_need(db_session):
    svc = ReviewCapacityPlanningService(db_session)
    now = datetime.utcnow()

    row = svc.build_rollup(
        queue_key="human_review",
        forecast_window_hours=24,
        projected_new_cases=20,
        current_open_cases=25,
        active_reviewers=3,
        average_capacity_per_reviewer=10,
        window_start=now,
        window_end=now + timedelta(hours=24),
    )

    assert row.projected_total_load == 45
    assert row.effective_capacity == 30
    assert row.capacity_gap == 15
    assert row.staffing_recommendation_count == 2
backend/tests/services/test_supervisor_quality_scoring_service.py
from app.services.supervisor_quality_scoring_service import SupervisorQualityScoringService


def test_build_score_assigns_quality_band(db_session):
    svc = SupervisorQualityScoringService(db_session)

    row = svc.build_score(
        supervisor_id="sup_1",
        supervisor_name="Supervisor 1",
        total_reviews_touched=100,
        total_overrides=10,
        effective_overrides=8,
        harmful_overrides=1,
        approval_accuracy_score=0.85,
        sla_rescue_score=0.75,
    )

    assert row.final_quality_score > 0.0
    assert row.quality_band in {"elite", "strong", "stable", "risky", "critical"}
8) FRONTEND — FULL FILES
frontend/src/types/reviewOptimization.ts
export type ReviewRebalanceAction = {
  id: string;
  review_case_id: string;
  from_reviewer_id?: string | null;
  to_reviewer_id: string;
  reason_code: string;
  reason_detail?: string | null;
  recommendation_score: number;
  auto_applied: boolean;
  status: string;
  created_by: string;
  created_at: string;
  applied_at?: string | null;
};

export type ReviewCapacityPlanRollup = {
  id: string;
  queue_key: string;
  forecast_window_hours: number;
  projected_new_cases: number;
  projected_total_load: number;
  active_reviewers: number;
  effective_capacity: number;
  capacity_gap: number;
  overload_risk_score: number;
  staffing_recommendation_count: number;
  window_start: string;
  window_end: string;
  computed_at: string;
};

export type SupervisorQualityScore = {
  supervisor_id: string;
  supervisor_name?: string | null;
  total_reviews_touched: number;
  total_overrides: number;
  effective_overrides: number;
  harmful_overrides: number;
  approval_accuracy_score: number;
  override_quality_score: number;
  sla_rescue_score: number;
  churn_penalty_score: number;
  final_quality_score: number;
  quality_band: string;
  computed_at: string;
};
frontend/src/api/reviewOptimization.ts
import { api } from "./client";
import {
  ReviewCapacityPlanRollup,
  ReviewRebalanceAction,
  SupervisorQualityScore,
} from "../types/reviewOptimization";

export async function fetchRebalanceActions(): Promise<ReviewRebalanceAction[]> {
  const res = await api.get("/review-optimization/rebalance-actions");
  return res.data;
}

export async function applyRebalanceAction(payload: {
  review_case_id: string;
  to_reviewer_id: string;
  reason_code: string;
  reason_detail?: string;
  auto_applied?: boolean;
}): Promise<ReviewRebalanceAction> {
  const res = await api.post("/review-optimization/rebalance-actions/apply", payload);
  return res.data;
}

export async function fetchCapacityPlans(queueKey?: string): Promise<ReviewCapacityPlanRollup[]> {
  const res = await api.get("/review-optimization/capacity-plans", {
    params: queueKey ? { queue_key: queueKey } : {},
  });
  return res.data;
}

export async function fetchSupervisorQualityScores(): Promise<SupervisorQualityScore[]> {
  const res = await api.get("/review-optimization/supervisors/quality");
  return res.data;
}
frontend/src/components/review/RebalanceActionsPanel.tsx
import React, { useEffect, useState } from "react";
import { applyRebalanceAction, fetchRebalanceActions } from "../../api/reviewOptimization";
import { ReviewRebalanceAction } from "../../types/reviewOptimization";

export function RebalanceActionsPanel() {
  const [rows, setRows] = useState<ReviewRebalanceAction[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setRows(await fetchRebalanceActions());
    } finally {
      setLoading(false);
    }
  }

  async function onApply(row: ReviewRebalanceAction) {
    await applyRebalanceAction({
      review_case_id: row.review_case_id,
      to_reviewer_id: row.to_reviewer_id,
      reason_code: row.reason_code,
      reason_detail: row.reason_detail ?? undefined,
      auto_applied: false,
    });
    await load();
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Rebalance Actions</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.id} className="rounded border p-3">
          <div className="font-medium">Case {row.review_case_id}</div>
          <div className="mt-1 text-sm text-gray-600">
            {row.from_reviewer_id ?? "unassigned"} → {row.to_reviewer_id}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Reason: {row.reason_code} · Score: {row.recommendation_score.toFixed(2)}
          </div>
          {row.reason_detail ? (
            <div className="mt-1 text-xs text-gray-500">{row.reason_detail}</div>
          ) : null}
          <div className="mt-1 text-xs text-gray-500">Status: {row.status}</div>

          {row.status === "proposed" ? (
            <div className="mt-2">
              <button className="rounded border px-3 py-1 text-sm" onClick={() => void onApply(row)}>
                Apply rebalance
              </button>
            </div>
          ) : null}
        </div>
      ))}

      {!rows.length && !loading ? (
        <div className="text-sm text-gray-500">No rebalance actions.</div>
      ) : null}
    </div>
  );
}
frontend/src/components/review/ReviewCapacityPlanPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchCapacityPlans } from "../../api/reviewOptimization";
import { ReviewCapacityPlanRollup } from "../../types/reviewOptimization";

type Props = {
  queueKey?: string;
};

export function ReviewCapacityPlanPanel({ queueKey }: Props) {
  const [rows, setRows] = useState<ReviewCapacityPlanRollup[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load(queueKey);
  }, [queueKey]);

  async function load(nextQueueKey?: string) {
    setLoading(true);
    try {
      setRows(await fetchCapacityPlans(nextQueueKey));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Review Capacity Planning</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load(queueKey)} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.id} className="rounded border p-3">
          <div className="font-medium">{row.queue_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            Forecast: {row.forecast_window_hours}h · Projected new: {row.projected_new_cases}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Total load: {row.projected_total_load} · Capacity: {row.effective_capacity} · Gap: {row.capacity_gap}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Active reviewers: {row.active_reviewers} · Staffing recommendation: {row.staffing_recommendation_count}
          </div>
          <div className="mt-1 text-xs text-gray-500">
            Overload risk: {(row.overload_risk_score * 100).toFixed(1)}%
          </div>
        </div>
      ))}

      {!rows.length && !loading ? (
        <div className="text-sm text-gray-500">No capacity plan data.</div>
      ) : null}
    </div>
  );
}
frontend/src/components/review/SupervisorQualityPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchSupervisorQualityScores } from "../../api/reviewOptimization";
import { SupervisorQualityScore } from "../../types/reviewOptimization";

export function SupervisorQualityPanel() {
  const [rows, setRows] = useState<SupervisorQualityScore[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setRows(await fetchSupervisorQualityScores());
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Supervisor Quality Scoring</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.supervisor_id} className="rounded border p-3">
          <div className="font-medium">{row.supervisor_name || row.supervisor_id}</div>
          <div className="mt-1 text-sm text-gray-600">
            Final score: {row.final_quality_score.toFixed(2)} · Band: {row.quality_band}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Approval accuracy: {row.approval_accuracy_score.toFixed(2)} · Override quality:{" "}
            {row.override_quality_score.toFixed(2)}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            SLA rescue: {row.sla_rescue_score.toFixed(2)} · Churn penalty:{" "}
            {row.churn_penalty_score.toFixed(2)}
          </div>
          <div className="mt-1 text-xs text-gray-500">
            Overrides: {row.total_overrides} · Effective: {row.effective_overrides} · Harmful:{" "}
            {row.harmful_overrides}
          </div>
        </div>
      ))}

      {!rows.length && !loading ? (
        <div className="text-sm text-gray-500">No supervisor quality data.</div>
      ) : null}
    </div>
  );
}
9) FRONTEND — PATCH CÁC FILE ĐANG CÓ
frontend/src/components/review/HumanReviewQueuePanel.tsx — PATCH
Thêm imports:
import { RebalanceActionsPanel } from "./RebalanceActionsPanel";
import { ReviewCapacityPlanPanel } from "./ReviewCapacityPlanPanel";
Trong JSX thêm:
<RebalanceActionsPanel />
<ReviewCapacityPlanPanel queueKey="human_review" />
Trong mỗi row của case, thêm:
{caseItem.rebalancing_recommended ? (
  <div className="mt-1 text-xs text-amber-700">
    Rebalance recommended · Action ID: {caseItem.latest_rebalance_action_id ?? "n/a"}
  </div>
) : null}
frontend/src/components/review/ReviewDecisionPanel.tsx — PATCH
Thêm import:
import { SupervisorQualityPanel } from "./SupervisorQualityPanel";
Trong JSX thêm:
<SupervisorQualityPanel />
Nếu có block supervisor action:
<div className="mt-2 text-xs text-gray-500">
  Supervisor decisions contribute to long-term quality scoring and override governance ranking.
</div>
10) ĐIỂM MAP KHI DÁN VÀO REPO THẬT
A. Route apply rebalance
Trong file route mình để placeholder lookup review case:
review_case = None
if hasattr(db, "review_case_repo_placeholder"):
    review_case = db.review_case_repo_placeholder.get(payload.review_case_id)
Trong repo thật, thay bằng repository thật của bạn. Ví dụ:
from app.repositories.human_review_case_repository import HumanReviewCaseRepository

case_repo = HumanReviewCaseRepository(db)
review_case = case_repo.get(payload.review_case_id)
B. Worker mock aggregates
review_optimization_worker.py đang dùng mock values. Ở repo thật, thay bằng aggregate từ:
human_review_case
reviewer_workload_snapshot
override_effectiveness_rollup
review_sla_rollup
C. Nếu repo có auth actor headers
actor_id="system_api" nên thay bằng actor thật từ request context.
D. Nếu repo có toast/notification system
Frontend panel apply rebalance nên nối thêm success/error toast.
11) KẾT QUẢ SAU PATCH NÀY
Sau phase này, hệ của bạn sẽ có thêm 3 lớp rất quan trọng:
A. Auto-rebalance action layer
Không chỉ biết “ai đang quá tải”, mà tạo được action rebalance có thể apply thật.
B. Capacity planning layer
Không chỉ nhìn hiện tại, mà forecast queue sắp thiếu bao nhiêu reviewer.
C. Supervisor quality scoring
Không chỉ log supervisor override, mà đánh giá supervisor đó theo chất lượng dài hạn.
Tức là queue đã đi từ:
measurable supervised governance
sang:
self-optimizing supervised governance
12) BƯỚC MẠNH NHẤT NGAY SAU BẢN NÀY
Bước tiếp theo mạnh nhất là:
PHASE 3 — AUTO-REBALANCE POLICY ENGINE + STAFFING RECOMMENDATIONS + SUPERVISOR INTERVENTION GUARDRAILS
Vì lúc đó hệ sẽ đi tiếp từ:
có rebalance action
có capacity forecast
có supervisor score
sang:
policy nào cho phép auto-rebalance không cần người
khi nào supervisor bị giới hạn quyền override
staffing recommendation theo shift / queue / severity
intervention guardrails dựa trên supervisor quality band
self-tuning governance policy loop
Nếu bạn muốn, mình viết tiếp ngay phase đó cũng theo đúng format full code file-by-file paste-ready.
Bước tiếp theo mạnh nhất là: PHASE 3 — AUTO-REBALANCE POLICY ENGINE + STAFFING RECOMMENDATIONS + SUPERVISOR INTERVENTION GUARDRAILS Vì lúc đó hệ sẽ đi tiếp từ: có rebalance action có capacity forecast có supervisor score sang: policy nào cho phép auto-rebalance không cần người khi nào supervisor bị giới hạn quyền override staffing recommendation theo shift / queue / severity intervention guardrails dựa trên supervisor quality band self-tuning governance policy loop Nếu bạn muốn, mình viết tiếp ngay phase đó cũng theo đúng format full code file-by-file paste-ready.
Mình sẽ nối tiếp luôn phase này theo đúng nhịp trước: thêm policy layer để quyết định auto-rebalance được hay không, thêm staffing recommendations theo queue/severity/shift, rồi khóa supervisor bằng guardrails dựa trên quality band.
Đã suy nghĩ trong giây lát
Dưới đây là bản full code file-by-file paste-ready cho:
PHASE 3 — AUTO-REBALANCE POLICY ENGINE + STAFFING RECOMMENDATIONS + SUPERVISOR INTERVENTION GUARDRAILS
Mục tiêu phase này là nâng hệ từ:
có rebalance action
có capacity forecast
có supervisor score
thành:
policy nào cho phép auto-rebalance không cần người
staffing recommendation theo shift / queue / severity
supervisor quality band có guardrails thật
override/intervention bị chặn hoặc cần approval theo risk
self-tuning governance policy loop
Mình giữ đúng nguyên tắc:
không tái cấu trúc
bám monorepo phase trước
file-by-file
paste-ready
1) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
add 4 models
register imports vào base
add repositories
add schemas
add services
patch rebalance / workflow / override execution services
add routes
wire router
add migration
add worker
add tests
Frontend
add types
add APIs
add panels
patch HumanReviewQueuePanel
patch ReviewDecisionPanel / supervisor area
2) BACKEND — FULL FILES
backend/app/models/review_rebalance_policy.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ReviewRebalancePolicy(Base):
    __tablename__ = "review_rebalance_policy"

    policy_key: Mapped[str] = mapped_column(String(128), primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    queue_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    allow_auto_rebalance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    min_recommendation_score: Mapped[float] = mapped_column(Float, nullable=False, default=6.0)
    min_capacity_gap_to_trigger: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_target_reviewer_load_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)

    allow_if_overdue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_if_pending_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_sensitive_projects: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/staffing_recommendation.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class StaffingRecommendation(Base):
    __tablename__ = "staffing_recommendation"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    queue_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    shift_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    recommended_additional_reviewers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommended_additional_supervisors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    forecast_load: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capacity_gap: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    urgency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recommendation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/supervisor_intervention_guardrail.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class SupervisorInterventionGuardrail(Base):
    __tablename__ = "supervisor_intervention_guardrail"

    guardrail_key: Mapped[str] = mapped_column(String(128), primary_key=True)

    quality_band: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    intervention_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # override | rebalance | force_approve | force_reject | sensitive_project_action

    action_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="allow")
    # allow | warn | require_approval | deny

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/policy_tuning_signal.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PolicyTuningSignal(Base):
    __tablename__ = "policy_tuning_signal"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    signal_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # sla_improved | sla_worsened | churn_increased | rebalance_success | rebalance_failure

    signal_strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/db/base.py — PATCH
Thêm imports:
from app.models.review_rebalance_policy import ReviewRebalancePolicy
from app.models.staffing_recommendation import StaffingRecommendation
from app.models.supervisor_intervention_guardrail import SupervisorInterventionGuardrail
from app.models.policy_tuning_signal import PolicyTuningSignal
backend/app/repositories/review_rebalance_policy_repository.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.review_rebalance_policy import ReviewRebalancePolicy


class ReviewRebalancePolicyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, policy_key: str) -> ReviewRebalancePolicy | None:
        return self.db.get(ReviewRebalancePolicy, policy_key)

    def upsert(self, model: ReviewRebalancePolicy) -> ReviewRebalancePolicy:
        existing = self.db.get(ReviewRebalancePolicy, model.policy_key)
        if existing:
            existing.enabled = model.enabled
            existing.queue_key = model.queue_key
            existing.severity = model.severity
            existing.allow_auto_rebalance = model.allow_auto_rebalance
            existing.require_human_approval = model.require_human_approval
            existing.min_recommendation_score = model.min_recommendation_score
            existing.min_capacity_gap_to_trigger = model.min_capacity_gap_to_trigger
            existing.max_target_reviewer_load_ratio = model.max_target_reviewer_load_ratio
            existing.allow_if_overdue = model.allow_if_overdue
            existing.allow_if_pending_approval = model.allow_if_pending_approval
            existing.allow_sensitive_projects = model.allow_sensitive_projects
            existing.updated_at = model.updated_at
            self.db.add(existing)
            return existing

        self.db.add(model)
        return model

    def list_all(self) -> list[ReviewRebalancePolicy]:
        stmt = select(ReviewRebalancePolicy).order_by(ReviewRebalancePolicy.policy_key.asc())
        return list(self.db.execute(stmt).scalars().all())

    def find_best_match(self, queue_key: str | None, severity: str | None) -> ReviewRebalancePolicy | None:
        stmt = select(ReviewRebalancePolicy).where(ReviewRebalancePolicy.enabled.is_(True))
        candidates = list(self.db.execute(stmt).scalars().all())

        exact = [
            p for p in candidates
            if p.queue_key == queue_key and p.severity == severity
        ]
        if exact:
            return exact[0]

        queue_only = [
            p for p in candidates
            if p.queue_key == queue_key and p.severity is None
        ]
        if queue_only:
            return queue_only[0]

        severity_only = [
            p for p in candidates
            if p.queue_key is None and p.severity == severity
        ]
        if severity_only:
            return severity_only[0]

        global_default = [
            p for p in candidates
            if p.queue_key is None and p.severity is None
        ]
        return global_default[0] if global_default else None
backend/app/repositories/staffing_recommendation_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.staffing_recommendation import StaffingRecommendation


class StaffingRecommendationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: StaffingRecommendation) -> StaffingRecommendation:
        self.db.add(model)
        return model

    def list_latest(self, queue_key: str | None = None) -> list[StaffingRecommendation]:
        stmt = select(StaffingRecommendation)
        if queue_key:
            stmt = stmt.where(StaffingRecommendation.queue_key == queue_key)
        stmt = stmt.order_by(desc(StaffingRecommendation.computed_at))
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/supervisor_intervention_guardrail_repository.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.supervisor_intervention_guardrail import SupervisorInterventionGuardrail


class SupervisorInterventionGuardrailRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, guardrail_key: str) -> SupervisorInterventionGuardrail | None:
        return self.db.get(SupervisorInterventionGuardrail, guardrail_key)

    def upsert(self, model: SupervisorInterventionGuardrail) -> SupervisorInterventionGuardrail:
        existing = self.db.get(SupervisorInterventionGuardrail, model.guardrail_key)
        if existing:
            existing.quality_band = model.quality_band
            existing.intervention_type = model.intervention_type
            existing.action_mode = model.action_mode
            existing.enabled = model.enabled
            existing.reason_template = model.reason_template
            existing.updated_at = model.updated_at
            self.db.add(existing)
            return existing

        self.db.add(model)
        return model

    def list_all(self) -> list[SupervisorInterventionGuardrail]:
        stmt = select(SupervisorInterventionGuardrail).order_by(
            SupervisorInterventionGuardrail.quality_band.asc(),
            SupervisorInterventionGuardrail.intervention_type.asc(),
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_rule(
        self,
        *,
        quality_band: str,
        intervention_type: str,
    ) -> SupervisorInterventionGuardrail | None:
        stmt = select(SupervisorInterventionGuardrail).where(
            SupervisorInterventionGuardrail.enabled.is_(True),
            SupervisorInterventionGuardrail.quality_band == quality_band,
            SupervisorInterventionGuardrail.intervention_type == intervention_type,
        )
        return self.db.execute(stmt).scalars().first()
backend/app/repositories/policy_tuning_signal_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.policy_tuning_signal import PolicyTuningSignal


class PolicyTuningSignalRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: PolicyTuningSignal) -> PolicyTuningSignal:
        self.db.add(model)
        return model

    def list_latest(self, policy_key: str | None = None) -> list[PolicyTuningSignal]:
        stmt = select(PolicyTuningSignal)
        if policy_key:
            stmt = stmt.where(PolicyTuningSignal.policy_key == policy_key)
        stmt = stmt.order_by(desc(PolicyTuningSignal.created_at))
        return list(self.db.execute(stmt).scalars().all())
backend/app/schemas/rebalance_policy.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReviewRebalancePolicyRead(BaseModel):
    policy_key: str
    enabled: bool
    queue_key: str | None = None
    severity: str | None = None
    allow_auto_rebalance: bool
    require_human_approval: bool
    min_recommendation_score: float
    min_capacity_gap_to_trigger: int
    max_target_reviewer_load_ratio: float
    allow_if_overdue: bool
    allow_if_pending_approval: bool
    allow_sensitive_projects: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
backend/app/schemas/staffing_recommendation.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class StaffingRecommendationRead(BaseModel):
    id: str
    queue_key: str
    shift_key: str | None = None
    severity: str | None = None
    recommended_additional_reviewers: int
    recommended_additional_supervisors: int
    forecast_load: int
    effective_capacity: int
    capacity_gap: int
    urgency_score: float
    recommendation_reason: str | None = None
    computed_at: datetime

    class Config:
        from_attributes = True
backend/app/schemas/intervention_guardrail.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SupervisorInterventionGuardrailRead(BaseModel):
    guardrail_key: str
    quality_band: str
    intervention_type: str
    action_mode: str
    enabled: bool
    reason_template: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GuardrailDecisionRead(BaseModel):
    intervention_type: str
    quality_band: str
    action_mode: str
    allowed: bool
    requires_approval: bool
    reason: str | None = None
backend/app/schemas/policy_tuning_signal.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PolicyTuningSignalRead(BaseModel):
    id: str
    policy_key: str
    signal_type: str
    signal_strength: float
    sample_size: int
    recommendation: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
backend/app/services/rebalance_policy_engine.py
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.review_rebalance_policy_repository import (
    ReviewRebalancePolicyRepository,
)


@dataclass
class RebalancePolicyInput:
    queue_key: str | None
    severity: str | None
    recommendation_score: float
    capacity_gap: int
    target_reviewer_load_ratio: float
    overdue: bool
    pending_approval: bool
    sensitive_project: bool


@dataclass
class RebalancePolicyDecision:
    allowed: bool
    auto_apply: bool
    requires_human_approval: bool
    policy_key: str | None
    reason_codes: list[str]


class RebalancePolicyEngine:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReviewRebalancePolicyRepository(db)

    def evaluate(self, payload: RebalancePolicyInput) -> RebalancePolicyDecision:
        policy = self.repo.find_best_match(payload.queue_key, payload.severity)
        if policy is None:
            return RebalancePolicyDecision(
                allowed=False,
                auto_apply=False,
                requires_human_approval=True,
                policy_key=None,
                reason_codes=["no_matching_policy"],
            )

        reasons: list[str] = []

        if not policy.enabled:
            return RebalancePolicyDecision(
                allowed=False,
                auto_apply=False,
                requires_human_approval=True,
                policy_key=policy.policy_key,
                reason_codes=["policy_disabled"],
            )

        if payload.recommendation_score < policy.min_recommendation_score:
            reasons.append("recommendation_score_below_threshold")

        if payload.capacity_gap < policy.min_capacity_gap_to_trigger:
            reasons.append("capacity_gap_below_trigger")

        if payload.target_reviewer_load_ratio > policy.max_target_reviewer_load_ratio:
            reasons.append("target_reviewer_load_ratio_too_high")

        if payload.overdue and not policy.allow_if_overdue:
            reasons.append("overdue_not_allowed")

        if payload.pending_approval and not policy.allow_if_pending_approval:
            reasons.append("pending_approval_not_allowed")

        if payload.sensitive_project and not policy.allow_sensitive_projects:
            reasons.append("sensitive_project_not_allowed")

        allowed = len(reasons) == 0
        auto_apply = (
            allowed
            and policy.allow_auto_rebalance
            and not policy.require_human_approval
        )

        return RebalancePolicyDecision(
            allowed=allowed,
            auto_apply=auto_apply,
            requires_human_approval=(not auto_apply),
            policy_key=policy.policy_key,
            reason_codes=reasons if reasons else ["policy_pass"],
        )
backend/app/services/staffing_recommendation_service.py
from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.staffing_recommendation import StaffingRecommendation
from app.repositories.staffing_recommendation_repository import (
    StaffingRecommendationRepository,
)


class StaffingRecommendationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = StaffingRecommendationRepository(db)

    def compute_urgency_score(
        self,
        *,
        capacity_gap: int,
        forecast_load: int,
        effective_capacity: int,
        severity: str | None,
    ) -> float:
        if effective_capacity <= 0:
            base = 1.0
        else:
            base = min(1.0, max(0.0, capacity_gap / max(effective_capacity, 1)))

        severity_bonus = 0.0
        if severity == "critical":
            severity_bonus = 0.30
        elif severity == "high":
            severity_bonus = 0.15

        return min(1.0, base + severity_bonus)

    def build_recommendation(
        self,
        *,
        queue_key: str,
        shift_key: str | None,
        severity: str | None,
        forecast_load: int,
        effective_capacity: int,
        capacity_gap: int,
    ) -> StaffingRecommendation:
        recommended_additional_reviewers = 0
        if capacity_gap > 0:
            recommended_additional_reviewers = max(1, capacity_gap // 10 + (1 if capacity_gap % 10 else 0))

        recommended_additional_supervisors = 0
        if capacity_gap >= 20 or severity == "critical":
            recommended_additional_supervisors = 1

        urgency_score = self.compute_urgency_score(
            capacity_gap=capacity_gap,
            forecast_load=forecast_load,
            effective_capacity=effective_capacity,
            severity=severity,
        )

        reason = (
            f"Queue {queue_key} projected load={forecast_load}, "
            f"capacity={effective_capacity}, gap={capacity_gap}, severity={severity or 'default'}."
        )

        model = StaffingRecommendation(
            id=str(uuid4()),
            queue_key=queue_key,
            shift_key=shift_key,
            severity=severity,
            recommended_additional_reviewers=recommended_additional_reviewers,
            recommended_additional_supervisors=recommended_additional_supervisors,
            forecast_load=forecast_load,
            effective_capacity=effective_capacity,
            capacity_gap=capacity_gap,
            urgency_score=urgency_score,
            recommendation_reason=reason,
        )
        return self.repo.create(model)
backend/app/services/supervisor_intervention_guardrail_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.supervisor_intervention_guardrail_repository import (
    SupervisorInterventionGuardrailRepository,
)
from app.repositories.supervisor_quality_score_repository import (
    SupervisorQualityScoreRepository,
)
from app.schemas.intervention_guardrail import GuardrailDecisionRead


class SupervisorInterventionGuardrailService:
    def __init__(self, db: Session):
        self.db = db
        self.guardrail_repo = SupervisorInterventionGuardrailRepository(db)
        self.quality_repo = SupervisorQualityScoreRepository(db)

    def evaluate(
        self,
        *,
        supervisor_id: str,
        intervention_type: str,
    ) -> GuardrailDecisionRead:
        quality_scores = {row.supervisor_id: row for row in self.quality_repo.list_all()}
        supervisor = quality_scores.get(supervisor_id)

        if supervisor is None:
            quality_band = "unrated"
        else:
            quality_band = supervisor.quality_band

        rule = self.guardrail_repo.find_rule(
            quality_band=quality_band,
            intervention_type=intervention_type,
        )

        if rule is None:
            return GuardrailDecisionRead(
                intervention_type=intervention_type,
                quality_band=quality_band,
                action_mode="warn",
                allowed=True,
                requires_approval=False,
                reason="No explicit guardrail matched. Defaulting to warn.",
            )

        if rule.action_mode == "deny":
            return GuardrailDecisionRead(
                intervention_type=intervention_type,
                quality_band=quality_band,
                action_mode=rule.action_mode,
                allowed=False,
                requires_approval=False,
                reason=rule.reason_template,
            )

        if rule.action_mode == "require_approval":
            return GuardrailDecisionRead(
                intervention_type=intervention_type,
                quality_band=quality_band,
                action_mode=rule.action_mode,
                allowed=True,
                requires_approval=True,
                reason=rule.reason_template,
            )

        return GuardrailDecisionRead(
            intervention_type=intervention_type,
            quality_band=quality_band,
            action_mode=rule.action_mode,
            allowed=True,
            requires_approval=False,
            reason=rule.reason_template,
        )
backend/app/services/policy_tuning_service.py
from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.policy_tuning_signal import PolicyTuningSignal
from app.repositories.policy_tuning_signal_repository import PolicyTuningSignalRepository


class PolicyTuningService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PolicyTuningSignalRepository(db)

    def emit_signal(
        self,
        *,
        policy_key: str,
        signal_type: str,
        signal_strength: float,
        sample_size: int,
        recommendation: str | None = None,
    ) -> PolicyTuningSignal:
        model = PolicyTuningSignal(
            id=str(uuid4()),
            policy_key=policy_key,
            signal_type=signal_type,
            signal_strength=signal_strength,
            sample_size=sample_size,
            recommendation=recommendation,
        )
        return self.repo.create(model)
3) BACKEND — PATCH CÁC FILE ĐANG CÓ
backend/app/models/review_rebalance_action.py — PATCH
Thêm các field sau nếu chưa có:
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

policy_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
approval_required: Mapped[bool] = mapped_column(nullable=False, default=False)
backend/app/models/human_review_case.py — PATCH
Nếu chưa có, thêm:
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
is_sensitive_project: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
auto_rebalance_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
auto_rebalance_block_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
backend/app/services/review_auto_rebalance_service.py — PATCH
Thêm imports:
from app.services.rebalance_policy_engine import (
    RebalancePolicyEngine,
    RebalancePolicyInput,
)
Trong __init__ thêm:
self.policy_engine = RebalancePolicyEngine(db)
Thay propose_rebalance_for_case(...) bằng bản đã nối policy:
def propose_rebalance_for_case(
    self,
    *,
    review_case_id: str,
    current_reviewer_id: str | None,
    queue_key: str | None = None,
    severity: str | None = None,
    overdue: bool = False,
    pending_approval: bool = False,
    sensitive_project: bool = False,
) -> ReviewRebalanceAction | None:
    recommendations = self.workload_service.suggest_reviewer_for_case()
    if not recommendations:
        return None

    best = recommendations[0]
    if current_reviewer_id and best.reviewer_id == current_reviewer_id:
        return None

    target_load_ratio = 0.5  # replace with real reviewer load ratio if available
    capacity_gap = 1  # replace with real queue capacity gap if available

    policy_decision = self.policy_engine.evaluate(
        RebalancePolicyInput(
            queue_key=queue_key,
            severity=severity,
            recommendation_score=best.recommendation_score,
            capacity_gap=capacity_gap,
            target_reviewer_load_ratio=target_load_ratio,
            overdue=overdue,
            pending_approval=pending_approval,
            sensitive_project=sensitive_project,
        )
    )

    if not policy_decision.allowed:
        return None

    action = ReviewRebalanceAction(
        id=str(uuid4()),
        review_case_id=review_case_id,
        from_reviewer_id=current_reviewer_id,
        to_reviewer_id=best.reviewer_id,
        reason_code="rebalance_under_capacity_target",
        reason_detail="Reassign to reviewer with highest recommendation score under active policy.",
        recommendation_score=best.recommendation_score,
        auto_applied=policy_decision.auto_apply,
        status="proposed",
        created_by="system",
        created_at=_utcnow(),
    )
    action.policy_key = policy_decision.policy_key
    action.approval_required = policy_decision.requires_human_approval
    return self.repo.create(action)
backend/app/services/review_workflow_service.py — PATCH
Trong logic supervisor override, trước khi execute override thêm guardrail check:
from app.services.supervisor_intervention_guardrail_service import (
    SupervisorInterventionGuardrailService,
)

guardrail_service = SupervisorInterventionGuardrailService(self.db)
decision = guardrail_service.evaluate(
    supervisor_id=actor_id,
    intervention_type="override",
)

if not decision.allowed:
    raise PermissionError(decision.reason or "Supervisor intervention denied by guardrail.")

if decision.requires_approval:
    # map to your approval workflow
    raise PermissionError(decision.reason or "Supervisor override requires approval.")
backend/app/services/auto_assign_service.py — PATCH
Khi gọi rebalance, truyền thêm context:
action = rebalance_service.propose_rebalance_for_case(
    review_case_id=review_case.id,
    current_reviewer_id=review_case.assigned_reviewer_id,
    queue_key=getattr(review_case, "queue_key", None),
    severity=getattr(review_case, "severity", None),
    overdue=getattr(review_case, "is_overdue", False),
    pending_approval=getattr(review_case, "status", None) == "pending_approval",
    sensitive_project=getattr(review_case, "is_sensitive_project", False),
)
if action is None:
    review_case.auto_rebalance_blocked = True
    review_case.auto_rebalance_block_reason = "Policy denied or no valid rebalance target."
else:
    review_case.rebalancing_recommended = True
    review_case.latest_rebalance_action_id = action.id
4) BACKEND — ROUTES
backend/app/api/routes/review_policy_governance.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.policy_tuning_signal_repository import PolicyTuningSignalRepository
from app.repositories.review_rebalance_policy_repository import ReviewRebalancePolicyRepository
from app.repositories.staffing_recommendation_repository import StaffingRecommendationRepository
from app.repositories.supervisor_intervention_guardrail_repository import (
    SupervisorInterventionGuardrailRepository,
)
from app.schemas.intervention_guardrail import (
    GuardrailDecisionRead,
    SupervisorInterventionGuardrailRead,
)
from app.schemas.policy_tuning_signal import PolicyTuningSignalRead
from app.schemas.rebalance_policy import ReviewRebalancePolicyRead
from app.schemas.staffing_recommendation import StaffingRecommendationRead
from app.services.supervisor_intervention_guardrail_service import (
    SupervisorInterventionGuardrailService,
)

router = APIRouter(prefix="/review-policy-governance", tags=["review-policy-governance"])


@router.get("/rebalance-policies", response_model=list[ReviewRebalancePolicyRead])
def list_rebalance_policies(db: Session = Depends(get_db)):
    repo = ReviewRebalancePolicyRepository(db)
    return repo.list_all()


@router.get("/staffing-recommendations", response_model=list[StaffingRecommendationRead])
def list_staffing_recommendations(queue_key: str | None = None, db: Session = Depends(get_db)):
    repo = StaffingRecommendationRepository(db)
    return repo.list_latest(queue_key=queue_key)


@router.get("/guardrails", response_model=list[SupervisorInterventionGuardrailRead])
def list_guardrails(db: Session = Depends(get_db)):
    repo = SupervisorInterventionGuardrailRepository(db)
    return repo.list_all()


@router.get("/guardrails/evaluate", response_model=GuardrailDecisionRead)
def evaluate_guardrail(
    supervisor_id: str,
    intervention_type: str,
    db: Session = Depends(get_db),
):
    svc = SupervisorInterventionGuardrailService(db)
    return svc.evaluate(
        supervisor_id=supervisor_id,
        intervention_type=intervention_type,
    )


@router.get("/policy-tuning-signals", response_model=list[PolicyTuningSignalRead])
def list_policy_tuning_signals(policy_key: str | None = None, db: Session = Depends(get_db)):
    repo = PolicyTuningSignalRepository(db)
    return repo.list_latest(policy_key=policy_key)
backend/app/api/api_v1/api.py — PATCH
Thêm import:
from app.api.routes import review_policy_governance
Và include router:
api_router.include_router(review_policy_governance.router)
5) BACKEND — MIGRATION
backend/alembic/versions/phase3_policy_staffing_guardrails.py
from alembic import op
import sqlalchemy as sa


revision = "phase3_policy_staffing_guardrails"
down_revision = "phase3_rebalance_capacity_supervisor_quality"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_rebalance_policy",
        sa.Column("policy_key", sa.String(length=128), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("queue_key", sa.String(length=128), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("allow_auto_rebalance", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("require_human_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("min_recommendation_score", sa.Float(), nullable=False, server_default="6"),
        sa.Column("min_capacity_gap_to_trigger", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_target_reviewer_load_ratio", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("allow_if_overdue", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_if_pending_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_sensitive_projects", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_rebalance_policy_queue_key", "review_rebalance_policy", ["queue_key"])
    op.create_index("ix_review_rebalance_policy_severity", "review_rebalance_policy", ["severity"])

    op.create_table(
        "staffing_recommendation",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("queue_key", sa.String(length=128), nullable=False),
        sa.Column("shift_key", sa.String(length=64), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("recommended_additional_reviewers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recommended_additional_supervisors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forecast_load", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capacity_gap", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("urgency_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recommendation_reason", sa.Text(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_staffing_recommendation_queue_key", "staffing_recommendation", ["queue_key"])
    op.create_index("ix_staffing_recommendation_shift_key", "staffing_recommendation", ["shift_key"])
    op.create_index("ix_staffing_recommendation_severity", "staffing_recommendation", ["severity"])

    op.create_table(
        "supervisor_intervention_guardrail",
        sa.Column("guardrail_key", sa.String(length=128), primary_key=True),
        sa.Column("quality_band", sa.String(length=32), nullable=False),
        sa.Column("intervention_type", sa.String(length=64), nullable=False),
        sa.Column("action_mode", sa.String(length=32), nullable=False, server_default="allow"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reason_template", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_supervisor_intervention_guardrail_quality_band", "supervisor_intervention_guardrail", ["quality_band"])
    op.create_index("ix_supervisor_intervention_guardrail_intervention_type", "supervisor_intervention_guardrail", ["intervention_type"])

    op.create_table(
        "policy_tuning_signal",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("policy_key", sa.String(length=128), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("signal_strength", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_tuning_signal_policy_key", "policy_tuning_signal", ["policy_key"])
    op.create_index("ix_policy_tuning_signal_signal_type", "policy_tuning_signal", ["signal_type"])

    # Optional patch existing tables only if missing
    #
    # op.add_column("review_rebalance_action", sa.Column("policy_key", sa.String(length=128), nullable=True))
    # op.add_column("review_rebalance_action", sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    #
    # op.add_column("human_review_case", sa.Column("severity", sa.String(length=32), nullable=True))
    # op.add_column("human_review_case", sa.Column("is_sensitive_project", sa.Boolean(), nullable=False, server_default=sa.false()))
    # op.add_column("human_review_case", sa.Column("auto_rebalance_blocked", sa.Boolean(), nullable=False, server_default=sa.false()))
    # op.add_column("human_review_case", sa.Column("auto_rebalance_block_reason", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_index("ix_policy_tuning_signal_signal_type", table_name="policy_tuning_signal")
    op.drop_index("ix_policy_tuning_signal_policy_key", table_name="policy_tuning_signal")
    op.drop_table("policy_tuning_signal")

    op.drop_index("ix_supervisor_intervention_guardrail_intervention_type", table_name="supervisor_intervention_guardrail")
    op.drop_index("ix_supervisor_intervention_guardrail_quality_band", table_name="supervisor_intervention_guardrail")
    op.drop_table("supervisor_intervention_guardrail")

    op.drop_index("ix_staffing_recommendation_severity", table_name="staffing_recommendation")
    op.drop_index("ix_staffing_recommendation_shift_key", table_name="staffing_recommendation")
    op.drop_index("ix_staffing_recommendation_queue_key", table_name="staffing_recommendation")
    op.drop_table("staffing_recommendation")

    op.drop_index("ix_review_rebalance_policy_severity", table_name="review_rebalance_policy")
    op.drop_index("ix_review_rebalance_policy_queue_key", table_name="review_rebalance_policy")
    op.drop_table("review_rebalance_policy")
6) BACKEND — WORKER
backend/app/workers/review_policy_governance_worker.py
from __future__ import annotations

from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.review_rebalance_policy import ReviewRebalancePolicy
from app.models.supervisor_intervention_guardrail import SupervisorInterventionGuardrail
from app.repositories.review_rebalance_policy_repository import (
    ReviewRebalancePolicyRepository,
)
from app.repositories.supervisor_intervention_guardrail_repository import (
    SupervisorInterventionGuardrailRepository,
)
from app.services.policy_tuning_service import PolicyTuningService
from app.services.staffing_recommendation_service import StaffingRecommendationService


def _utcnow():
    return datetime.now(timezone.utc)


@celery_app.task(name="review_policy_governance.refresh")
def refresh_review_policy_governance():
    db = SessionLocal()
    try:
        policy_repo = ReviewRebalancePolicyRepository(db)
        guardrail_repo = SupervisorInterventionGuardrailRepository(db)
        staffing_service = StaffingRecommendationService(db)
        tuning_service = PolicyTuningService(db)

        policy_repo.upsert(
            ReviewRebalancePolicy(
                policy_key="global_default",
                enabled=True,
                queue_key=None,
                severity=None,
                allow_auto_rebalance=False,
                require_human_approval=True,
                min_recommendation_score=6.0,
                min_capacity_gap_to_trigger=1,
                max_target_reviewer_load_ratio=0.85,
                allow_if_overdue=True,
                allow_if_pending_approval=True,
                allow_sensitive_projects=False,
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
        )

        policy_repo.upsert(
            ReviewRebalancePolicy(
                policy_key="human_review_high",
                enabled=True,
                queue_key="human_review",
                severity="high",
                allow_auto_rebalance=True,
                require_human_approval=False,
                min_recommendation_score=7.0,
                min_capacity_gap_to_trigger=1,
                max_target_reviewer_load_ratio=0.70,
                allow_if_overdue=True,
                allow_if_pending_approval=True,
                allow_sensitive_projects=False,
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
        )

        guardrail_repo.upsert(
            SupervisorInterventionGuardrail(
                guardrail_key="risky_override",
                quality_band="risky",
                intervention_type="override",
                action_mode="require_approval",
                enabled=True,
                reason_template="Supervisor in risky band must obtain approval for override actions.",
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
        )

        guardrail_repo.upsert(
            SupervisorInterventionGuardrail(
                guardrail_key="critical_sensitive_action",
                quality_band="critical",
                intervention_type="sensitive_project_action",
                action_mode="deny",
                enabled=True,
                reason_template="Critical-band supervisor cannot perform sensitive project actions.",
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
        )

        staffing_service.build_recommendation(
            queue_key="human_review",
            shift_key="night",
            severity="high",
            forecast_load=52,
            effective_capacity=30,
            capacity_gap=22,
        )

        tuning_service.emit_signal(
            policy_key="human_review_high",
            signal_type="rebalance_success",
            signal_strength=0.82,
            sample_size=34,
            recommendation="Current policy performs well for high-severity human_review queue.",
        )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
7) BACKEND — TESTS
backend/tests/services/test_rebalance_policy_engine.py
from datetime import datetime

from app.models.review_rebalance_policy import ReviewRebalancePolicy
from app.repositories.review_rebalance_policy_repository import ReviewRebalancePolicyRepository
from app.services.rebalance_policy_engine import (
    RebalancePolicyEngine,
    RebalancePolicyInput,
)


def test_policy_engine_allows_auto_rebalance_when_thresholds_pass(db_session):
    repo = ReviewRebalancePolicyRepository(db_session)
    repo.upsert(
        ReviewRebalancePolicy(
            policy_key="p1",
            enabled=True,
            queue_key="human_review",
            severity="high",
            allow_auto_rebalance=True,
            require_human_approval=False,
            min_recommendation_score=7.0,
            min_capacity_gap_to_trigger=1,
            max_target_reviewer_load_ratio=0.8,
            allow_if_overdue=True,
            allow_if_pending_approval=True,
            allow_sensitive_projects=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )

    engine = RebalancePolicyEngine(db_session)
    decision = engine.evaluate(
        RebalancePolicyInput(
            queue_key="human_review",
            severity="high",
            recommendation_score=8.2,
            capacity_gap=3,
            target_reviewer_load_ratio=0.5,
            overdue=True,
            pending_approval=False,
            sensitive_project=False,
        )
    )

    assert decision.allowed is True
    assert decision.auto_apply is True
backend/tests/services/test_staffing_recommendation_service.py
from app.services.staffing_recommendation_service import StaffingRecommendationService


def test_staffing_recommendation_computes_extra_reviewers(db_session):
    svc = StaffingRecommendationService(db_session)

    row = svc.build_recommendation(
        queue_key="human_review",
        shift_key="night",
        severity="critical",
        forecast_load=60,
        effective_capacity=30,
        capacity_gap=30,
    )

    assert row.recommended_additional_reviewers >= 3
    assert row.recommended_additional_supervisors == 1
    assert row.urgency_score > 0.0
backend/tests/services/test_supervisor_intervention_guardrail_service.py
from datetime import datetime

from app.models.supervisor_intervention_guardrail import SupervisorInterventionGuardrail
from app.models.supervisor_quality_score import SupervisorQualityScore
from app.repositories.supervisor_intervention_guardrail_repository import (
    SupervisorInterventionGuardrailRepository,
)
from app.repositories.supervisor_quality_score_repository import (
    SupervisorQualityScoreRepository,
)
from app.services.supervisor_intervention_guardrail_service import (
    SupervisorInterventionGuardrailService,
)


def test_guardrail_requires_approval_for_risky_supervisor_override(db_session):
    quality_repo = SupervisorQualityScoreRepository(db_session)
    guardrail_repo = SupervisorInterventionGuardrailRepository(db_session)

    quality_repo.upsert(
        SupervisorQualityScore(
            supervisor_id="sup_1",
            supervisor_name="Supervisor 1",
            total_reviews_touched=100,
            total_overrides=20,
            effective_overrides=8,
            harmful_overrides=6,
            approval_accuracy_score=0.4,
            override_quality_score=0.4,
            sla_rescue_score=0.5,
            churn_penalty_score=0.6,
            final_quality_score=0.4,
            quality_band="risky",
            computed_at=datetime.utcnow(),
        )
    )

    guardrail_repo.upsert(
        SupervisorInterventionGuardrail(
            guardrail_key="g1",
            quality_band="risky",
            intervention_type="override",
            action_mode="require_approval",
            enabled=True,
            reason_template="Requires approval.",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )

    svc = SupervisorInterventionGuardrailService(db_session)
    decision = svc.evaluate(
        supervisor_id="sup_1",
        intervention_type="override",
    )

    assert decision.allowed is True
    assert decision.requires_approval is True
8) FRONTEND — FULL FILES
frontend/src/types/reviewPolicyGovernance.ts
export type ReviewRebalancePolicy = {
  policy_key: string;
  enabled: boolean;
  queue_key?: string | null;
  severity?: string | null;
  allow_auto_rebalance: boolean;
  require_human_approval: boolean;
  min_recommendation_score: number;
  min_capacity_gap_to_trigger: number;
  max_target_reviewer_load_ratio: number;
  allow_if_overdue: boolean;
  allow_if_pending_approval: boolean;
  allow_sensitive_projects: boolean;
  created_at: string;
  updated_at: string;
};

export type StaffingRecommendation = {
  id: string;
  queue_key: string;
  shift_key?: string | null;
  severity?: string | null;
  recommended_additional_reviewers: number;
  recommended_additional_supervisors: number;
  forecast_load: number;
  effective_capacity: number;
  capacity_gap: number;
  urgency_score: number;
  recommendation_reason?: string | null;
  computed_at: string;
};

export type SupervisorInterventionGuardrail = {
  guardrail_key: string;
  quality_band: string;
  intervention_type: string;
  action_mode: string;
  enabled: boolean;
  reason_template?: string | null;
  created_at: string;
  updated_at: string;
};

export type GuardrailDecision = {
  intervention_type: string;
  quality_band: string;
  action_mode: string;
  allowed: boolean;
  requires_approval: boolean;
  reason?: string | null;
};

export type PolicyTuningSignal = {
  id: string;
  policy_key: string;
  signal_type: string;
  signal_strength: number;
  sample_size: number;
  recommendation?: string | null;
  created_at: string;
};
frontend/src/api/reviewPolicyGovernance.ts
import { api } from "./client";
import {
  GuardrailDecision,
  PolicyTuningSignal,
  ReviewRebalancePolicy,
  StaffingRecommendation,
  SupervisorInterventionGuardrail,
} from "../types/reviewPolicyGovernance";

export async function fetchRebalancePolicies(): Promise<ReviewRebalancePolicy[]> {
  const res = await api.get("/review-policy-governance/rebalance-policies");
  return res.data;
}

export async function fetchStaffingRecommendations(queueKey?: string): Promise<StaffingRecommendation[]> {
  const res = await api.get("/review-policy-governance/staffing-recommendations", {
    params: queueKey ? { queue_key: queueKey } : {},
  });
  return res.data;
}

export async function fetchGuardrails(): Promise<SupervisorInterventionGuardrail[]> {
  const res = await api.get("/review-policy-governance/guardrails");
  return res.data;
}

export async function evaluateGuardrail(
  supervisorId: string,
  interventionType: string
): Promise<GuardrailDecision> {
  const res = await api.get("/review-policy-governance/guardrails/evaluate", {
    params: { supervisor_id: supervisorId, intervention_type: interventionType },
  });
  return res.data;
}

export async function fetchPolicyTuningSignals(policyKey?: string): Promise<PolicyTuningSignal[]> {
  const res = await api.get("/review-policy-governance/policy-tuning-signals", {
    params: policyKey ? { policy_key: policyKey } : {},
  });
  return res.data;
}
frontend/src/components/review/RebalancePolicyPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchRebalancePolicies } from "../../api/reviewPolicyGovernance";
import { ReviewRebalancePolicy } from "../../types/reviewPolicyGovernance";

export function RebalancePolicyPanel() {
  const [rows, setRows] = useState<ReviewRebalancePolicy[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setRows(await fetchRebalancePolicies());
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Auto-Rebalance Policies</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.policy_key} className="rounded border p-3">
          <div className="font-medium">{row.policy_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            Queue: {row.queue_key ?? "global"} · Severity: {row.severity ?? "all"} · Enabled:{" "}
            {row.enabled ? "yes" : "no"}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Auto-rebalance: {row.allow_auto_rebalance ? "yes" : "no"} · Human approval:{" "}
            {row.require_human_approval ? "required" : "not required"}
          </div>
          <div className="mt-1 text-xs text-gray-500">
            Min score: {row.min_recommendation_score} · Min gap: {row.min_capacity_gap_to_trigger} ·
            Max target load ratio: {row.max_target_reviewer_load_ratio}
          </div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No policy data.</div> : null}
    </div>
  );
}
frontend/src/components/review/StaffingRecommendationPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchStaffingRecommendations } from "../../api/reviewPolicyGovernance";
import { StaffingRecommendation } from "../../types/reviewPolicyGovernance";

type Props = {
  queueKey?: string;
};

export function StaffingRecommendationPanel({ queueKey }: Props) {
  const [rows, setRows] = useState<StaffingRecommendation[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load(queueKey);
  }, [queueKey]);

  async function load(nextQueueKey?: string) {
    setLoading(true);
    try {
      setRows(await fetchStaffingRecommendations(nextQueueKey));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Staffing Recommendations</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load(queueKey)} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.id} className="rounded border p-3">
          <div className="font-medium">
            {row.queue_key} · {row.shift_key ?? "all shifts"} · {row.severity ?? "all severity"}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            +Reviewers: {row.recommended_additional_reviewers} · +Supervisors:{" "}
            {row.recommended_additional_supervisors}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Forecast load: {row.forecast_load} · Capacity: {row.effective_capacity} · Gap: {row.capacity_gap}
          </div>
          <div className="mt-1 text-xs text-gray-500">
            Urgency: {(row.urgency_score * 100).toFixed(1)}% · {row.recommendation_reason}
          </div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No staffing recommendations.</div> : null}
    </div>
  );
}
frontend/src/components/review/SupervisorGuardrailPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchGuardrails } from "../../api/reviewPolicyGovernance";
import { SupervisorInterventionGuardrail } from "../../types/reviewPolicyGovernance";

export function SupervisorGuardrailPanel() {
  const [rows, setRows] = useState<SupervisorInterventionGuardrail[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setRows(await fetchGuardrails());
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Supervisor Intervention Guardrails</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.guardrail_key} className="rounded border p-3">
          <div className="font-medium">{row.guardrail_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            Band: {row.quality_band} · Intervention: {row.intervention_type} · Mode: {row.action_mode}
          </div>
          <div className="mt-1 text-xs text-gray-500">{row.reason_template ?? "No reason template."}</div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No guardrails configured.</div> : null}
    </div>
  );
}
frontend/src/components/review/PolicyTuningSignalPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchPolicyTuningSignals } from "../../api/reviewPolicyGovernance";
import { PolicyTuningSignal } from "../../types/reviewPolicyGovernance";

type Props = {
  policyKey?: string;
};

export function PolicyTuningSignalPanel({ policyKey }: Props) {
  const [rows, setRows] = useState<PolicyTuningSignal[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load(policyKey);
  }, [policyKey]);

  async function load(nextPolicyKey?: string) {
    setLoading(true);
    try {
      setRows(await fetchPolicyTuningSignals(nextPolicyKey));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Policy Tuning Signals</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load(policyKey)} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.id} className="rounded border p-3">
          <div className="font-medium">{row.policy_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            {row.signal_type} · strength={row.signal_strength.toFixed(2)} · n={row.sample_size}
          </div>
          <div className="mt-1 text-xs text-gray-500">{row.recommendation ?? "No recommendation."}</div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No tuning signals.</div> : null}
    </div>
  );
}
9) FRONTEND — PATCH CÁC FILE ĐANG CÓ
frontend/src/components/review/HumanReviewQueuePanel.tsx — PATCH
Thêm imports:
import { RebalancePolicyPanel } from "./RebalancePolicyPanel";
import { StaffingRecommendationPanel } from "./StaffingRecommendationPanel";
Trong JSX thêm:
<RebalancePolicyPanel />
<StaffingRecommendationPanel queueKey="human_review" />
Trong từng review case row, thêm:
{caseItem.auto_rebalance_blocked ? (
  <div className="mt-1 text-xs text-red-600">
    Auto-rebalance blocked: {caseItem.auto_rebalance_block_reason ?? "policy blocked"}
  </div>
) : null}
frontend/src/components/review/ReviewDecisionPanel.tsx — PATCH
Thêm imports:
import { SupervisorGuardrailPanel } from "./SupervisorGuardrailPanel";
import { PolicyTuningSignalPanel } from "./PolicyTuningSignalPanel";
Trong JSX thêm:
<SupervisorGuardrailPanel />
<PolicyTuningSignalPanel />
Trong block supervisor decision, thêm note:
<div className="mt-2 text-xs text-gray-500">
  Supervisor interventions are evaluated against quality-band guardrails and may require approval or be denied.
</div>
10) ĐIỂM MAP QUAN TRỌNG KHI DÁN VÀO REPO THẬT
A. review_auto_rebalance_service.py
Hiện đang dùng placeholder:
target_load_ratio = 0.5
capacity_gap = 1
Trong repo thật, thay bằng dữ liệu thật từ:
reviewer_workload_snapshot
review_capacity_plan_rollup
B. Guardrail enforcement
Trong review_workflow_service.py, mình đang raise PermissionError. Ở repo thật, map sang:
HTTPException(403) nếu ở route layer
hoặc DomainPolicyViolation nếu repo có error taxonomy riêng
C. Policy tuning loop
policy_tuning_service.py hiện mới emit signal. Ở phase sau, bạn có thể:
auto-adjust threshold
recommend policy changes
simulate impact trước khi promote
D. Staffing recommendation granularity
Hiện layer này hỗ trợ:
queue
shift
severity
Ở repo thật bạn có thể mở rộng thêm:
project
region
reviewer skill band
11) KẾT QUẢ SAU PATCH NÀY
Sau phase này, hệ của bạn đã đi từ:
self-optimizing supervised governance
sang:
policy-governed self-adjusting review operations
Cụ thể hệ đã có:
A. Auto-rebalance policy engine
Không phải rebalance nào cũng apply. Hệ biết rebalance nào được phép.
B. Staffing recommendations
Không chỉ thấy thiếu tải, mà đề xuất thêm reviewer/supervisor theo queue/shift/severity.
C. Supervisor intervention guardrails
Supervisor band thấp có thể bị warn, require approval, hoặc deny.
D. Policy tuning signals
Hệ bắt đầu có vòng phản hồi để tự học xem policy nào đang tốt/xấu.
PHASE 3 — POLICY SIMULATION + SAFE AUTO-TUNING + MULTI-QUEUE STAFFING OPTIMIZER
Mục tiêu phase này là nâng hệ từ:
có policy engine
có tuning signal
có staffing recommendation
thành:
simulate policy trước khi áp dụng
safe auto-tuning thresholds
tối ưu staffing trên nhiều queue cùng lúc
cost-aware staffing vs SLA tradeoff
promote / rollback policy bundles
Mình giữ đúng nguyên tắc:
không tái cấu trúc
bám phase trước
file-by-file
paste-ready
chỗ nào repo thật cần map riêng, mình đánh dấu rõ
1) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
add 5 models
register imports vào base
add repositories
add schemas
add simulation / tuning / optimizer services
patch policy engine / rebalance service / staffing service
add routes
wire router
add migration
add worker
add tests
Frontend
add types
add APIs
add simulation / tuning / optimizer panels
patch policy governance area
patch staffing area
2) BACKEND — FULL FILES
backend/app/models/policy_simulation_run.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PolicySimulationRun(Base):
    __tablename__ = "policy_simulation_run"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bundle_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    simulation_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="queue")
    scope_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    baseline_sla_breach_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    projected_sla_breach_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    projected_churn_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    projected_rebalance_success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    projected_cost_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    projected_staffing_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    safety_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False, default="hold")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/policy_bundle.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PolicyBundle(Base):
    __tablename__ = "policy_bundle"

    bundle_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    # draft | simulated | promoted | rolled_back | archived

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    promoted_from_bundle_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rollback_target_bundle_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/policy_bundle_event.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PolicyBundleEvent(Base):
    __tablename__ = "policy_bundle_event"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bundle_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # simulated | promoted | rollback_requested | rolled_back | tuning_applied

    actor_id: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/policy_tuning_decision.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PolicyTuningDecision(Base):
    __tablename__ = "policy_tuning_decision"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    bundle_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    parameter_name: Mapped[str] = mapped_column(String(128), nullable=False)
    old_value: Mapped[str] = mapped_column(String(255), nullable=False)
    proposed_value: Mapped[str] = mapped_column(String(255), nullable=False)

    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    safety_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    auto_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decision_status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    # proposed | approved | auto_applied | rejected | rolled_back

    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/multi_queue_staffing_plan.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class MultiQueueStaffingPlan(Base):
    __tablename__ = "multi_queue_staffing_plan"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    queue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_forecast_load: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_effective_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_capacity_gap: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    projected_total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    projected_sla_protection_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    projected_tradeoff_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    recommendation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/db/base.py — PATCH
Thêm imports:
from app.models.policy_simulation_run import PolicySimulationRun
from app.models.policy_bundle import PolicyBundle
from app.models.policy_bundle_event import PolicyBundleEvent
from app.models.policy_tuning_decision import PolicyTuningDecision
from app.models.multi_queue_staffing_plan import MultiQueueStaffingPlan
backend/app/repositories/policy_simulation_run_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.policy_simulation_run import PolicySimulationRun


class PolicySimulationRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: PolicySimulationRun) -> PolicySimulationRun:
        self.db.add(model)
        return model

    def list_latest(self, bundle_key: str | None = None) -> list[PolicySimulationRun]:
        stmt = select(PolicySimulationRun)
        if bundle_key:
            stmt = stmt.where(PolicySimulationRun.bundle_key == bundle_key)
        stmt = stmt.order_by(desc(PolicySimulationRun.created_at))
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/policy_bundle_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.policy_bundle import PolicyBundle


class PolicyBundleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, bundle_key: str) -> PolicyBundle | None:
        return self.db.get(PolicyBundle, bundle_key)

    def upsert(self, model: PolicyBundle) -> PolicyBundle:
        existing = self.db.get(PolicyBundle, model.bundle_key)
        if existing:
            existing.display_name = model.display_name
            existing.status = model.status
            existing.active = model.active
            existing.version = model.version
            existing.description = model.description
            existing.promoted_from_bundle_key = model.promoted_from_bundle_key
            existing.rollback_target_bundle_key = model.rollback_target_bundle_key
            existing.updated_at = model.updated_at
            self.db.add(existing)
            return existing
        self.db.add(model)
        return model

    def list_all(self) -> list[PolicyBundle]:
        stmt = select(PolicyBundle).order_by(desc(PolicyBundle.updated_at))
        return list(self.db.execute(stmt).scalars().all())

    def get_active_bundle(self) -> PolicyBundle | None:
        stmt = select(PolicyBundle).where(PolicyBundle.active.is_(True))
        return self.db.execute(stmt).scalars().first()
backend/app/repositories/policy_bundle_event_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.policy_bundle_event import PolicyBundleEvent


class PolicyBundleEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: PolicyBundleEvent) -> PolicyBundleEvent:
        self.db.add(model)
        return model

    def list_latest(self, bundle_key: str | None = None) -> list[PolicyBundleEvent]:
        stmt = select(PolicyBundleEvent)
        if bundle_key:
            stmt = stmt.where(PolicyBundleEvent.bundle_key == bundle_key)
        stmt = stmt.order_by(desc(PolicyBundleEvent.created_at))
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/policy_tuning_decision_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.policy_tuning_decision import PolicyTuningDecision


class PolicyTuningDecisionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: PolicyTuningDecision) -> PolicyTuningDecision:
        self.db.add(model)
        return model

    def list_latest(self, policy_key: str | None = None) -> list[PolicyTuningDecision]:
        stmt = select(PolicyTuningDecision)
        if policy_key:
            stmt = stmt.where(PolicyTuningDecision.policy_key == policy_key)
        stmt = stmt.order_by(desc(PolicyTuningDecision.created_at))
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/multi_queue_staffing_plan_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.multi_queue_staffing_plan import MultiQueueStaffingPlan


class MultiQueueStaffingPlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: MultiQueueStaffingPlan) -> MultiQueueStaffingPlan:
        self.db.add(model)
        return model

    def list_latest(self, plan_key: str | None = None) -> list[MultiQueueStaffingPlan]:
        stmt = select(MultiQueueStaffingPlan)
        if plan_key:
            stmt = stmt.where(MultiQueueStaffingPlan.plan_key == plan_key)
        stmt = stmt.order_by(desc(MultiQueueStaffingPlan.created_at))
        return list(self.db.execute(stmt).scalars().all())
backend/app/schemas/policy_simulation.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class PolicySimulationRunRead(BaseModel):
    id: str
    bundle_key: str
    policy_key: str | None = None
    simulation_scope: str
    scope_key: str | None = None
    baseline_sla_breach_rate: float
    projected_sla_breach_rate: float
    projected_churn_rate: float
    projected_rebalance_success_rate: float
    projected_cost_delta: float
    projected_staffing_delta: int
    safety_score: float
    recommendation: str
    summary: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
backend/app/schemas/policy_bundle.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class PolicyBundleRead(BaseModel):
    bundle_key: str
    display_name: str
    status: str
    active: bool
    version: int
    description: str | None = None
    promoted_from_bundle_key: str | None = None
    rollback_target_bundle_key: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromotePolicyBundleRequest(BaseModel):
    bundle_key: str
    actor_id: str


class RollbackPolicyBundleRequest(BaseModel):
    bundle_key: str
    actor_id: str
    rollback_target_bundle_key: str | None = None
backend/app/schemas/policy_bundle_event.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class PolicyBundleEventRead(BaseModel):
    id: str
    bundle_key: str
    event_type: str
    actor_id: str
    detail: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
backend/app/schemas/policy_tuning_decision.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class PolicyTuningDecisionRead(BaseModel):
    id: str
    policy_key: str
    bundle_key: str | None = None
    parameter_name: str
    old_value: str
    proposed_value: str
    confidence_score: float
    safety_score: float
    sample_size: int
    auto_applied: bool
    decision_status: str
    rationale: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
backend/app/schemas/multi_queue_staffing_plan.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class MultiQueueStaffingPlanRead(BaseModel):
    id: str
    plan_key: str
    queue_count: int
    total_forecast_load: int
    total_effective_capacity: int
    total_capacity_gap: int
    projected_total_cost: float
    projected_sla_protection_score: float
    projected_tradeoff_score: float
    recommendation_summary: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
backend/app/services/policy_simulation_service.py
from __future__ import annotations

from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.policy_simulation_run import PolicySimulationRun
from app.repositories.policy_simulation_run_repository import PolicySimulationRunRepository


class PolicySimulationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PolicySimulationRunRepository(db)

    def compute_safety_score(
        self,
        *,
        baseline_sla_breach_rate: float,
        projected_sla_breach_rate: float,
        projected_churn_rate: float,
        projected_cost_delta: float,
    ) -> float:
        sla_gain = max(0.0, baseline_sla_breach_rate - projected_sla_breach_rate)
        churn_penalty = min(1.0, projected_churn_rate)
        cost_penalty = min(1.0, max(0.0, projected_cost_delta) / 100.0)
        score = (sla_gain * 0.55) + ((1.0 - churn_penalty) * 0.30) + ((1.0 - cost_penalty) * 0.15)
        return max(0.0, min(1.0, score))

    def simulate(
        self,
        *,
        bundle_key: str,
        policy_key: str | None,
        simulation_scope: str,
        scope_key: str | None,
        baseline_sla_breach_rate: float,
        projected_sla_breach_rate: float,
        projected_churn_rate: float,
        projected_rebalance_success_rate: float,
        projected_cost_delta: float,
        projected_staffing_delta: int,
    ) -> PolicySimulationRun:
        safety_score = self.compute_safety_score(
            baseline_sla_breach_rate=baseline_sla_breach_rate,
            projected_sla_breach_rate=projected_sla_breach_rate,
            projected_churn_rate=projected_churn_rate,
            projected_cost_delta=projected_cost_delta,
        )

        recommendation = "hold"
        if safety_score >= 0.80:
            recommendation = "promote"
        elif safety_score >= 0.60:
            recommendation = "canary"

        summary = (
            f"baseline_breach={baseline_sla_breach_rate:.3f}, "
            f"projected_breach={projected_sla_breach_rate:.3f}, "
            f"churn={projected_churn_rate:.3f}, "
            f"cost_delta={projected_cost_delta:.2f}, "
            f"safety={safety_score:.3f}"
        )

        model = PolicySimulationRun(
            id=str(uuid4()),
            bundle_key=bundle_key,
            policy_key=policy_key,
            simulation_scope=simulation_scope,
            scope_key=scope_key,
            baseline_sla_breach_rate=baseline_sla_breach_rate,
            projected_sla_breach_rate=projected_sla_breach_rate,
            projected_churn_rate=projected_churn_rate,
            projected_rebalance_success_rate=projected_rebalance_success_rate,
            projected_cost_delta=projected_cost_delta,
            projected_staffing_delta=projected_staffing_delta,
            safety_score=safety_score,
            recommendation=recommendation,
            summary=summary,
        )
        return self.repo.create(model)
backend/app/services/safe_policy_tuning_service.py
from __future__ import annotations

from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.policy_tuning_decision import PolicyTuningDecision
from app.repositories.policy_tuning_decision_repository import (
    PolicyTuningDecisionRepository,
)
from app.repositories.policy_tuning_signal_repository import PolicyTuningSignalRepository


class SafePolicyTuningService:
    def __init__(self, db: Session):
        self.db = db
        self.decision_repo = PolicyTuningDecisionRepository(db)
        self.signal_repo = PolicyTuningSignalRepository(db)

    def compute_confidence_score(self, signal_strength: float, sample_size: int) -> float:
        sample_factor = min(1.0, sample_size / 100.0)
        return max(0.0, min(1.0, (signal_strength * 0.7) + (sample_factor * 0.3)))

    def compute_safety_score(self, signal_type: str, signal_strength: float) -> float:
        if signal_type in {"sla_improved", "rebalance_success"}:
            return max(0.0, min(1.0, signal_strength))
        if signal_type in {"sla_worsened", "churn_increased", "rebalance_failure"}:
            return max(0.0, min(1.0, 1.0 - signal_strength))
        return 0.5

    def propose_tuning(
        self,
        *,
        policy_key: str,
        bundle_key: str | None,
        parameter_name: str,
        old_value: str,
        proposed_value: str,
        signal_type: str,
        signal_strength: float,
        sample_size: int,
        rationale: str | None = None,
    ) -> PolicyTuningDecision:
        confidence = self.compute_confidence_score(signal_strength, sample_size)
        safety = self.compute_safety_score(signal_type, signal_strength)

        auto_applied = confidence >= 0.85 and safety >= 0.80 and sample_size >= 50
        status = "auto_applied" if auto_applied else "proposed"

        model = PolicyTuningDecision(
            id=str(uuid4()),
            policy_key=policy_key,
            bundle_key=bundle_key,
            parameter_name=parameter_name,
            old_value=old_value,
            proposed_value=proposed_value,
            confidence_score=confidence,
            safety_score=safety,
            sample_size=sample_size,
            auto_applied=auto_applied,
            decision_status=status,
            rationale=rationale,
        )
        return self.decision_repo.create(model)
backend/app/services/multi_queue_staffing_optimizer_service.py
from __future__ import annotations

from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.multi_queue_staffing_plan import MultiQueueStaffingPlan
from app.repositories.multi_queue_staffing_plan_repository import (
    MultiQueueStaffingPlanRepository,
)


class MultiQueueStaffingOptimizerService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MultiQueueStaffingPlanRepository(db)

    def compute_tradeoff_score(
        self,
        *,
        total_capacity_gap: int,
        projected_total_cost: float,
        projected_sla_protection_score: float,
    ) -> float:
        normalized_gap_penalty = min(1.0, max(0.0, total_capacity_gap / 100.0))
        normalized_cost_penalty = min(1.0, max(0.0, projected_total_cost / 10000.0))
        score = (
            projected_sla_protection_score * 0.60
            + (1.0 - normalized_gap_penalty) * 0.25
            + (1.0 - normalized_cost_penalty) * 0.15
        )
        return max(0.0, min(1.0, score))

    def build_plan(
        self,
        *,
        plan_key: str,
        queue_count: int,
        total_forecast_load: int,
        total_effective_capacity: int,
        total_capacity_gap: int,
        projected_total_cost: float,
        projected_sla_protection_score: float,
        recommendation_summary: str | None = None,
    ) -> MultiQueueStaffingPlan:
        tradeoff = self.compute_tradeoff_score(
            total_capacity_gap=total_capacity_gap,
            projected_total_cost=projected_total_cost,
            projected_sla_protection_score=projected_sla_protection_score,
        )

        model = MultiQueueStaffingPlan(
            id=str(uuid4()),
            plan_key=plan_key,
            queue_count=queue_count,
            total_forecast_load=total_forecast_load,
            total_effective_capacity=total_effective_capacity,
            total_capacity_gap=total_capacity_gap,
            projected_total_cost=projected_total_cost,
            projected_sla_protection_score=projected_sla_protection_score,
            projected_tradeoff_score=tradeoff,
            recommendation_summary=recommendation_summary,
        )
        return self.repo.create(model)
backend/app/services/policy_bundle_lifecycle_service.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.policy_bundle import PolicyBundle
from app.models.policy_bundle_event import PolicyBundleEvent
from app.repositories.policy_bundle_event_repository import PolicyBundleEventRepository
from app.repositories.policy_bundle_repository import PolicyBundleRepository
from app.repositories.policy_simulation_run_repository import PolicySimulationRunRepository


def _utcnow():
    return datetime.now(timezone.utc)


class PolicyBundleLifecycleService:
    def __init__(self, db: Session):
        self.db = db
        self.bundle_repo = PolicyBundleRepository(db)
        self.event_repo = PolicyBundleEventRepository(db)
        self.sim_repo = PolicySimulationRunRepository(db)

    def promote_bundle(self, *, bundle_key: str, actor_id: str) -> PolicyBundle:
        bundle = self.bundle_repo.get(bundle_key)
        if bundle is None:
            raise ValueError("Policy bundle not found")

        sims = self.sim_repo.list_latest(bundle_key=bundle_key)
        latest = sims[0] if sims else None
        if latest is None or latest.recommendation not in {"promote", "canary"}:
            raise ValueError("Policy bundle cannot be promoted without passing simulation")

        active = self.bundle_repo.get_active_bundle()
        if active and active.bundle_key != bundle.bundle_key:
            active.active = False
            active.updated_at = _utcnow()
            self.db.add(active)

        bundle.status = "promoted"
        bundle.active = True
        bundle.updated_at = _utcnow()
        self.db.add(bundle)

        self.event_repo.create(
            PolicyBundleEvent(
                id=str(uuid4()),
                bundle_key=bundle_key,
                event_type="promoted",
                actor_id=actor_id,
                detail=f"Promoted with safety_score={latest.safety_score:.3f}",
            )
        )
        return bundle

    def rollback_bundle(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        rollback_target_bundle_key: str | None = None,
    ) -> PolicyBundle:
        bundle = self.bundle_repo.get(bundle_key)
        if bundle is None:
            raise ValueError("Policy bundle not found")

        bundle.active = False
        bundle.status = "rolled_back"
        bundle.rollback_target_bundle_key = rollback_target_bundle_key
        bundle.updated_at = _utcnow()
        self.db.add(bundle)

        if rollback_target_bundle_key:
            target = self.bundle_repo.get(rollback_target_bundle_key)
            if target:
                target.active = True
                target.status = "promoted"
                target.updated_at = _utcnow()
                self.db.add(target)

        self.event_repo.create(
            PolicyBundleEvent(
                id=str(uuid4()),
                bundle_key=bundle_key,
                event_type="rolled_back",
                actor_id=actor_id,
                detail=f"Rollback target={rollback_target_bundle_key or 'none'}",
            )
        )
        return bundle
3) BACKEND — PATCH CÁC FILE ĐANG CÓ
backend/app/models/review_rebalance_policy.py — PATCH
Nếu chưa có, thêm:
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

bundle_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
backend/app/repositories/review_rebalance_policy_repository.py — PATCH
Trong upsert(...), thêm:
existing.bundle_key = model.bundle_key
Trong create path giữ nguyên bundle_key.
backend/app/services/rebalance_policy_engine.py — PATCH
Nếu muốn engine chỉ dùng active bundle, thêm logic đầu evaluate(...):
from app.repositories.policy_bundle_repository import PolicyBundleRepository

self.bundle_repo = PolicyBundleRepository(db)
Trong __init__ thêm:
self.bundle_repo = PolicyBundleRepository(db)
Và trong evaluate(...), sau khi lấy policy:
active_bundle = self.bundle_repo.get_active_bundle()
if policy and active_bundle and getattr(policy, "bundle_key", None):
    if policy.bundle_key != active_bundle.bundle_key:
        return RebalancePolicyDecision(
            allowed=False,
            auto_apply=False,
            requires_human_approval=True,
            policy_key=policy.policy_key,
            reason_codes=["policy_not_in_active_bundle"],
        )
backend/app/services/staffing_recommendation_service.py — PATCH
Nếu muốn cost-aware ngay ở per-queue recommendation, thêm helper:
def estimate_staffing_cost(
    self,
    *,
    additional_reviewers: int,
    additional_supervisors: int,
    reviewer_unit_cost: float = 100.0,
    supervisor_unit_cost: float = 180.0,
) -> float:
    return additional_reviewers * reviewer_unit_cost + additional_supervisors * supervisor_unit_cost
backend/app/services/policy_tuning_service.py — PATCH
Có thể giữ file cũ, nhưng nếu muốn nối vào decision layer thì sau khi emit signal, dùng SafePolicyTuningService ở worker hoặc orchestration layer để tạo decision.
4) BACKEND — ROUTES
backend/app/api/routes/policy_optimization.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.multi_queue_staffing_plan_repository import (
    MultiQueueStaffingPlanRepository,
)
from app.repositories.policy_bundle_event_repository import PolicyBundleEventRepository
from app.repositories.policy_bundle_repository import PolicyBundleRepository
from app.repositories.policy_simulation_run_repository import PolicySimulationRunRepository
from app.repositories.policy_tuning_decision_repository import (
    PolicyTuningDecisionRepository,
)
from app.schemas.multi_queue_staffing_plan import MultiQueueStaffingPlanRead
from app.schemas.policy_bundle import (
    PolicyBundleRead,
    PromotePolicyBundleRequest,
    RollbackPolicyBundleRequest,
)
from app.schemas.policy_bundle_event import PolicyBundleEventRead
from app.schemas.policy_simulation import PolicySimulationRunRead
from app.schemas.policy_tuning_decision import PolicyTuningDecisionRead
from app.services.policy_bundle_lifecycle_service import PolicyBundleLifecycleService

router = APIRouter(prefix="/policy-optimization", tags=["policy-optimization"])


@router.get("/simulation-runs", response_model=list[PolicySimulationRunRead])
def list_simulation_runs(bundle_key: str | None = None, db: Session = Depends(get_db)):
    repo = PolicySimulationRunRepository(db)
    return repo.list_latest(bundle_key=bundle_key)


@router.get("/bundles", response_model=list[PolicyBundleRead])
def list_policy_bundles(db: Session = Depends(get_db)):
    repo = PolicyBundleRepository(db)
    return repo.list_all()


@router.get("/bundle-events", response_model=list[PolicyBundleEventRead])
def list_policy_bundle_events(bundle_key: str | None = None, db: Session = Depends(get_db)):
    repo = PolicyBundleEventRepository(db)
    return repo.list_latest(bundle_key=bundle_key)


@router.post("/bundles/promote", response_model=PolicyBundleRead)
def promote_policy_bundle(payload: PromotePolicyBundleRequest, db: Session = Depends(get_db)):
    svc = PolicyBundleLifecycleService(db)
    try:
        bundle = svc.promote_bundle(bundle_key=payload.bundle_key, actor_id=payload.actor_id)
        db.commit()
        db.refresh(bundle)
        return bundle
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/bundles/rollback", response_model=PolicyBundleRead)
def rollback_policy_bundle(payload: RollbackPolicyBundleRequest, db: Session = Depends(get_db)):
    svc = PolicyBundleLifecycleService(db)
    try:
        bundle = svc.rollback_bundle(
            bundle_key=payload.bundle_key,
            actor_id=payload.actor_id,
            rollback_target_bundle_key=payload.rollback_target_bundle_key,
        )
        db.commit()
        db.refresh(bundle)
        return bundle
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/tuning-decisions", response_model=list[PolicyTuningDecisionRead])
def list_tuning_decisions(policy_key: str | None = None, db: Session = Depends(get_db)):
    repo = PolicyTuningDecisionRepository(db)
    return repo.list_latest(policy_key=policy_key)


@router.get("/multi-queue-staffing-plans", response_model=list[MultiQueueStaffingPlanRead])
def list_multi_queue_staffing_plans(plan_key: str | None = None, db: Session = Depends(get_db)):
    repo = MultiQueueStaffingPlanRepository(db)
    return repo.list_latest(plan_key=plan_key)
backend/app/api/api_v1/api.py — PATCH
Thêm import:
from app.api.routes import policy_optimization
Và include:
api_router.include_router(policy_optimization.router)
5) BACKEND — MIGRATION
backend/alembic/versions/phase3_policy_simulation_autotuning_optimizer.py
from alembic import op
import sqlalchemy as sa


revision = "phase3_policy_simulation_autotuning_optimizer"
down_revision = "phase3_policy_staffing_guardrails"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "policy_simulation_run",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("bundle_key", sa.String(length=128), nullable=False),
        sa.Column("policy_key", sa.String(length=128), nullable=True),
        sa.Column("simulation_scope", sa.String(length=64), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=True),
        sa.Column("baseline_sla_breach_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("projected_sla_breach_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("projected_churn_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("projected_rebalance_success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("projected_cost_delta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("projected_staffing_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safety_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recommendation", sa.String(length=32), nullable=False, server_default="hold"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_simulation_run_bundle_key", "policy_simulation_run", ["bundle_key"])
    op.create_index("ix_policy_simulation_run_policy_key", "policy_simulation_run", ["policy_key"])

    op.create_table(
        "policy_bundle",
        sa.Column("bundle_key", sa.String(length=128), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("promoted_from_bundle_key", sa.String(length=128), nullable=True),
        sa.Column("rollback_target_bundle_key", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "policy_bundle_event",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("bundle_key", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_bundle_event_bundle_key", "policy_bundle_event", ["bundle_key"])
    op.create_index("ix_policy_bundle_event_event_type", "policy_bundle_event", ["event_type"])

    op.create_table(
        "policy_tuning_decision",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("policy_key", sa.String(length=128), nullable=False),
        sa.Column("bundle_key", sa.String(length=128), nullable=True),
        sa.Column("parameter_name", sa.String(length=128), nullable=False),
        sa.Column("old_value", sa.String(length=255), nullable=False),
        sa.Column("proposed_value", sa.String(length=255), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("safety_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("decision_status", sa.String(length=32), nullable=False, server_default="proposed"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_tuning_decision_policy_key", "policy_tuning_decision", ["policy_key"])
    op.create_index("ix_policy_tuning_decision_bundle_key", "policy_tuning_decision", ["bundle_key"])

    op.create_table(
        "multi_queue_staffing_plan",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("plan_key", sa.String(length=128), nullable=False),
        sa.Column("queue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_forecast_load", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_effective_capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_capacity_gap", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("projected_total_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("projected_sla_protection_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("projected_tradeoff_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recommendation_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_multi_queue_staffing_plan_plan_key", "multi_queue_staffing_plan", ["plan_key"])

    # Optional patch existing table if needed
    # op.add_column("review_rebalance_policy", sa.Column("bundle_key", sa.String(length=128), nullable=True))
    # op.create_index("ix_review_rebalance_policy_bundle_key", "review_rebalance_policy", ["bundle_key"])
def downgrade():
    op.drop_index("ix_multi_queue_staffing_plan_plan_key", table_name="multi_queue_staffing_plan")
    op.drop_table("multi_queue_staffing_plan")

    op.drop_index("ix_policy_tuning_decision_bundle_key", table_name="policy_tuning_decision")
    op.drop_index("ix_policy_tuning_decision_policy_key", table_name="policy_tuning_decision")
    op.drop_table("policy_tuning_decision")

    op.drop_index("ix_policy_bundle_event_event_type", table_name="policy_bundle_event")
    op.drop_index("ix_policy_bundle_event_bundle_key", table_name="policy_bundle_event")
    op.drop_table("policy_bundle_event")

    op.drop_table("policy_bundle")

    op.drop_index("ix_policy_simulation_run_policy_key", table_name="policy_simulation_run")
    op.drop_index("ix_policy_simulation_run_bundle_key", table_name="policy_simulation_run")
    op.drop_table("policy_simulation_run")
6) BACKEND — WORKER
backend/app/workers/policy_optimization_worker.py
from __future__ import annotations

from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.policy_bundle import PolicyBundle
from app.models.review_rebalance_policy import ReviewRebalancePolicy
from app.repositories.policy_bundle_repository import PolicyBundleRepository
from app.repositories.review_rebalance_policy_repository import (
    ReviewRebalancePolicyRepository,
)
from app.services.multi_queue_staffing_optimizer_service import (
    MultiQueueStaffingOptimizerService,
)
from app.services.policy_simulation_service import PolicySimulationService
from app.services.safe_policy_tuning_service import SafePolicyTuningService


def _utcnow():
    return datetime.now(timezone.utc)


@celery_app.task(name="policy_optimization.refresh")
def refresh_policy_optimization():
    db = SessionLocal()
    try:
        bundle_repo = PolicyBundleRepository(db)
        policy_repo = ReviewRebalancePolicyRepository(db)
        sim_service = PolicySimulationService(db)
        tuning_service = SafePolicyTuningService(db)
        mq_service = MultiQueueStaffingOptimizerService(db)

        bundle = bundle_repo.upsert(
            PolicyBundle(
                bundle_key="bundle_human_review_v2",
                display_name="Human Review Bundle V2",
                status="simulated",
                active=False,
                version=2,
                description="Safer high-severity rebalance thresholds.",
                created_by="system",
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
        )

        policy_repo.upsert(
            ReviewRebalancePolicy(
                policy_key="human_review_high_v2",
                bundle_key=bundle.bundle_key,
                enabled=True,
                queue_key="human_review",
                severity="high",
                allow_auto_rebalance=True,
                require_human_approval=False,
                min_recommendation_score=7.5,
                min_capacity_gap_to_trigger=2,
                max_target_reviewer_load_ratio=0.65,
                allow_if_overdue=True,
                allow_if_pending_approval=True,
                allow_sensitive_projects=False,
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
        )

        sim_service.simulate(
            bundle_key=bundle.bundle_key,
            policy_key="human_review_high_v2",
            simulation_scope="queue",
            scope_key="human_review",
            baseline_sla_breach_rate=0.18,
            projected_sla_breach_rate=0.11,
            projected_churn_rate=0.05,
            projected_rebalance_success_rate=0.82,
            projected_cost_delta=220.0,
            projected_staffing_delta=2,
        )

        tuning_service.propose_tuning(
            policy_key="human_review_high_v2",
            bundle_key=bundle.bundle_key,
            parameter_name="min_recommendation_score",
            old_value="7.0",
            proposed_value="7.5",
            signal_type="rebalance_success",
            signal_strength=0.88,
            sample_size=72,
            rationale="Higher recommendation threshold improved rebalance outcomes with low churn.",
        )

        mq_service.build_plan(
            plan_key="global_review_ops_plan",
            queue_count=3,
            total_forecast_load=210,
            total_effective_capacity=170,
            total_capacity_gap=40,
            projected_total_cost=1280.0,
            projected_sla_protection_score=0.81,
            recommendation_summary="Allocate more staffing to human_review and approvals queue; keep low-severity queue lean.",
        )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
7) BACKEND — TESTS
backend/tests/services/test_policy_simulation_service.py
from app.services.policy_simulation_service import PolicySimulationService


def test_simulation_computes_safety_and_recommendation(db_session):
    svc = PolicySimulationService(db_session)

    row = svc.simulate(
        bundle_key="bundle_1",
        policy_key="policy_1",
        simulation_scope="queue",
        scope_key="human_review",
        baseline_sla_breach_rate=0.20,
        projected_sla_breach_rate=0.10,
        projected_churn_rate=0.04,
        projected_rebalance_success_rate=0.80,
        projected_cost_delta=100.0,
        projected_staffing_delta=1,
    )

    assert row.safety_score > 0.0
    assert row.recommendation in {"hold", "canary", "promote"}
backend/tests/services/test_safe_policy_tuning_service.py
from app.services.safe_policy_tuning_service import SafePolicyTuningService


def test_safe_tuning_auto_applies_only_when_safe_and_confident(db_session):
    svc = SafePolicyTuningService(db_session)

    row = svc.propose_tuning(
        policy_key="policy_1",
        bundle_key="bundle_1",
        parameter_name="min_recommendation_score",
        old_value="7.0",
        proposed_value="7.5",
        signal_type="rebalance_success",
        signal_strength=0.92,
        sample_size=80,
        rationale="Strong signal.",
    )

    assert row.auto_applied is True
    assert row.decision_status == "auto_applied"
backend/tests/services/test_multi_queue_staffing_optimizer_service.py
from app.services.multi_queue_staffing_optimizer_service import (
    MultiQueueStaffingOptimizerService,
)


def test_multi_queue_optimizer_builds_plan(db_session):
    svc = MultiQueueStaffingOptimizerService(db_session)

    row = svc.build_plan(
        plan_key="plan_1",
        queue_count=3,
        total_forecast_load=200,
        total_effective_capacity=160,
        total_capacity_gap=40,
        projected_total_cost=1200.0,
        projected_sla_protection_score=0.78,
        recommendation_summary="Shift 2 reviewers to human_review.",
    )

    assert row.queue_count == 3
    assert row.projected_tradeoff_score > 0.0
backend/tests/services/test_policy_bundle_lifecycle_service.py
from datetime import datetime

from app.models.policy_bundle import PolicyBundle
from app.services.policy_bundle_lifecycle_service import PolicyBundleLifecycleService
from app.services.policy_simulation_service import PolicySimulationService
from app.repositories.policy_bundle_repository import PolicyBundleRepository


def test_promote_bundle_requires_good_simulation(db_session):
    bundle_repo = PolicyBundleRepository(db_session)
    bundle_repo.upsert(
        PolicyBundle(
            bundle_key="bundle_test",
            display_name="Bundle Test",
            status="simulated",
            active=False,
            version=1,
            description="Test",
            created_by="tester",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )

    sim = PolicySimulationService(db_session)
    sim.simulate(
        bundle_key="bundle_test",
        policy_key="policy_test",
        simulation_scope="queue",
        scope_key="human_review",
        baseline_sla_breach_rate=0.20,
        projected_sla_breach_rate=0.09,
        projected_churn_rate=0.03,
        projected_rebalance_success_rate=0.84,
        projected_cost_delta=150.0,
        projected_staffing_delta=1,
    )

    svc = PolicyBundleLifecycleService(db_session)
    bundle = svc.promote_bundle(bundle_key="bundle_test", actor_id="tester")

    assert bundle.active is True
    assert bundle.status == "promoted"
8) FRONTEND — FULL FILES
frontend/src/types/policyOptimization.ts
export type PolicySimulationRun = {
  id: string;
  bundle_key: string;
  policy_key?: string | null;
  simulation_scope: string;
  scope_key?: string | null;
  baseline_sla_breach_rate: number;
  projected_sla_breach_rate: number;
  projected_churn_rate: number;
  projected_rebalance_success_rate: number;
  projected_cost_delta: number;
  projected_staffing_delta: number;
  safety_score: number;
  recommendation: string;
  summary?: string | null;
  created_at: string;
};

export type PolicyBundle = {
  bundle_key: string;
  display_name: string;
  status: string;
  active: boolean;
  version: number;
  description?: string | null;
  promoted_from_bundle_key?: string | null;
  rollback_target_bundle_key?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type PolicyBundleEvent = {
  id: string;
  bundle_key: string;
  event_type: string;
  actor_id: string;
  detail?: string | null;
  created_at: string;
};

export type PolicyTuningDecision = {
  id: string;
  policy_key: string;
  bundle_key?: string | null;
  parameter_name: string;
  old_value: string;
  proposed_value: string;
  confidence_score: number;
  safety_score: number;
  sample_size: number;
  auto_applied: boolean;
  decision_status: string;
  rationale?: string | null;
  created_at: string;
};

export type MultiQueueStaffingPlan = {
  id: string;
  plan_key: string;
  queue_count: number;
  total_forecast_load: number;
  total_effective_capacity: number;
  total_capacity_gap: number;
  projected_total_cost: number;
  projected_sla_protection_score: number;
  projected_tradeoff_score: number;
  recommendation_summary?: string | null;
  created_at: string;
};
frontend/src/api/policyOptimization.ts
import { api } from "./client";
import {
  MultiQueueStaffingPlan,
  PolicyBundle,
  PolicyBundleEvent,
  PolicySimulationRun,
  PolicyTuningDecision,
} from "../types/policyOptimization";

export async function fetchPolicySimulationRuns(bundleKey?: string): Promise<PolicySimulationRun[]> {
  const res = await api.get("/policy-optimization/simulation-runs", {
    params: bundleKey ? { bundle_key: bundleKey } : {},
  });
  return res.data;
}

export async function fetchPolicyBundles(): Promise<PolicyBundle[]> {
  const res = await api.get("/policy-optimization/bundles");
  return res.data;
}

export async function fetchPolicyBundleEvents(bundleKey?: string): Promise<PolicyBundleEvent[]> {
  const res = await api.get("/policy-optimization/bundle-events", {
    params: bundleKey ? { bundle_key: bundleKey } : {},
  });
  return res.data;
}

export async function promotePolicyBundle(payload: {
  bundle_key: string;
  actor_id: string;
}): Promise<PolicyBundle> {
  const res = await api.post("/policy-optimization/bundles/promote", payload);
  return res.data;
}

export async function rollbackPolicyBundle(payload: {
  bundle_key: string;
  actor_id: string;
  rollback_target_bundle_key?: string;
}): Promise<PolicyBundle> {
  const res = await api.post("/policy-optimization/bundles/rollback", payload);
  return res.data;
}

export async function fetchPolicyTuningDecisions(policyKey?: string): Promise<PolicyTuningDecision[]> {
  const res = await api.get("/policy-optimization/tuning-decisions", {
    params: policyKey ? { policy_key: policyKey } : {},
  });
  return res.data;
}

export async function fetchMultiQueueStaffingPlans(planKey?: string): Promise<MultiQueueStaffingPlan[]> {
  const res = await api.get("/policy-optimization/multi-queue-staffing-plans", {
    params: planKey ? { plan_key: planKey } : {},
  });
  return res.data;
}
frontend/src/components/review/PolicySimulationPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchPolicySimulationRuns } from "../../api/policyOptimization";
import { PolicySimulationRun } from "../../types/policyOptimization";

type Props = {
  bundleKey?: string;
};

export function PolicySimulationPanel({ bundleKey }: Props) {
  const [rows, setRows] = useState<PolicySimulationRun[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load(bundleKey);
  }, [bundleKey]);

  async function load(nextBundleKey?: string) {
    setLoading(true);
    try {
      setRows(await fetchPolicySimulationRuns(nextBundleKey));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Policy Simulation</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load(bundleKey)} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.id} className="rounded border p-3">
          <div className="font-medium">{row.bundle_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            Scope: {row.simulation_scope} / {row.scope_key ?? "global"} · Recommendation: {row.recommendation}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Baseline breach: {(row.baseline_sla_breach_rate * 100).toFixed(1)}% · Projected breach:{" "}
            {(row.projected_sla_breach_rate * 100).toFixed(1)}%
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Churn: {(row.projected_churn_rate * 100).toFixed(1)}% · Cost delta: {row.projected_cost_delta.toFixed(2)}
          </div>
          <div className="mt-1 text-xs text-gray-500">
            Safety: {(row.safety_score * 100).toFixed(1)}% · {row.summary}
          </div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No simulation data.</div> : null}
    </div>
  );
}
frontend/src/components/review/PolicyBundlePanel.tsx
import React, { useEffect, useState } from "react";
import {
  fetchPolicyBundles,
  promotePolicyBundle,
  rollbackPolicyBundle,
} from "../../api/policyOptimization";
import { PolicyBundle } from "../../types/policyOptimization";

export function PolicyBundlePanel() {
  const [rows, setRows] = useState<PolicyBundle[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setRows(await fetchPolicyBundles());
    } finally {
      setLoading(false);
    }
  }

  async function onPromote(bundleKey: string) {
    await promotePolicyBundle({ bundle_key: bundleKey, actor_id: "ui_operator" });
    await load();
  }

  async function onRollback(bundleKey: string) {
    await rollbackPolicyBundle({ bundle_key: bundleKey, actor_id: "ui_operator" });
    await load();
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Policy Bundles</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.bundle_key} className="rounded border p-3">
          <div className="font-medium">{row.display_name}</div>
          <div className="mt-1 text-sm text-gray-600">
            Key: {row.bundle_key} · Version: {row.version} · Status: {row.status}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Active: {row.active ? "yes" : "no"}
          </div>
          <div className="mt-1 text-xs text-gray-500">{row.description ?? "No description."}</div>

          <div className="mt-3 flex gap-2">
            <button className="rounded border px-3 py-1 text-sm" onClick={() => void onPromote(row.bundle_key)}>
              Promote
            </button>
            <button className="rounded border px-3 py-1 text-sm" onClick={() => void onRollback(row.bundle_key)}>
              Rollback
            </button>
          </div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No bundles.</div> : null}
    </div>
  );
}
frontend/src/components/review/PolicyTuningDecisionPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchPolicyTuningDecisions } from "../../api/policyOptimization";
import { PolicyTuningDecision } from "../../types/policyOptimization";

type Props = {
  policyKey?: string;
};

export function PolicyTuningDecisionPanel({ policyKey }: Props) {
  const [rows, setRows] = useState<PolicyTuningDecision[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load(policyKey);
  }, [policyKey]);

  async function load(nextPolicyKey?: string) {
    setLoading(true);
    try {
      setRows(await fetchPolicyTuningDecisions(nextPolicyKey));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Safe Auto-Tuning Decisions</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load(policyKey)} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.id} className="rounded border p-3">
          <div className="font-medium">{row.policy_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            {row.parameter_name}: {row.old_value} → {row.proposed_value}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Confidence: {(row.confidence_score * 100).toFixed(1)}% · Safety: {(row.safety_score * 100).toFixed(1)}%
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Sample size: {row.sample_size} · Status: {row.decision_status}
          </div>
          <div className="mt-1 text-xs text-gray-500">{row.rationale ?? "No rationale."}</div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No tuning decisions.</div> : null}
    </div>
  );
}
frontend/src/components/review/MultiQueueStaffingOptimizerPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchMultiQueueStaffingPlans } from "../../api/policyOptimization";
import { MultiQueueStaffingPlan } from "../../types/policyOptimization";

type Props = {
  planKey?: string;
};

export function MultiQueueStaffingOptimizerPanel({ planKey }: Props) {
  const [rows, setRows] = useState<MultiQueueStaffingPlan[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load(planKey);
  }, [planKey]);

  async function load(nextPlanKey?: string) {
    setLoading(true);
    try {
      setRows(await fetchMultiQueueStaffingPlans(nextPlanKey));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Multi-Queue Staffing Optimizer</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load(planKey)} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.id} className="rounded border p-3">
          <div className="font-medium">{row.plan_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            Queues: {row.queue_count} · Forecast load: {row.total_forecast_load} · Capacity: {row.total_effective_capacity}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Gap: {row.total_capacity_gap} · Cost: {row.projected_total_cost.toFixed(2)}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            SLA protection: {(row.projected_sla_protection_score * 100).toFixed(1)}% · Tradeoff:{" "}
            {(row.projected_tradeoff_score * 100).toFixed(1)}%
          </div>
          <div className="mt-1 text-xs text-gray-500">{row.recommendation_summary ?? "No summary."}</div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No staffing plans.</div> : null}
    </div>
  );
}
9) FRONTEND — PATCH CÁC FILE ĐANG CÓ
frontend/src/components/review/ReviewDecisionPanel.tsx — PATCH
Thêm imports:
import { PolicySimulationPanel } from "./PolicySimulationPanel";
import { PolicyBundlePanel } from "./PolicyBundlePanel";
import { PolicyTuningDecisionPanel } from "./PolicyTuningDecisionPanel";
Trong JSX thêm:
<PolicySimulationPanel />
<PolicyBundlePanel />
<PolicyTuningDecisionPanel />
frontend/src/components/review/HumanReviewQueuePanel.tsx — PATCH
Thêm import:
import { MultiQueueStaffingOptimizerPanel } from "./MultiQueueStaffingOptimizerPanel";
Trong JSX thêm:
<MultiQueueStaffingOptimizerPanel />
frontend/src/components/review/StaffingRecommendationPanel.tsx — PATCH
Nếu muốn hiển thị bridge từ per-queue sang multi-queue, thêm note:
<div className="text-xs text-gray-500">
  These queue-level recommendations should be reviewed alongside the multi-queue optimizer for global cost vs SLA tradeoffs.
</div>
10) ĐIỂM MAP QUAN TRỌNG KHI DÁN VÀO REPO THẬT
A. Simulation hiện là safe deterministic model
Hiện PolicySimulationService dùng công thức dự báo đơn giản. Trong repo thật, nên map sang:
historical SLA breach deltas
actual churn / rework rates
realized rebalance success
realized staffing cost
B. Auto-tuning hiện chỉ tạo decision
SafePolicyTuningService mới sinh PolicyTuningDecision. Nếu muốn auto-apply thật, bạn map tiếp sang:
repository update policy field
emit bundle event
maybe create canary version thay vì sửa trực tiếp active policy
C. Bundle promotion
PolicyBundleLifecycleService đang check simulation pass trước khi promote. Repo thật có thể siết thêm:
require min sample size
require no harmful signal in last N hours
require supervisor guardrail compatibility
D. Multi-queue optimizer
Hiện MultiQueueStaffingOptimizerService làm tổng hợp cấp cao. Repo thật có thể mở rộng:
allocate headcount per queue
prioritize queues by severity / revenue / SLA class
shift borrowing rules giữa queues
11) KẾT QUẢ SAU PATCH NÀY
Sau phase này, hệ của bạn đã đi từ:
policy-governed self-adjusting review operations
sang:
simulation-backed, safely tuned, cost-aware governance optimization
Cụ thể hệ đã có:
A. Policy simulation
Policy không cần áp thẳng. Có thể simulate trước.
B. Safe auto-tuning
Threshold chỉ được auto-tune khi đủ confidence + đủ safety + đủ sample size.
C. Multi-queue staffing optimizer
Không chỉ tối ưu từng queue riêng lẻ, mà tối ưu toàn cục giữa nhiều queue.
D. Promote / rollback bundle
Có khái niệm bundle policy versioning và lifecycle thật.
E. Policy event trail
Có nền để làm audit promotion, rollback, tuning, canary.
PHASE 3 — CANARY POLICY RELEASE + REALIZED OUTCOME ATTRIBUTION + AUTO-ROLLBACK GUARD
Mục tiêu phase này là nâng hệ từ:
simulate trước khi promote
có tuning decision
có bundle lifecycle
thành:
canary rollout theo % queue / severity / shift
đo realized outcome thật sau rollout
auto-rollback nếu SLA/churn xấu đi
attribution rõ policy nào gây tốt/xấu
closed-loop policy delivery system
Mình giữ đúng nguyên tắc:
không tái cấu trúc
bám phase trước
file-by-file
paste-ready
chỗ nào repo thật cần map sang repository/runtime thật mình ghi rõ
1) THỨ TỰ PASTE KHUYẾN NGHỊ
Backend
add 5 models
register imports vào base
add repositories
add schemas
add canary / attribution / rollback services
patch bundle lifecycle / rebalance policy engine / worker orchestration
add routes
wire router
add migration
add worker
add tests
Frontend
add types
add APIs
add canary / realized outcome / rollback panels
patch policy optimization area
patch governance analytics area
2) BACKEND — FULL FILES
backend/app/models/policy_canary_release.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PolicyCanaryRelease(Base):
    __tablename__ = "policy_canary_release"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bundle_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    rollout_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="queue")
    scope_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    severity: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    shift_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    rollout_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cohort_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    # scheduled | active | completed | rolled_back | paused

    auto_promote_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_rollback_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/policy_realized_outcome.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PolicyRealizedOutcome(Base):
    __tablename__ = "policy_realized_outcome"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bundle_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canary_release_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    scope_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    shift_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    observed_sla_breach_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    observed_churn_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    observed_rebalance_success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    observed_cost_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    baseline_sla_breach_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    baseline_churn_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    baseline_rebalance_success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome_label: Mapped[str] = mapped_column(String(32), nullable=False, default="neutral")
    # positive | neutral | negative

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/policy_outcome_attribution.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PolicyOutcomeAttribution(Base):
    __tablename__ = "policy_outcome_attribution"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bundle_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    canary_release_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    attribution_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="queue")
    scope_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    positive_effect_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    negative_effect_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_effect_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    impacted_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attribution_label: Mapped[str] = mapped_column(String(32), nullable=False, default="mixed")
    # winner | mixed | loser

    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/policy_rollback_guard.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PolicyRollbackGuard(Base):
    __tablename__ = "policy_rollback_guard"

    guard_key: Mapped[str] = mapped_column(String(128), primary_key=True)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bundle_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    scope_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    max_sla_breach_increase: Mapped[float] = mapped_column(Float, nullable=False, default=0.03)
    max_churn_increase: Mapped[float] = mapped_column(Float, nullable=False, default=0.02)
    min_rebalance_success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.50)
    min_sample_size: Mapped[float] = mapped_column(Float, nullable=False, default=20)

    auto_rollback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/models/policy_delivery_state.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PolicyDeliveryState(Base):
    __tablename__ = "policy_delivery_state"

    state_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    bundle_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    delivery_stage: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    # draft | simulated | canary | promoted | rollback | archived

    current_canary_release_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    last_outcome_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_guard_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # pass | warn | rollback

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
backend/app/db/base.py — PATCH
Thêm imports:
from app.models.policy_canary_release import PolicyCanaryRelease
from app.models.policy_realized_outcome import PolicyRealizedOutcome
from app.models.policy_outcome_attribution import PolicyOutcomeAttribution
from app.models.policy_rollback_guard import PolicyRollbackGuard
from app.models.policy_delivery_state import PolicyDeliveryState
backend/app/repositories/policy_canary_release_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.policy_canary_release import PolicyCanaryRelease


class PolicyCanaryReleaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: PolicyCanaryRelease) -> PolicyCanaryRelease:
        self.db.add(model)
        return model

    def get(self, release_id: str) -> PolicyCanaryRelease | None:
        return self.db.get(PolicyCanaryRelease, release_id)

    def list_latest(self, bundle_key: str | None = None) -> list[PolicyCanaryRelease]:
        stmt = select(PolicyCanaryRelease)
        if bundle_key:
            stmt = stmt.where(PolicyCanaryRelease.bundle_key == bundle_key)
        stmt = stmt.order_by(desc(PolicyCanaryRelease.created_at))
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/policy_realized_outcome_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.policy_realized_outcome import PolicyRealizedOutcome


class PolicyRealizedOutcomeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: PolicyRealizedOutcome) -> PolicyRealizedOutcome:
        self.db.add(model)
        return model

    def list_latest(self, bundle_key: str | None = None) -> list[PolicyRealizedOutcome]:
        stmt = select(PolicyRealizedOutcome)
        if bundle_key:
            stmt = stmt.where(PolicyRealizedOutcome.bundle_key == bundle_key)
        stmt = stmt.order_by(desc(PolicyRealizedOutcome.observed_at))
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/policy_outcome_attribution_repository.py
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.policy_outcome_attribution import PolicyOutcomeAttribution


class PolicyOutcomeAttributionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, model: PolicyOutcomeAttribution) -> PolicyOutcomeAttribution:
        self.db.add(model)
        return model

    def list_latest(self, bundle_key: str | None = None) -> list[PolicyOutcomeAttribution]:
        stmt = select(PolicyOutcomeAttribution)
        if bundle_key:
            stmt = stmt.where(PolicyOutcomeAttribution.bundle_key == bundle_key)
        stmt = stmt.order_by(desc(PolicyOutcomeAttribution.created_at))
        return list(self.db.execute(stmt).scalars().all())
backend/app/repositories/policy_rollback_guard_repository.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.policy_rollback_guard import PolicyRollbackGuard


class PolicyRollbackGuardRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, guard_key: str) -> PolicyRollbackGuard | None:
        return self.db.get(PolicyRollbackGuard, guard_key)

    def upsert(self, model: PolicyRollbackGuard) -> PolicyRollbackGuard:
        existing = self.db.get(PolicyRollbackGuard, model.guard_key)
        if existing:
            existing.enabled = model.enabled
            existing.bundle_key = model.bundle_key
            existing.scope_key = model.scope_key
            existing.max_sla_breach_increase = model.max_sla_breach_increase
            existing.max_churn_increase = model.max_churn_increase
            existing.min_rebalance_success_rate = model.min_rebalance_success_rate
            existing.min_sample_size = model.min_sample_size
            existing.auto_rollback = model.auto_rollback
            existing.reason_template = model.reason_template
            existing.updated_at = model.updated_at
            self.db.add(existing)
            return existing

        self.db.add(model)
        return model

    def list_all(self) -> list[PolicyRollbackGuard]:
        stmt = select(PolicyRollbackGuard).order_by(PolicyRollbackGuard.guard_key.asc())
        return list(self.db.execute(stmt).scalars().all())

    def find_best_match(self, bundle_key: str | None, scope_key: str | None) -> PolicyRollbackGuard | None:
        stmt = select(PolicyRollbackGuard).where(PolicyRollbackGuard.enabled.is_(True))
        guards = list(self.db.execute(stmt).scalars().all())

        exact = [g for g in guards if g.bundle_key == bundle_key and g.scope_key == scope_key]
        if exact:
            return exact[0]

        bundle_only = [g for g in guards if g.bundle_key == bundle_key and g.scope_key is None]
        if bundle_only:
            return bundle_only[0]

        global_default = [g for g in guards if g.bundle_key is None and g.scope_key is None]
        return global_default[0] if global_default else None
backend/app/repositories/policy_delivery_state_repository.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.policy_delivery_state import PolicyDeliveryState


class PolicyDeliveryStateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, state_key: str) -> PolicyDeliveryState | None:
        return self.db.get(PolicyDeliveryState, state_key)

    def upsert(self, model: PolicyDeliveryState) -> PolicyDeliveryState:
        existing = self.db.get(PolicyDeliveryState, model.state_key)
        if existing:
            existing.bundle_key = model.bundle_key
            existing.delivery_stage = model.delivery_stage
            existing.current_canary_release_id = model.current_canary_release_id
            existing.last_outcome_label = model.last_outcome_label
            existing.last_guard_decision = model.last_guard_decision
            existing.summary = model.summary
            existing.updated_at = model.updated_at
            self.db.add(existing)
            return existing

        self.db.add(model)
        return model

    def list_all(self) -> list[PolicyDeliveryState]:
        stmt = select(PolicyDeliveryState).order_by(PolicyDeliveryState.updated_at.desc())
        return list(self.db.execute(stmt).scalars().all())
backend/app/schemas/policy_canary_release.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class PolicyCanaryReleaseRead(BaseModel):
    id: str
    bundle_key: str
    rollout_scope: str
    scope_key: str | None = None
    severity: str | None = None
    shift_key: str | None = None
    rollout_percent: float
    cohort_size: int
    status: str
    auto_promote_enabled: bool
    auto_rollback_enabled: bool
    notes: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CreateCanaryReleaseRequest(BaseModel):
    bundle_key: str
    rollout_scope: str = "queue"
    scope_key: str | None = None
    severity: str | None = None
    shift_key: str | None = None
    rollout_percent: float
    cohort_size: int = 0
    auto_promote_enabled: bool = False
    auto_rollback_enabled: bool = True
    notes: str | None = None
backend/app/schemas/policy_realized_outcome.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class PolicyRealizedOutcomeRead(BaseModel):
    id: str
    bundle_key: str
    canary_release_id: str | None = None
    scope_key: str | None = None
    severity: str | None = None
    shift_key: str | None = None
    observed_sla_breach_rate: float
    observed_churn_rate: float
    observed_rebalance_success_rate: float
    observed_cost_delta: float
    baseline_sla_breach_rate: float
    baseline_churn_rate: float
    baseline_rebalance_success_rate: float
    sample_size: int
    outcome_label: str
    summary: str | None = None
    observed_at: datetime

    class Config:
        from_attributes = True
backend/app/schemas/policy_outcome_attribution.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class PolicyOutcomeAttributionRead(BaseModel):
    id: str
    bundle_key: str
    policy_key: str | None = None
    canary_release_id: str | None = None
    attribution_scope: str
    scope_key: str | None = None
    positive_effect_score: float
    negative_effect_score: float
    net_effect_score: float
    impacted_case_count: int
    attribution_label: str
    rationale: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
backend/app/schemas/policy_rollback_guard.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class PolicyRollbackGuardRead(BaseModel):
    guard_key: str
    enabled: bool
    bundle_key: str | None = None
    scope_key: str | None = None
    max_sla_breach_increase: float
    max_churn_increase: float
    min_rebalance_success_rate: float
    min_sample_size: float
    auto_rollback: bool
    reason_template: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RollbackGuardDecisionRead(BaseModel):
    bundle_key: str
    scope_key: str | None = None
    should_rollback: bool
    action: str
    reason_codes: list[str]
    reason: str | None = None
backend/app/schemas/policy_delivery_state.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class PolicyDeliveryStateRead(BaseModel):
    state_key: str
    bundle_key: str
    delivery_stage: str
    current_canary_release_id: str | None = None
    last_outcome_label: str | None = None
    last_guard_decision: str | None = None
    summary: str | None = None
    updated_at: datetime

    class Config:
        from_attributes = True
backend/app/services/policy_canary_release_service.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.policy_canary_release import PolicyCanaryRelease
from app.models.policy_delivery_state import PolicyDeliveryState
from app.repositories.policy_canary_release_repository import PolicyCanaryReleaseRepository
from app.repositories.policy_delivery_state_repository import PolicyDeliveryStateRepository


def _utcnow():
    return datetime.now(timezone.utc)


class PolicyCanaryReleaseService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PolicyCanaryReleaseRepository(db)
        self.state_repo = PolicyDeliveryStateRepository(db)

    def create_release(
        self,
        *,
        bundle_key: str,
        rollout_scope: str,
        scope_key: str | None,
        severity: str | None,
        shift_key: str | None,
        rollout_percent: float,
        cohort_size: int,
        auto_promote_enabled: bool,
        auto_rollback_enabled: bool,
        notes: str | None = None,
    ) -> PolicyCanaryRelease:
        release = PolicyCanaryRelease(
            id=str(uuid4()),
            bundle_key=bundle_key,
            rollout_scope=rollout_scope,
            scope_key=scope_key,
            severity=severity,
            shift_key=shift_key,
            rollout_percent=rollout_percent,
            cohort_size=cohort_size,
            status="active",
            auto_promote_enabled=auto_promote_enabled,
            auto_rollback_enabled=auto_rollback_enabled,
            notes=notes,
            started_at=_utcnow(),
        )
        self.repo.create(release)

        self.state_repo.upsert(
            PolicyDeliveryState(
                state_key=f"delivery:{bundle_key}",
                bundle_key=bundle_key,
                delivery_stage="canary",
                current_canary_release_id=release.id,
                summary=f"Canary active at {rollout_percent:.1f}% for scope={scope_key or 'global'}",
                updated_at=_utcnow(),
            )
        )
        return release

    def complete_release(self, release: PolicyCanaryRelease) -> PolicyCanaryRelease:
        release.status = "completed"
        release.ended_at = _utcnow()
        self.db.add(release)
        return release

    def mark_rolled_back(self, release: PolicyCanaryRelease) -> PolicyCanaryRelease:
        release.status = "rolled_back"
        release.ended_at = _utcnow()
        self.db.add(release)
        return release
backend/app/services/policy_realized_outcome_service.py
from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.policy_realized_outcome import PolicyRealizedOutcome
from app.repositories.policy_realized_outcome_repository import (
    PolicyRealizedOutcomeRepository,
)


class PolicyRealizedOutcomeService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PolicyRealizedOutcomeRepository(db)

    def classify_outcome(
        self,
        *,
        observed_sla_breach_rate: float,
        baseline_sla_breach_rate: float,
        observed_churn_rate: float,
        baseline_churn_rate: float,
    ) -> str:
        breach_delta = observed_sla_breach_rate - baseline_sla_breach_rate
        churn_delta = observed_churn_rate - baseline_churn_rate

        if breach_delta <= -0.02 and churn_delta <= 0.01:
            return "positive"
        if breach_delta >= 0.02 or churn_delta >= 0.02:
            return "negative"
        return "neutral"

    def record_outcome(
        self,
        *,
        bundle_key: str,
        canary_release_id: str | None,
        scope_key: str | None,
        severity: str | None,
        shift_key: str | None,
        observed_sla_breach_rate: float,
        observed_churn_rate: float,
        observed_rebalance_success_rate: float,
        observed_cost_delta: float,
        baseline_sla_breach_rate: float,
        baseline_churn_rate: float,
        baseline_rebalance_success_rate: float,
        sample_size: int,
    ) -> PolicyRealizedOutcome:
        label = self.classify_outcome(
            observed_sla_breach_rate=observed_sla_breach_rate,
            baseline_sla_breach_rate=baseline_sla_breach_rate,
            observed_churn_rate=observed_churn_rate,
            baseline_churn_rate=baseline_churn_rate,
        )

        summary = (
            f"outcome={label}, breach_delta={observed_sla_breach_rate - baseline_sla_breach_rate:.3f}, "
            f"churn_delta={observed_churn_rate - baseline_churn_rate:.3f}, "
            f"rebalance_success_delta={observed_rebalance_success_rate - baseline_rebalance_success_rate:.3f}"
        )

        model = PolicyRealizedOutcome(
            id=str(uuid4()),
            bundle_key=bundle_key,
            canary_release_id=canary_release_id,
            scope_key=scope_key,
            severity=severity,
            shift_key=shift_key,
            observed_sla_breach_rate=observed_sla_breach_rate,
            observed_churn_rate=observed_churn_rate,
            observed_rebalance_success_rate=observed_rebalance_success_rate,
            observed_cost_delta=observed_cost_delta,
            baseline_sla_breach_rate=baseline_sla_breach_rate,
            baseline_churn_rate=baseline_churn_rate,
            baseline_rebalance_success_rate=baseline_rebalance_success_rate,
            sample_size=sample_size,
            outcome_label=label,
            summary=summary,
        )
        return self.repo.create(model)
backend/app/services/policy_outcome_attribution_service.py
from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.policy_outcome_attribution import PolicyOutcomeAttribution
from app.repositories.policy_outcome_attribution_repository import (
    PolicyOutcomeAttributionRepository,
)


class PolicyOutcomeAttributionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PolicyOutcomeAttributionRepository(db)

    def build_attribution(
        self,
        *,
        bundle_key: str,
        policy_key: str | None,
        canary_release_id: str | None,
        attribution_scope: str,
        scope_key: str | None,
        positive_effect_score: float,
        negative_effect_score: float,
        impacted_case_count: int,
        rationale: str | None = None,
    ) -> PolicyOutcomeAttribution:
        net_effect_score = positive_effect_score - negative_effect_score

        label = "mixed"
        if net_effect_score >= 0.20:
            label = "winner"
        elif net_effect_score <= -0.20:
            label = "loser"

        model = PolicyOutcomeAttribution(
            id=str(uuid4()),
            bundle_key=bundle_key,
            policy_key=policy_key,
            canary_release_id=canary_release_id,
            attribution_scope=attribution_scope,
            scope_key=scope_key,
            positive_effect_score=positive_effect_score,
            negative_effect_score=negative_effect_score,
            net_effect_score=net_effect_score,
            impacted_case_count=impacted_case_count,
            attribution_label=label,
            rationale=rationale,
        )
        return self.repo.create(model)
backend/app/services/policy_rollback_guard_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.policy_rollback_guard_repository import (
    PolicyRollbackGuardRepository,
)
from app.schemas.policy_rollback_guard import RollbackGuardDecisionRead


class PolicyRollbackGuardService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PolicyRollbackGuardRepository(db)

    def evaluate(
        self,
        *,
        bundle_key: str,
        scope_key: str | None,
        observed_sla_breach_rate: float,
        baseline_sla_breach_rate: float,
        observed_churn_rate: float,
        baseline_churn_rate: float,
        observed_rebalance_success_rate: float,
        sample_size: int,
    ) -> RollbackGuardDecisionRead:
        guard = self.repo.find_best_match(bundle_key=bundle_key, scope_key=scope_key)
        if guard is None:
            return RollbackGuardDecisionRead(
                bundle_key=bundle_key,
                scope_key=scope_key,
                should_rollback=False,
                action="warn",
                reason_codes=["no_guard_found"],
                reason="No rollback guard matched.",
            )

        reasons: list[str] = []

        if sample_size < guard.min_sample_size:
            reasons.append("sample_size_too_low")

        if (observed_sla_breach_rate - baseline_sla_breach_rate) > guard.max_sla_breach_increase:
            reasons.append("sla_breach_increase_exceeded")

        if (observed_churn_rate - baseline_churn_rate) > guard.max_churn_increase:
            reasons.append("churn_increase_exceeded")

        if observed_rebalance_success_rate < guard.min_rebalance_success_rate:
            reasons.append("rebalance_success_below_floor")

        should_rollback = (
            guard.auto_rollback
            and "sample_size_too_low" not in reasons
            and any(
                code in reasons
                for code in [
                    "sla_breach_increase_exceeded",
                    "churn_increase_exceeded",
                    "rebalance_success_below_floor",
                ]
            )
        )

        action = "pass"
        if should_rollback:
            action = "rollback"
        elif reasons:
            action = "warn"

        return RollbackGuardDecisionRead(
            bundle_key=bundle_key,
            scope_key=scope_key,
            should_rollback=should_rollback,
            action=action,
            reason_codes=reasons if reasons else ["guard_pass"],
            reason=guard.reason_template,
        )
backend/app/services/policy_delivery_loop_service.py
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.policy_delivery_state import PolicyDeliveryState
from app.repositories.policy_bundle_repository import PolicyBundleRepository
from app.repositories.policy_delivery_state_repository import (
    PolicyDeliveryStateRepository,
)
from app.repositories.policy_canary_release_repository import (
    PolicyCanaryReleaseRepository,
)
from app.services.policy_bundle_lifecycle_service import PolicyBundleLifecycleService


def _utcnow():
    return datetime.now(timezone.utc)


class PolicyDeliveryLoopService:
    def __init__(self, db: Session):
        self.db = db
        self.state_repo = PolicyDeliveryStateRepository(db)
        self.bundle_repo = PolicyBundleRepository(db)
        self.release_repo = PolicyCanaryReleaseRepository(db)
        self.lifecycle = PolicyBundleLifecycleService(db)

    def mark_outcome(
        self,
        *,
        bundle_key: str,
        canary_release_id: str | None,
        outcome_label: str,
        guard_decision: str,
        summary: str | None = None,
    ) -> PolicyDeliveryState:
        delivery_stage = "canary"
        if guard_decision == "rollback":
            delivery_stage = "rollback"
        elif outcome_label == "positive" and guard_decision == "pass":
            delivery_stage = "promoted"

        state = PolicyDeliveryState(
            state_key=f"delivery:{bundle_key}",
            bundle_key=bundle_key,
            delivery_stage=delivery_stage,
            current_canary_release_id=canary_release_id,
            last_outcome_label=outcome_label,
            last_guard_decision=guard_decision,
            summary=summary,
            updated_at=_utcnow(),
        )
        return self.state_repo.upsert(state)

    def auto_rollback_if_needed(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        rollback_target_bundle_key: str | None = None,
    ):
        return self.lifecycle.rollback_bundle(
            bundle_key=bundle_key,
            actor_id=actor_id,
            rollback_target_bundle_key=rollback_target_bundle_key,
        )

    def auto_promote_if_safe(
        self,
        *,
        bundle_key: str,
        actor_id: str,
    ):
        return self.lifecycle.promote_bundle(
            bundle_key=bundle_key,
            actor_id=actor_id,
        )
3) BACKEND — PATCH CÁC FILE ĐANG CÓ
backend/app/models/policy_bundle.py — PATCH
Nếu chưa có, thêm:
from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column

canary_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
backend/app/repositories/policy_bundle_repository.py — PATCH
Trong upsert(...), thêm:
existing.canary_enabled = model.canary_enabled
Và create path giữ nguyên field này.
backend/app/services/policy_bundle_lifecycle_service.py — PATCH
Thêm event ghi nhận simulation/canary nếu muốn. Ví dụ helper:
def mark_simulated(self, *, bundle_key: str, actor_id: str, detail: str | None = None):
    bundle = self.bundle_repo.get(bundle_key)
    if bundle is None:
        raise ValueError("Policy bundle not found")
    bundle.status = "simulated"
    bundle.updated_at = _utcnow()
    self.db.add(bundle)
    self.event_repo.create(
        PolicyBundleEvent(
            id=str(uuid4()),
            bundle_key=bundle_key,
            event_type="simulated",
            actor_id=actor_id,
            detail=detail,
        )
    )
    return bundle
backend/app/services/rebalance_policy_engine.py — PATCH
Nếu muốn canary-aware evaluation, thêm logic lọc bundle active/canary:
active_bundle = self.bundle_repo.get_active_bundle()
if policy and active_bundle and getattr(policy, "bundle_key", None):
    if policy.bundle_key != active_bundle.bundle_key:
        # canary bundle handling should be mapped by rollout targeting layer
        return RebalancePolicyDecision(
            allowed=False,
            auto_apply=False,
            requires_human_approval=True,
            policy_key=policy.policy_key,
            reason_codes=["policy_not_in_active_delivery_path"],
        )
Trong repo thật, đoạn này nên được thay bằng canary targeting resolver theo queue/severity/shift/cohort.
4) BACKEND — ROUTES
backend/app/api/routes/policy_delivery.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.policy_canary_release_repository import (
    PolicyCanaryReleaseRepository,
)
from app.repositories.policy_delivery_state_repository import (
    PolicyDeliveryStateRepository,
)
from app.repositories.policy_outcome_attribution_repository import (
    PolicyOutcomeAttributionRepository,
)
from app.repositories.policy_realized_outcome_repository import (
    PolicyRealizedOutcomeRepository,
)
from app.repositories.policy_rollback_guard_repository import (
    PolicyRollbackGuardRepository,
)
from app.schemas.policy_canary_release import (
    CreateCanaryReleaseRequest,
    PolicyCanaryReleaseRead,
)
from app.schemas.policy_delivery_state import PolicyDeliveryStateRead
from app.schemas.policy_outcome_attribution import PolicyOutcomeAttributionRead
from app.schemas.policy_realized_outcome import PolicyRealizedOutcomeRead
from app.schemas.policy_rollback_guard import (
    PolicyRollbackGuardRead,
    RollbackGuardDecisionRead,
)
from app.services.policy_canary_release_service import PolicyCanaryReleaseService
from app.services.policy_rollback_guard_service import PolicyRollbackGuardService

router = APIRouter(prefix="/policy-delivery", tags=["policy-delivery"])


@router.get("/canary-releases", response_model=list[PolicyCanaryReleaseRead])
def list_canary_releases(bundle_key: str | None = None, db: Session = Depends(get_db)):
    repo = PolicyCanaryReleaseRepository(db)
    return repo.list_latest(bundle_key=bundle_key)


@router.post("/canary-releases", response_model=PolicyCanaryReleaseRead)
def create_canary_release(
    payload: CreateCanaryReleaseRequest,
    db: Session = Depends(get_db),
):
    svc = PolicyCanaryReleaseService(db)
    release = svc.create_release(
        bundle_key=payload.bundle_key,
        rollout_scope=payload.rollout_scope,
        scope_key=payload.scope_key,
        severity=payload.severity,
        shift_key=payload.shift_key,
        rollout_percent=payload.rollout_percent,
        cohort_size=payload.cohort_size,
        auto_promote_enabled=payload.auto_promote_enabled,
        auto_rollback_enabled=payload.auto_rollback_enabled,
        notes=payload.notes,
    )
    db.commit()
    db.refresh(release)
    return release


@router.get("/realized-outcomes", response_model=list[PolicyRealizedOutcomeRead])
def list_realized_outcomes(bundle_key: str | None = None, db: Session = Depends(get_db)):
    repo = PolicyRealizedOutcomeRepository(db)
    return repo.list_latest(bundle_key=bundle_key)


@router.get("/outcome-attributions", response_model=list[PolicyOutcomeAttributionRead])
def list_outcome_attributions(bundle_key: str | None = None, db: Session = Depends(get_db)):
    repo = PolicyOutcomeAttributionRepository(db)
    return repo.list_latest(bundle_key=bundle_key)


@router.get("/rollback-guards", response_model=list[PolicyRollbackGuardRead])
def list_rollback_guards(db: Session = Depends(get_db)):
    repo = PolicyRollbackGuardRepository(db)
    return repo.list_all()


@router.get("/rollback-guards/evaluate", response_model=RollbackGuardDecisionRead)
def evaluate_rollback_guard(
    bundle_key: str,
    scope_key: str | None,
    observed_sla_breach_rate: float,
    baseline_sla_breach_rate: float,
    observed_churn_rate: float,
    baseline_churn_rate: float,
    observed_rebalance_success_rate: float,
    sample_size: int,
    db: Session = Depends(get_db),
):
    svc = PolicyRollbackGuardService(db)
    return svc.evaluate(
        bundle_key=bundle_key,
        scope_key=scope_key,
        observed_sla_breach_rate=observed_sla_breach_rate,
        baseline_sla_breach_rate=baseline_sla_breach_rate,
        observed_churn_rate=observed_churn_rate,
        baseline_churn_rate=baseline_churn_rate,
        observed_rebalance_success_rate=observed_rebalance_success_rate,
        sample_size=sample_size,
    )


@router.get("/delivery-states", response_model=list[PolicyDeliveryStateRead])
def list_delivery_states(db: Session = Depends(get_db)):
    repo = PolicyDeliveryStateRepository(db)
    return repo.list_all()
backend/app/api/api_v1/api.py — PATCH
Thêm import:
from app.api.routes import policy_delivery
Và include:
api_router.include_router(policy_delivery.router)
5) BACKEND — MIGRATION
backend/alembic/versions/phase3_canary_outcome_rollback_guard.py
from alembic import op
import sqlalchemy as sa


revision = "phase3_canary_outcome_rollback_guard"
down_revision = "phase3_policy_simulation_autotuning_optimizer"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "policy_canary_release",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("bundle_key", sa.String(length=128), nullable=False),
        sa.Column("rollout_scope", sa.String(length=64), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("shift_key", sa.String(length=64), nullable=True),
        sa.Column("rollout_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cohort_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="scheduled"),
        sa.Column("auto_promote_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_rollback_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_canary_release_bundle_key", "policy_canary_release", ["bundle_key"])
    op.create_index("ix_policy_canary_release_scope_key", "policy_canary_release", ["scope_key"])
    op.create_index("ix_policy_canary_release_severity", "policy_canary_release", ["severity"])
    op.create_index("ix_policy_canary_release_shift_key", "policy_canary_release", ["shift_key"])

    op.create_table(
        "policy_realized_outcome",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("bundle_key", sa.String(length=128), nullable=False),
        sa.Column("canary_release_id", sa.String(length=64), nullable=True),
        sa.Column("scope_key", sa.String(length=128), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("shift_key", sa.String(length=64), nullable=True),
        sa.Column("observed_sla_breach_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("observed_churn_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("observed_rebalance_success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("observed_cost_delta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("baseline_sla_breach_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("baseline_churn_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("baseline_rebalance_success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outcome_label", sa.String(length=32), nullable=False, server_default="neutral"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_realized_outcome_bundle_key", "policy_realized_outcome", ["bundle_key"])
    op.create_index("ix_policy_realized_outcome_canary_release_id", "policy_realized_outcome", ["canary_release_id"])
    op.create_index("ix_policy_realized_outcome_scope_key", "policy_realized_outcome", ["scope_key"])
    op.create_index("ix_policy_realized_outcome_severity", "policy_realized_outcome", ["severity"])
    op.create_index("ix_policy_realized_outcome_shift_key", "policy_realized_outcome", ["shift_key"])

    op.create_table(
        "policy_outcome_attribution",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("bundle_key", sa.String(length=128), nullable=False),
        sa.Column("policy_key", sa.String(length=128), nullable=True),
        sa.Column("canary_release_id", sa.String(length=64), nullable=True),
        sa.Column("attribution_scope", sa.String(length=64), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=True),
        sa.Column("positive_effect_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("negative_effect_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("net_effect_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("impacted_case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attribution_label", sa.String(length=32), nullable=False, server_default="mixed"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_outcome_attribution_bundle_key", "policy_outcome_attribution", ["bundle_key"])
    op.create_index("ix_policy_outcome_attribution_policy_key", "policy_outcome_attribution", ["policy_key"])
    op.create_index("ix_policy_outcome_attribution_canary_release_id", "policy_outcome_attribution", ["canary_release_id"])

    op.create_table(
        "policy_rollback_guard",
        sa.Column("guard_key", sa.String(length=128), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("bundle_key", sa.String(length=128), nullable=True),
        sa.Column("scope_key", sa.String(length=128), nullable=True),
        sa.Column("max_sla_breach_increase", sa.Float(), nullable=False, server_default="0.03"),
        sa.Column("max_churn_increase", sa.Float(), nullable=False, server_default="0.02"),
        sa.Column("min_rebalance_success_rate", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("min_sample_size", sa.Float(), nullable=False, server_default="20"),
        sa.Column("auto_rollback", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reason_template", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_rollback_guard_bundle_key", "policy_rollback_guard", ["bundle_key"])
    op.create_index("ix_policy_rollback_guard_scope_key", "policy_rollback_guard", ["scope_key"])

    op.create_table(
        "policy_delivery_state",
        sa.Column("state_key", sa.String(length=128), primary_key=True),
        sa.Column("bundle_key", sa.String(length=128), nullable=False),
        sa.Column("delivery_stage", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("current_canary_release_id", sa.String(length=64), nullable=True),
        sa.Column("last_outcome_label", sa.String(length=32), nullable=True),
        sa.Column("last_guard_decision", sa.String(length=32), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_delivery_state_bundle_key", "policy_delivery_state", ["bundle_key"])
    op.create_index("ix_policy_delivery_state_current_canary_release_id", "policy_delivery_state", ["current_canary_release_id"])

    # Optional patch if existing table lacks canary flag
    # op.add_column("policy_bundle", sa.Column("canary_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
def downgrade():
    op.drop_index("ix_policy_delivery_state_current_canary_release_id", table_name="policy_delivery_state")
    op.drop_index("ix_policy_delivery_state_bundle_key", table_name="policy_delivery_state")
    op.drop_table("policy_delivery_state")

    op.drop_index("ix_policy_rollback_guard_scope_key", table_name="policy_rollback_guard")
    op.drop_index("ix_policy_rollback_guard_bundle_key", table_name="policy_rollback_guard")
    op.drop_table("policy_rollback_guard")

    op.drop_index("ix_policy_outcome_attribution_canary_release_id", table_name="policy_outcome_attribution")
    op.drop_index("ix_policy_outcome_attribution_policy_key", table_name="policy_outcome_attribution")
    op.drop_index("ix_policy_outcome_attribution_bundle_key", table_name="policy_outcome_attribution")
    op.drop_table("policy_outcome_attribution")

    op.drop_index("ix_policy_realized_outcome_shift_key", table_name="policy_realized_outcome")
    op.drop_index("ix_policy_realized_outcome_severity", table_name="policy_realized_outcome")
    op.drop_index("ix_policy_realized_outcome_scope_key", table_name="policy_realized_outcome")
    op.drop_index("ix_policy_realized_outcome_canary_release_id", table_name="policy_realized_outcome")
    op.drop_index("ix_policy_realized_outcome_bundle_key", table_name="policy_realized_outcome")
    op.drop_table("policy_realized_outcome")

    op.drop_index("ix_policy_canary_release_shift_key", table_name="policy_canary_release")
    op.drop_index("ix_policy_canary_release_severity", table_name="policy_canary_release")
    op.drop_index("ix_policy_canary_release_scope_key", table_name="policy_canary_release")
    op.drop_index("ix_policy_canary_release_bundle_key", table_name="policy_canary_release")
    op.drop_table("policy_canary_release")
6) BACKEND — WORKER
backend/app/workers/policy_delivery_worker.py
from __future__ import annotations

from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.policy_rollback_guard import PolicyRollbackGuard
from app.repositories.policy_canary_release_repository import (
    PolicyCanaryReleaseRepository,
)
from app.repositories.policy_delivery_state_repository import (
    PolicyDeliveryStateRepository,
)
from app.repositories.policy_rollback_guard_repository import (
    PolicyRollbackGuardRepository,
)
from app.services.policy_canary_release_service import PolicyCanaryReleaseService
from app.services.policy_delivery_loop_service import PolicyDeliveryLoopService
from app.services.policy_outcome_attribution_service import (
    PolicyOutcomeAttributionService,
)
from app.services.policy_realized_outcome_service import PolicyRealizedOutcomeService
from app.services.policy_rollback_guard_service import PolicyRollbackGuardService


def _utcnow():
    return datetime.now(timezone.utc)


@celery_app.task(name="policy_delivery.refresh")
def refresh_policy_delivery():
    db = SessionLocal()
    try:
        guard_repo = PolicyRollbackGuardRepository(db)
        release_service = PolicyCanaryReleaseService(db)
        outcome_service = PolicyRealizedOutcomeService(db)
        attribution_service = PolicyOutcomeAttributionService(db)
        guard_service = PolicyRollbackGuardService(db)
        delivery_loop = PolicyDeliveryLoopService(db)
        release_repo = PolicyCanaryReleaseRepository(db)

        guard_repo.upsert(
            PolicyRollbackGuard(
                guard_key="bundle_human_review_v2_default",
                enabled=True,
                bundle_key="bundle_human_review_v2",
                scope_key="human_review",
                max_sla_breach_increase=0.02,
                max_churn_increase=0.015,
                min_rebalance_success_rate=0.60,
                min_sample_size=25,
                auto_rollback=True,
                reason_template="Rollback when canary materially worsens SLA/churn or fails rebalance floor.",
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
        )

        release = release_service.create_release(
            bundle_key="bundle_human_review_v2",
            rollout_scope="queue",
            scope_key="human_review",
            severity="high",
            shift_key="night",
            rollout_percent=20.0,
            cohort_size=40,
            auto_promote_enabled=False,
            auto_rollback_enabled=True,
            notes="Night shift high severity canary",
        )

        outcome = outcome_service.record_outcome(
            bundle_key="bundle_human_review_v2",
            canary_release_id=release.id,
            scope_key="human_review",
            severity="high",
            shift_key="night",
            observed_sla_breach_rate=0.16,
            observed_churn_rate=0.03,
            observed_rebalance_success_rate=0.58,
            observed_cost_delta=140.0,
            baseline_sla_breach_rate=0.12,
            baseline_churn_rate=0.015,
            baseline_rebalance_success_rate=0.74,
            sample_size=38,
        )

        attribution_service.build_attribution(
            bundle_key="bundle_human_review_v2",
            policy_key="human_review_high_v2",
            canary_release_id=release.id,
            attribution_scope="queue",
            scope_key="human_review",
            positive_effect_score=0.10,
            negative_effect_score=0.42,
            impacted_case_count=38,
            rationale="Observed worse SLA and lower rebalance success in the canary cohort.",
        )

        guard_decision = guard_service.evaluate(
            bundle_key="bundle_human_review_v2",
            scope_key="human_review",
            observed_sla_breach_rate=outcome.observed_sla_breach_rate,
            baseline_sla_breach_rate=outcome.baseline_sla_breach_rate,
            observed_churn_rate=outcome.observed_churn_rate,
            baseline_churn_rate=outcome.baseline_churn_rate,
            observed_rebalance_success_rate=outcome.observed_rebalance_success_rate,
            sample_size=outcome.sample_size,
        )

        delivery_loop.mark_outcome(
            bundle_key="bundle_human_review_v2",
            canary_release_id=release.id,
            outcome_label=outcome.outcome_label,
            guard_decision=guard_decision.action,
            summary=outcome.summary,
        )

        if guard_decision.should_rollback:
            release_service.mark_rolled_back(release)
            delivery_loop.auto_rollback_if_needed(
                bundle_key="bundle_human_review_v2",
                actor_id="system_auto_guard",
                rollback_target_bundle_key=None,
            )
        else:
            release_service.complete_release(release)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
7) BACKEND — TESTS
backend/tests/services/test_policy_realized_outcome_service.py
from app.services.policy_realized_outcome_service import PolicyRealizedOutcomeService


def test_realized_outcome_classifies_negative_when_breach_and_churn_worsen(db_session):
    svc = PolicyRealizedOutcomeService(db_session)

    row = svc.record_outcome(
        bundle_key="bundle_1",
        canary_release_id="rel_1",
        scope_key="human_review",
        severity="high",
        shift_key="night",
        observed_sla_breach_rate=0.18,
        observed_churn_rate=0.04,
        observed_rebalance_success_rate=0.55,
        observed_cost_delta=100.0,
        baseline_sla_breach_rate=0.12,
        baseline_churn_rate=0.01,
        baseline_rebalance_success_rate=0.70,
        sample_size=30,
    )

    assert row.outcome_label == "negative"
backend/tests/services/test_policy_outcome_attribution_service.py
from app.services.policy_outcome_attribution_service import (
    PolicyOutcomeAttributionService,
)


def test_outcome_attribution_labels_loser_when_negative_dominates(db_session):
    svc = PolicyOutcomeAttributionService(db_session)

    row = svc.build_attribution(
        bundle_key="bundle_1",
        policy_key="policy_1",
        canary_release_id="rel_1",
        attribution_scope="queue",
        scope_key="human_review",
        positive_effect_score=0.10,
        negative_effect_score=0.45,
        impacted_case_count=40,
        rationale="More harm than gain.",
    )

    assert row.attribution_label == "loser"
backend/tests/services/test_policy_rollback_guard_service.py
from datetime import datetime

from app.models.policy_rollback_guard import PolicyRollbackGuard
from app.repositories.policy_rollback_guard_repository import (
    PolicyRollbackGuardRepository,
)
from app.services.policy_rollback_guard_service import PolicyRollbackGuardService


def test_rollback_guard_triggers_rollback_when_thresholds_exceeded(db_session):
    repo = PolicyRollbackGuardRepository(db_session)
    repo.upsert(
        PolicyRollbackGuard(
            guard_key="g1",
            enabled=True,
            bundle_key="bundle_1",
            scope_key="human_review",
            max_sla_breach_increase=0.02,
            max_churn_increase=0.01,
            min_rebalance_success_rate=0.60,
            min_sample_size=20,
            auto_rollback=True,
            reason_template="Rollback template",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )

    svc = PolicyRollbackGuardService(db_session)
    decision = svc.evaluate(
        bundle_key="bundle_1",
        scope_key="human_review",
        observed_sla_breach_rate=0.18,
        baseline_sla_breach_rate=0.12,
        observed_churn_rate=0.03,
        baseline_churn_rate=0.01,
        observed_rebalance_success_rate=0.50,
        sample_size=35,
    )

    assert decision.should_rollback is True
    assert decision.action == "rollback"
backend/tests/services/test_policy_canary_release_service.py
from app.services.policy_canary_release_service import PolicyCanaryReleaseService


def test_canary_release_creation_updates_delivery_state(db_session):
    svc = PolicyCanaryReleaseService(db_session)

    release = svc.create_release(
        bundle_key="bundle_1",
        rollout_scope="queue",
        scope_key="human_review",
        severity="high",
        shift_key="night",
        rollout_percent=20.0,
        cohort_size=40,
        auto_promote_enabled=False,
        auto_rollback_enabled=True,
        notes="test release",
    )

    assert release.status == "active"
    assert release.bundle_key == "bundle_1"
8) FRONTEND — FULL FILES
frontend/src/types/policyDelivery.ts
export type PolicyCanaryRelease = {
  id: string;
  bundle_key: string;
  rollout_scope: string;
  scope_key?: string | null;
  severity?: string | null;
  shift_key?: string | null;
  rollout_percent: number;
  cohort_size: number;
  status: string;
  auto_promote_enabled: boolean;
  auto_rollback_enabled: boolean;
  notes?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  created_at: string;
};

export type PolicyRealizedOutcome = {
  id: string;
  bundle_key: string;
  canary_release_id?: string | null;
  scope_key?: string | null;
  severity?: string | null;
  shift_key?: string | null;
  observed_sla_breach_rate: number;
  observed_churn_rate: number;
  observed_rebalance_success_rate: number;
  observed_cost_delta: number;
  baseline_sla_breach_rate: number;
  baseline_churn_rate: number;
  baseline_rebalance_success_rate: number;
  sample_size: number;
  outcome_label: string;
  summary?: string | null;
  observed_at: string;
};

export type PolicyOutcomeAttribution = {
  id: string;
  bundle_key: string;
  policy_key?: string | null;
  canary_release_id?: string | null;
  attribution_scope: string;
  scope_key?: string | null;
  positive_effect_score: number;
  negative_effect_score: number;
  net_effect_score: number;
  impacted_case_count: number;
  attribution_label: string;
  rationale?: string | null;
  created_at: string;
};

export type PolicyRollbackGuard = {
  guard_key: string;
  enabled: boolean;
  bundle_key?: string | null;
  scope_key?: string | null;
  max_sla_breach_increase: number;
  max_churn_increase: number;
  min_rebalance_success_rate: number;
  min_sample_size: number;
  auto_rollback: boolean;
  reason_template?: string | null;
  created_at: string;
  updated_at: string;
};

export type RollbackGuardDecision = {
  bundle_key: string;
  scope_key?: string | null;
  should_rollback: boolean;
  action: string;
  reason_codes: string[];
  reason?: string | null;
};

export type PolicyDeliveryState = {
  state_key: string;
  bundle_key: string;
  delivery_stage: string;
  current_canary_release_id?: string | null;
  last_outcome_label?: string | null;
  last_guard_decision?: string | null;
  summary?: string | null;
  updated_at: string;
};
frontend/src/api/policyDelivery.ts
import { api } from "./client";
import {
  PolicyCanaryRelease,
  PolicyDeliveryState,
  PolicyOutcomeAttribution,
  PolicyRealizedOutcome,
  PolicyRollbackGuard,
  RollbackGuardDecision,
} from "../types/policyDelivery";

export async function fetchCanaryReleases(bundleKey?: string): Promise<PolicyCanaryRelease[]> {
  const res = await api.get("/policy-delivery/canary-releases", {
    params: bundleKey ? { bundle_key: bundleKey } : {},
  });
  return res.data;
}

export async function createCanaryRelease(payload: {
  bundle_key: string;
  rollout_scope?: string;
  scope_key?: string;
  severity?: string;
  shift_key?: string;
  rollout_percent: number;
  cohort_size?: number;
  auto_promote_enabled?: boolean;
  auto_rollback_enabled?: boolean;
  notes?: string;
}): Promise<PolicyCanaryRelease> {
  const res = await api.post("/policy-delivery/canary-releases", payload);
  return res.data;
}

export async function fetchRealizedOutcomes(bundleKey?: string): Promise<PolicyRealizedOutcome[]> {
  const res = await api.get("/policy-delivery/realized-outcomes", {
    params: bundleKey ? { bundle_key: bundleKey } : {},
  });
  return res.data;
}

export async function fetchOutcomeAttributions(bundleKey?: string): Promise<PolicyOutcomeAttribution[]> {
  const res = await api.get("/policy-delivery/outcome-attributions", {
    params: bundleKey ? { bundle_key: bundleKey } : {},
  });
  return res.data;
}

export async function fetchRollbackGuards(): Promise<PolicyRollbackGuard[]> {
  const res = await api.get("/policy-delivery/rollback-guards");
  return res.data;
}

export async function evaluateRollbackGuard(params: {
  bundle_key: string;
  scope_key?: string;
  observed_sla_breach_rate: number;
  baseline_sla_breach_rate: number;
  observed_churn_rate: number;
  baseline_churn_rate: number;
  observed_rebalance_success_rate: number;
  sample_size: number;
}): Promise<RollbackGuardDecision> {
  const res = await api.get("/policy-delivery/rollback-guards/evaluate", {
    params,
  });
  return res.data;
}

export async function fetchDeliveryStates(): Promise<PolicyDeliveryState[]> {
  const res = await api.get("/policy-delivery/delivery-states");
  return res.data;
}
frontend/src/components/review/PolicyCanaryReleasePanel.tsx
import React, { useEffect, useState } from "react";
import { createCanaryRelease, fetchCanaryReleases } from "../../api/policyDelivery";
import { PolicyCanaryRelease } from "../../types/policyDelivery";

export function PolicyCanaryReleasePanel() {
  const [rows, setRows] = useState<PolicyCanaryRelease[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setRows(await fetchCanaryReleases());
    } finally {
      setLoading(false);
    }
  }

  async function onCreateSample() {
    await createCanaryRelease({
      bundle_key: "bundle_human_review_v2",
      rollout_scope: "queue",
      scope_key: "human_review",
      severity: "high",
      shift_key: "night",
      rollout_percent: 20,
      cohort_size: 40,
      auto_promote_enabled: false,
      auto_rollback_enabled: true,
      notes: "UI-created sample canary",
    });
    await load();
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Canary Policy Release</h3>
        <div className="flex gap-2">
          <button className="rounded border px-3 py-1 text-sm" onClick={() => void onCreateSample()}>
            Create Sample Canary
          </button>
          <button className="rounded border px-3 py-1 text-sm" onClick={() => void load()} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      {rows.map((row) => (
        <div key={row.id} className="rounded border p-3">
          <div className="font-medium">{row.bundle_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            Scope: {row.rollout_scope} / {row.scope_key ?? "global"} / {row.shift_key ?? "all shifts"}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Severity: {row.severity ?? "all"} · Rollout: {row.rollout_percent}% · Cohort: {row.cohort_size}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Status: {row.status} · Auto rollback: {row.auto_rollback_enabled ? "yes" : "no"}
          </div>
          <div className="mt-1 text-xs text-gray-500">{row.notes ?? "No notes."}</div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No canary releases.</div> : null}
    </div>
  );
}
frontend/src/components/review/PolicyRealizedOutcomePanel.tsx
import React, { useEffect, useState } from "react";
import { fetchRealizedOutcomes } from "../../api/policyDelivery";
import { PolicyRealizedOutcome } from "../../types/policyDelivery";

type Props = {
  bundleKey?: string;
};

export function PolicyRealizedOutcomePanel({ bundleKey }: Props) {
  const [rows, setRows] = useState<PolicyRealizedOutcome[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load(bundleKey);
  }, [bundleKey]);

  async function load(nextBundleKey?: string) {
    setLoading(true);
    try {
      setRows(await fetchRealizedOutcomes(nextBundleKey));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Realized Policy Outcomes</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load(bundleKey)} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.id} className="rounded border p-3">
          <div className="font-medium">{row.bundle_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            Outcome: {row.outcome_label} · Sample: {row.sample_size}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            SLA breach: {(row.baseline_sla_breach_rate * 100).toFixed(1)}% → {(row.observed_sla_breach_rate * 100).toFixed(1)}%
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Churn: {(row.baseline_churn_rate * 100).toFixed(1)}% → {(row.observed_churn_rate * 100).toFixed(1)}%
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Rebalance success: {(row.baseline_rebalance_success_rate * 100).toFixed(1)}% → {(row.observed_rebalance_success_rate * 100).toFixed(1)}%
          </div>
          <div className="mt-1 text-xs text-gray-500">{row.summary ?? "No summary."}</div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No realized outcomes.</div> : null}
    </div>
  );
}
frontend/src/components/review/PolicyOutcomeAttributionPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchOutcomeAttributions } from "../../api/policyDelivery";
import { PolicyOutcomeAttribution } from "../../types/policyDelivery";

type Props = {
  bundleKey?: string;
};

export function PolicyOutcomeAttributionPanel({ bundleKey }: Props) {
  const [rows, setRows] = useState<PolicyOutcomeAttribution[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load(bundleKey);
  }, [bundleKey]);

  async function load(nextBundleKey?: string) {
    setLoading(true);
    try {
      setRows(await fetchOutcomeAttributions(nextBundleKey));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Outcome Attribution</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load(bundleKey)} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.id} className="rounded border p-3">
          <div className="font-medium">{row.bundle_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            Policy: {row.policy_key ?? "bundle-level"} · Label: {row.attribution_label}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Positive: {row.positive_effect_score.toFixed(2)} · Negative: {row.negative_effect_score.toFixed(2)} · Net: {row.net_effect_score.toFixed(2)}
          </div>
          <div className="mt-1 text-xs text-gray-500">
            Impacted cases: {row.impacted_case_count} · {row.rationale ?? "No rationale."}
          </div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No outcome attribution data.</div> : null}
    </div>
  );
}
frontend/src/components/review/PolicyRollbackGuardPanel.tsx
import React, { useEffect, useState } from "react";
import { fetchRollbackGuards } from "../../api/policyDelivery";
import { PolicyRollbackGuard } from "../../types/policyDelivery";

export function PolicyRollbackGuardPanel() {
  const [rows, setRows] = useState<PolicyRollbackGuard[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setRows(await fetchRollbackGuards());
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Auto-Rollback Guards</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.guard_key} className="rounded border p-3">
          <div className="font-medium">{row.guard_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            Bundle: {row.bundle_key ?? "global"} · Scope: {row.scope_key ?? "all"}
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Max SLA increase: {(row.max_sla_breach_increase * 100).toFixed(1)}% · Max churn increase: {(row.max_churn_increase * 100).toFixed(1)}%
          </div>
          <div className="mt-1 text-sm text-gray-600">
            Min rebalance success: {(row.min_rebalance_success_rate * 100).toFixed(1)}% · Min sample: {row.min_sample_size}
          </div>
          <div className="mt-1 text-xs text-gray-500">{row.reason_template ?? "No reason template."}</div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No rollback guards.</div> : null}
    </div>
  );
}
frontend/src/components/review/PolicyDeliveryStatePanel.tsx
import React, { useEffect, useState } from "react";
import { fetchDeliveryStates } from "../../api/policyDelivery";
import { PolicyDeliveryState } from "../../types/policyDelivery";

export function PolicyDeliveryStatePanel() {
  const [rows, setRows] = useState<PolicyDeliveryState[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setRows(await fetchDeliveryStates());
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Policy Delivery State</h3>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      {rows.map((row) => (
        <div key={row.state_key} className="rounded border p-3">
          <div className="font-medium">{row.bundle_key}</div>
          <div className="mt-1 text-sm text-gray-600">
            Stage: {row.delivery_stage} · Last outcome: {row.last_outcome_label ?? "n/a"} · Guard: {row.last_guard_decision ?? "n/a"}
          </div>
          <div className="mt-1 text-xs text-gray-500">{row.summary ?? "No summary."}</div>
        </div>
      ))}

      {!rows.length && !loading ? <div className="text-sm text-gray-500">No delivery state data.</div> : null}
    </div>
  );
}
9) FRONTEND — PATCH CÁC FILE ĐANG CÓ
frontend/src/components/review/ReviewDecisionPanel.tsx — PATCH
Thêm imports:
import { PolicyCanaryReleasePanel } from "./PolicyCanaryReleasePanel";
import { PolicyRealizedOutcomePanel } from "./PolicyRealizedOutcomePanel";
import { PolicyOutcomeAttributionPanel } from "./PolicyOutcomeAttributionPanel";
import { PolicyRollbackGuardPanel } from "./PolicyRollbackGuardPanel";
import { PolicyDeliveryStatePanel } from "./PolicyDeliveryStatePanel";
Trong JSX thêm:
<PolicyCanaryReleasePanel />
<PolicyRealizedOutcomePanel />
<PolicyOutcomeAttributionPanel />
<PolicyRollbackGuardPanel />
<PolicyDeliveryStatePanel />
frontend/src/components/review/PolicyBundlePanel.tsx — PATCH
Nếu muốn canary-aware status note, thêm:
<div className="mt-1 text-xs text-gray-500">
  Promote should normally follow successful simulation and healthy canary outcomes.
</div>
frontend/src/components/review/PolicySimulationPanel.tsx — PATCH
Thêm note bridge sang realized outcomes:
<div className="text-xs text-gray-500">
  Simulation is projected behavior; compare with realized outcomes after canary release before promoting globally.
</div>
10) ĐIỂM MAP QUAN TRỌNG KHI DÁN VÀO REPO THẬT
A. Canary targeting
Hiện PolicyCanaryReleaseService mới lưu metadata rollout. Repo thật cần thêm lớp chọn cohort thật theo:
queue
severity
shift
project
reviewer/review-case hash buckets
Ví dụ rollout 20% có thể map bằng hashing review_case_id.
B. Realized outcomes
PolicyRealizedOutcomeService hiện nhận số liệu đầu vào trực tiếp. Repo thật cần aggregate từ:
actual SLA breach metrics
actual churn / rework / conflict
actual rebalance success
actual staffing or execution cost
C. Outcome attribution
PolicyOutcomeAttributionService đang nhận positive/negative scores như input. Repo thật nên tính từ:
delta vs control cohort
delta vs pre-rollout baseline
diff-in-diff nếu có multi-cohort setup
D. Auto rollback
PolicyRollbackGuardService hiện quyết định rollback ở mức guard logic. Repo thật nên map thêm:
rollback to prior active bundle
mark canary release rolled_back
emit alert / audit event / notification
freeze auto-promote for that bundle
E. Delivery loop
PolicyDeliveryLoopService là khung orchestration. Repo thật nên nối nó với:
canary scheduler
metrics ingestion
alerting
bundle lifecycle events
operator approvals if rollback is not fully automatic
11) KẾT QUẢ SAU PATCH NÀY
Sau phase này, hệ của bạn đã đi từ:
simulation-backed, safely tuned, cost-aware governance optimization
sang:
closed-loop policy delivery system
Cụ thể hệ đã có:
A. Canary policy release
Không cần promote toàn hệ ngay. Có thể rollout theo queue / severity / shift.
B. Realized outcome attribution
Không còn chỉ dự báo. Hệ đo được outcome thật sau rollout.
C. Policy winner / loser detection
Biết policy nào thực sự tạo lợi ích, policy nào gây hại.
D. Auto-rollback guard
Nếu rollout làm xấu SLA/churn hoặc hỏng rebalance success, hệ có thể rollback.
E. Delivery state machine
Bundle policy giờ có lifecycle thực: simulated → canary → promoted / rollback.
PHASE 3 — POLICY EXPERIMENTATION PLATFORM + MULTI-ARM BANDIT ROLLOUT + CROSS-BUNDLE LEARNING MEMORY theo đúng kiểu full code file-by-file paste-ready.
Mình giữ định hướng:
không tái cấu trúc vô cớ
bám style monorepo backend hiện có
tương thích với các phase trước:
policy bundle lifecycle
canary release
realized outcomes
rollback guard
thêm lớp:
experiment
variant allocation
bandit learning
cross-bundle memory
1) KIẾN TRÚC NGẮN GỌN CỦA PHASE NÀY
Hệ sẽ có thêm 5 lớp chính:
PolicyExperiment
định nghĩa một thí nghiệm rollout
gắn nhiều arm/policy bundle variant
PolicyExperimentArm
mỗi arm là một bundle variant
có traffic weight, prior, posterior, status
PolicyExperimentExposure
ghi nhận mỗi lần một review-case / work-item được gán vào arm nào
PolicyOutcomeObservation
ghi realized outcome thật cho exposure đó
PolicyLearningMemory
lưu memory thắng/thua theo context để dùng lại cross-bundle
Bandit allocator:
nhận context
chọn arm
ghi exposure
sau đó khi outcome về:
update posterior
update arm score
update cross-bundle learning memory
2) GIẢ ĐỊNH MAP NHANH KHI DÁN VÀO REPO THẬT
Mình giả định repo thật đã có:
Base
TimestampMixin hoặc equivalent
SessionLocal
FastAPI APIRouter
repo pattern tương tự phase governance trước
policy bundle model đã tồn tại, ví dụ PolicyBundle
actor header auth hoặc RBAC đã có sẵn
Nếu tên khác thì map lại import.
3) FILE-BY-FILE
backend/app/models/policy_experiment.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyExperimentStatus(str, enum.Enum):
    draft = "draft"
    running = "running"
    paused = "paused"
    completed = "completed"
    canceled = "canceled"


class PolicyExperimentObjective(str, enum.Enum):
    maximize_net_benefit = "maximize_net_benefit"
    minimize_sla_breach = "minimize_sla_breach"
    maximize_rebalance_success = "maximize_rebalance_success"
    minimize_churn_rework = "minimize_churn_rework"
    minimize_cost = "minimize_cost"


class PolicyExperiment(Base):
    __tablename__ = "policy_experiment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_key = Column(String(255), unique=True, nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(Enum(PolicyExperimentStatus), nullable=False, default=PolicyExperimentStatus.draft)
    objective = Column(Enum(PolicyExperimentObjective), nullable=False, default=PolicyExperimentObjective.maximize_net_benefit)

    targeting_filters = Column(JSON, nullable=False, default=dict)
    allocation_strategy = Column(String(64), nullable=False, default="thompson_sampling")
    control_arm_key = Column(String(255), nullable=True)

    min_sample_size_per_arm = Column(Integer, nullable=False, default=50)
    confidence_threshold = Column(Integer, nullable=False, default=95)
    auto_promote_enabled = Column(Boolean, nullable=False, default=False)
    auto_pause_on_regression = Column(Boolean, nullable=False, default=True)
    auto_rollback_enabled = Column(Boolean, nullable=False, default=True)

    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)

    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/models/policy_experiment_arm.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyExperimentArmStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    retired = "retired"
    winner = "winner"
    loser = "loser"


class PolicyExperimentArm(Base):
    __tablename__ = "policy_experiment_arm"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("policy_experiment.id"), nullable=False, index=True)

    arm_key = Column(String(255), nullable=False, index=True)
    bundle_id = Column(String(255), nullable=False, index=True)
    is_control = Column(Boolean, nullable=False, default=False)

    status = Column(Enum(PolicyExperimentArmStatus), nullable=False, default=PolicyExperimentArmStatus.active)

    initial_weight = Column(Float, nullable=False, default=0.5)
    current_weight = Column(Float, nullable=False, default=0.5)
    min_weight = Column(Float, nullable=False, default=0.05)
    max_weight = Column(Float, nullable=False, default=0.95)

    alpha = Column(Float, nullable=False, default=1.0)
    beta = Column(Float, nullable=False, default=1.0)

    total_exposures = Column(Integer, nullable=False, default=0)
    total_successes = Column(Integer, nullable=False, default=0)
    total_failures = Column(Integer, nullable=False, default=0)

    latest_score = Column(Float, nullable=True)
    latest_regret = Column(Float, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/models/policy_experiment_exposure.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyExperimentExposure(Base):
    __tablename__ = "policy_experiment_exposure"
    __table_args__ = (
        UniqueConstraint("experiment_id", "subject_key", name="uq_policy_experiment_subject_once"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    experiment_id = Column(UUID(as_uuid=True), ForeignKey("policy_experiment.id"), nullable=False, index=True)
    arm_id = Column(UUID(as_uuid=True), ForeignKey("policy_experiment_arm.id"), nullable=False, index=True)

    subject_key = Column(String(255), nullable=False, index=True)
    subject_type = Column(String(64), nullable=False, default="review_case")

    cohort_key = Column(String(255), nullable=True, index=True)
    context_hash = Column(String(255), nullable=True, index=True)
    context_json = Column(JSON, nullable=False, default=dict)

    allocation_score = Column(Float, nullable=True)
    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
backend/app/models/policy_outcome_observation.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyOutcomeObservation(Base):
    __tablename__ = "policy_outcome_observation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exposure_id = Column(UUID(as_uuid=True), ForeignKey("policy_experiment_exposure.id"), nullable=False, index=True)

    observed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    sla_breach_delta = Column(Float, nullable=True)
    churn_delta = Column(Float, nullable=True)
    rework_delta = Column(Float, nullable=True)
    conflict_delta = Column(Float, nullable=True)
    rebalance_success_delta = Column(Float, nullable=True)
    execution_cost_delta = Column(Float, nullable=True)

    net_benefit_score = Column(Float, nullable=True)
    success_label = Column(Boolean, nullable=False)

    control_baseline_json = Column(JSON, nullable=False, default=dict)
    pre_rollout_baseline_json = Column(JSON, nullable=False, default=dict)
    diff_in_diff_json = Column(JSON, nullable=False, default=dict)
    metadata_json = Column(JSON, nullable=False, default=dict)
backend/app/models/policy_learning_memory.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, Integer, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyLearningMemory(Base):
    __tablename__ = "policy_learning_memory"
    __table_args__ = (
        UniqueConstraint("memory_key", name="uq_policy_learning_memory_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    memory_key = Column(String(255), nullable=False, index=True)
    context_signature = Column(String(255), nullable=False, index=True)

    bundle_id = Column(String(255), nullable=False, index=True)
    arm_key = Column(String(255), nullable=False, index=True)

    win_count = Column(Integer, nullable=False, default=0)
    loss_count = Column(Integer, nullable=False, default=0)
    sample_count = Column(Integer, nullable=False, default=0)

    avg_net_benefit = Column(Float, nullable=False, default=0.0)
    avg_sla_delta = Column(Float, nullable=False, default=0.0)
    avg_churn_delta = Column(Float, nullable=False, default=0.0)
    avg_rebalance_delta = Column(Float, nullable=False, default=0.0)
    avg_cost_delta = Column(Float, nullable=False, default=0.0)

    last_observed_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/repositories/policy_experiment_repository.py
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_experiment import PolicyExperiment, PolicyExperimentStatus


class PolicyExperimentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, experiment: PolicyExperiment) -> PolicyExperiment:
        self.db.add(experiment)
        self.db.flush()
        return experiment

    def get(self, experiment_id: UUID) -> Optional[PolicyExperiment]:
        return self.db.query(PolicyExperiment).filter(PolicyExperiment.id == experiment_id).one_or_none()

    def get_by_key(self, experiment_key: str) -> Optional[PolicyExperiment]:
        return (
            self.db.query(PolicyExperiment)
            .filter(PolicyExperiment.experiment_key == experiment_key)
            .one_or_none()
        )

    def list_running(self) -> Sequence[PolicyExperiment]:
        return (
            self.db.query(PolicyExperiment)
            .filter(PolicyExperiment.status == PolicyExperimentStatus.running)
            .all()
        )

    def save(self, experiment: PolicyExperiment) -> PolicyExperiment:
        self.db.add(experiment)
        self.db.flush()
        return experiment
backend/app/repositories/policy_experiment_arm_repository.py
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_experiment_arm import PolicyExperimentArm, PolicyExperimentArmStatus


class PolicyExperimentArmRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, arm: PolicyExperimentArm) -> PolicyExperimentArm:
        self.db.add(arm)
        self.db.flush()
        return arm

    def get(self, arm_id: UUID) -> Optional[PolicyExperimentArm]:
        return self.db.query(PolicyExperimentArm).filter(PolicyExperimentArm.id == arm_id).one_or_none()

    def list_by_experiment_id(self, experiment_id: UUID) -> Sequence[PolicyExperimentArm]:
        return (
            self.db.query(PolicyExperimentArm)
            .filter(PolicyExperimentArm.experiment_id == experiment_id)
            .order_by(PolicyExperimentArm.arm_key.asc())
            .all()
        )

    def list_active_by_experiment_id(self, experiment_id: UUID) -> Sequence[PolicyExperimentArm]:
        return (
            self.db.query(PolicyExperimentArm)
            .filter(
                PolicyExperimentArm.experiment_id == experiment_id,
                PolicyExperimentArm.status == PolicyExperimentArmStatus.active,
            )
            .order_by(PolicyExperimentArm.arm_key.asc())
            .all()
        )

    def save(self, arm: PolicyExperimentArm) -> PolicyExperimentArm:
        self.db.add(arm)
        self.db.flush()
        return arm
backend/app/repositories/policy_experiment_exposure_repository.py
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_experiment_exposure import PolicyExperimentExposure


class PolicyExperimentExposureRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, exposure: PolicyExperimentExposure) -> PolicyExperimentExposure:
        self.db.add(exposure)
        self.db.flush()
        return exposure

    def get(self, exposure_id: UUID) -> Optional[PolicyExperimentExposure]:
        return (
            self.db.query(PolicyExperimentExposure)
            .filter(PolicyExperimentExposure.id == exposure_id)
            .one_or_none()
        )

    def get_by_subject_key(self, experiment_id: UUID, subject_key: str) -> Optional[PolicyExperimentExposure]:
        return (
            self.db.query(PolicyExperimentExposure)
            .filter(
                PolicyExperimentExposure.experiment_id == experiment_id,
                PolicyExperimentExposure.subject_key == subject_key,
            )
            .one_or_none()
        )

    def list_by_experiment_id(self, experiment_id: UUID) -> Sequence[PolicyExperimentExposure]:
        return (
            self.db.query(PolicyExperimentExposure)
            .filter(PolicyExperimentExposure.experiment_id == experiment_id)
            .all()
        )
backend/app/repositories/policy_outcome_observation_repository.py
from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_outcome_observation import PolicyOutcomeObservation


class PolicyOutcomeObservationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, observation: PolicyOutcomeObservation) -> PolicyOutcomeObservation:
        self.db.add(observation)
        self.db.flush()
        return observation

    def list_by_exposure_id(self, exposure_id: UUID) -> Sequence[PolicyOutcomeObservation]:
        return (
            self.db.query(PolicyOutcomeObservation)
            .filter(PolicyOutcomeObservation.exposure_id == exposure_id)
            .all()
        )
backend/app/repositories/policy_learning_memory_repository.py
from __future__ import annotations

from typing import Optional, Sequence
from sqlalchemy.orm import Session

from app.models.policy_learning_memory import PolicyLearningMemory


class PolicyLearningMemoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_memory_key(self, memory_key: str) -> Optional[PolicyLearningMemory]:
        return (
            self.db.query(PolicyLearningMemory)
            .filter(PolicyLearningMemory.memory_key == memory_key)
            .one_or_none()
        )

    def create(self, memory: PolicyLearningMemory) -> PolicyLearningMemory:
        self.db.add(memory)
        self.db.flush()
        return memory

    def save(self, memory: PolicyLearningMemory) -> PolicyLearningMemory:
        self.db.add(memory)
        self.db.flush()
        return memory

    def list_by_context_signature(self, context_signature: str) -> Sequence[PolicyLearningMemory]:
        return (
            self.db.query(PolicyLearningMemory)
            .filter(PolicyLearningMemory.context_signature == context_signature)
            .order_by(PolicyLearningMemory.avg_net_benefit.desc())
            .all()
        )
backend/app/schemas/policy_experiment.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PolicyExperimentArmCreateRequest(BaseModel):
    arm_key: str
    bundle_id: str
    is_control: bool = False
    initial_weight: float = 0.5
    min_weight: float = 0.05
    max_weight: float = 0.95
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class PolicyExperimentCreateRequest(BaseModel):
    experiment_key: str
    name: str
    description: Optional[str] = None
    objective: str = "maximize_net_benefit"
    targeting_filters: Dict[str, Any] = Field(default_factory=dict)
    allocation_strategy: str = "thompson_sampling"
    control_arm_key: Optional[str] = None
    min_sample_size_per_arm: int = 50
    confidence_threshold: int = 95
    auto_promote_enabled: bool = False
    auto_pause_on_regression: bool = True
    auto_rollback_enabled: bool = True
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    arms: List[PolicyExperimentArmCreateRequest]


class PolicyExperimentExposureAssignRequest(BaseModel):
    experiment_key: str
    subject_key: str
    subject_type: str = "review_case"
    context_json: Dict[str, Any] = Field(default_factory=dict)


class PolicyOutcomeObservationCreateRequest(BaseModel):
    exposure_id: UUID
    sla_breach_delta: Optional[float] = None
    churn_delta: Optional[float] = None
    rework_delta: Optional[float] = None
    conflict_delta: Optional[float] = None
    rebalance_success_delta: Optional[float] = None
    execution_cost_delta: Optional[float] = None
    control_baseline_json: Dict[str, Any] = Field(default_factory=dict)
    pre_rollout_baseline_json: Dict[str, Any] = Field(default_factory=dict)
    diff_in_diff_json: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class PolicyExperimentArmResponse(BaseModel):
    id: UUID
    arm_key: str
    bundle_id: str
    is_control: bool
    status: str
    current_weight: float
    alpha: float
    beta: float
    total_exposures: int
    total_successes: int
    total_failures: int
    latest_score: Optional[float]

    class Config:
        from_attributes = True


class PolicyExperimentResponse(BaseModel):
    id: UUID
    experiment_key: str
    name: str
    description: Optional[str]
    status: str
    objective: str
    allocation_strategy: str
    control_arm_key: Optional[str]
    min_sample_size_per_arm: int
    confidence_threshold: int
    auto_promote_enabled: bool
    auto_pause_on_regression: bool
    auto_rollback_enabled: bool
    targeting_filters: Dict[str, Any]
    start_at: Optional[datetime]
    end_at: Optional[datetime]
    arms: List[PolicyExperimentArmResponse]

    class Config:
        from_attributes = True
backend/app/services/policy_context_signature_service.py
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


class PolicyContextSignatureService:
    KEY_FIELDS = [
        "queue",
        "severity",
        "shift",
        "project",
        "reviewer_bucket",
        "review_case_bucket",
    ]

    def build_context_signature(self, context: Dict[str, Any]) -> str:
        normalized = {k: context.get(k) for k in self.KEY_FIELDS}
        payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

    def build_subject_bucket(self, subject_key: str, bucket_count: int = 100) -> int:
        value = int(hashlib.sha256(subject_key.encode("utf-8")).hexdigest(), 16)
        return value % bucket_count
backend/app/services/policy_variant_scoring_service.py
from __future__ import annotations

from typing import Optional


class PolicyVariantScoringService:
    """
    Positive is good:
    - lower SLA breach => positive when delta negative
    - lower churn/rework/conflict => positive when delta negative
    - higher rebalance success => positive when delta positive
    - lower cost => positive when delta negative
    """

    def compute_net_benefit_score(
        self,
        sla_breach_delta: Optional[float],
        churn_delta: Optional[float],
        rework_delta: Optional[float],
        conflict_delta: Optional[float],
        rebalance_success_delta: Optional[float],
        execution_cost_delta: Optional[float],
    ) -> float:
        score = 0.0

        if sla_breach_delta is not None:
            score += (-1.0 * sla_breach_delta) * 5.0
        if churn_delta is not None:
            score += (-1.0 * churn_delta) * 3.0
        if rework_delta is not None:
            score += (-1.0 * rework_delta) * 2.0
        if conflict_delta is not None:
            score += (-1.0 * conflict_delta) * 2.0
        if rebalance_success_delta is not None:
            score += rebalance_success_delta * 4.0
        if execution_cost_delta is not None:
            score += (-1.0 * execution_cost_delta) * 1.5

        return score

    def to_success_label(self, net_benefit_score: float, threshold: float = 0.0) -> bool:
        return net_benefit_score >= threshold
backend/app/services/policy_bandit_allocator_service.py
from __future__ import annotations

import random
from typing import List

from app.models.policy_experiment_arm import PolicyExperimentArm


class PolicyBanditAllocatorService:
    """
    Thompson Sampling over Beta(alpha, beta).
    """

    def choose_arm(self, arms: List[PolicyExperimentArm]) -> PolicyExperimentArm:
        if not arms:
            raise ValueError("No active experiment arms available")

        samples = []
        for arm in arms:
            sampled = random.betavariate(max(arm.alpha, 0.001), max(arm.beta, 0.001))
            adjusted = sampled * arm.current_weight
            samples.append((adjusted, arm))

        samples.sort(key=lambda item: item[0], reverse=True)
        return samples[0][1]

    def update_posterior(self, arm: PolicyExperimentArm, success: bool) -> PolicyExperimentArm:
        arm.total_exposures += 1
        if success:
            arm.alpha += 1.0
            arm.total_successes += 1
        else:
            arm.beta += 1.0
            arm.total_failures += 1
        return arm
backend/app/services/policy_cross_bundle_learning_memory_service.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.policy_learning_memory import PolicyLearningMemory
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository


class PolicyCrossBundleLearningMemoryService:
    def __init__(self, memory_repo: PolicyLearningMemoryRepository) -> None:
        self.memory_repo = memory_repo

    def build_memory_key(self, context_signature: str, bundle_id: str, arm_key: str) -> str:
        return f"{context_signature}:{bundle_id}:{arm_key}"

    def update_memory(
        self,
        context_signature: str,
        bundle_id: str,
        arm_key: str,
        success_label: bool,
        net_benefit_score: float,
        sla_delta: Optional[float],
        churn_delta: Optional[float],
        rebalance_delta: Optional[float],
        cost_delta: Optional[float],
    ) -> PolicyLearningMemory:
        memory_key = self.build_memory_key(context_signature, bundle_id, arm_key)
        memory = self.memory_repo.get_by_memory_key(memory_key)

        if memory is None:
            memory = PolicyLearningMemory(
                memory_key=memory_key,
                context_signature=context_signature,
                bundle_id=bundle_id,
                arm_key=arm_key,
            )
            self.memory_repo.create(memory)

        prev_n = memory.sample_count
        new_n = prev_n + 1

        def rolling_avg(old: float, new_val: float) -> float:
            return ((old * prev_n) + new_val) / new_n

        memory.sample_count = new_n
        if success_label:
            memory.win_count += 1
        else:
            memory.loss_count += 1

        memory.avg_net_benefit = rolling_avg(memory.avg_net_benefit, net_benefit_score)
        memory.avg_sla_delta = rolling_avg(memory.avg_sla_delta, float(sla_delta or 0.0))
        memory.avg_churn_delta = rolling_avg(memory.avg_churn_delta, float(churn_delta or 0.0))
        memory.avg_rebalance_delta = rolling_avg(memory.avg_rebalance_delta, float(rebalance_delta or 0.0))
        memory.avg_cost_delta = rolling_avg(memory.avg_cost_delta, float(cost_delta or 0.0))
        memory.last_observed_at = datetime.utcnow()

        return self.memory_repo.save(memory)
backend/app/services/policy_experiment_service.py
from __future__ import annotations

from typing import Dict, Any
from uuid import UUID

from app.models.policy_experiment import PolicyExperiment, PolicyExperimentStatus, PolicyExperimentObjective
from app.models.policy_experiment_arm import PolicyExperimentArm
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.schemas.policy_experiment import PolicyExperimentCreateRequest


class PolicyExperimentService:
    def __init__(
        self,
        experiment_repo: PolicyExperimentRepository,
        arm_repo: PolicyExperimentArmRepository,
    ) -> None:
        self.experiment_repo = experiment_repo
        self.arm_repo = arm_repo

    def create_experiment(self, payload: PolicyExperimentCreateRequest, actor_id: str) -> PolicyExperiment:
        experiment = PolicyExperiment(
            experiment_key=payload.experiment_key,
            name=payload.name,
            description=payload.description,
            objective=PolicyExperimentObjective(payload.objective),
            targeting_filters=payload.targeting_filters,
            allocation_strategy=payload.allocation_strategy,
            control_arm_key=payload.control_arm_key,
            min_sample_size_per_arm=payload.min_sample_size_per_arm,
            confidence_threshold=payload.confidence_threshold,
            auto_promote_enabled=payload.auto_promote_enabled,
            auto_pause_on_regression=payload.auto_pause_on_regression,
            auto_rollback_enabled=payload.auto_rollback_enabled,
            start_at=payload.start_at,
            end_at=payload.end_at,
            status=PolicyExperimentStatus.draft,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.experiment_repo.create(experiment)

        for arm_payload in payload.arms:
            arm = PolicyExperimentArm(
                experiment_id=experiment.id,
                arm_key=arm_payload.arm_key,
                bundle_id=arm_payload.bundle_id,
                is_control=arm_payload.is_control,
                initial_weight=arm_payload.initial_weight,
                current_weight=arm_payload.initial_weight,
                min_weight=arm_payload.min_weight,
                max_weight=arm_payload.max_weight,
                metadata_json=arm_payload.metadata_json,
            )
            self.arm_repo.create(arm)

        return experiment

    def start_experiment(self, experiment_id: UUID, actor_id: str) -> PolicyExperiment:
        experiment = self._require_experiment(experiment_id)
        experiment.status = PolicyExperimentStatus.running
        experiment.updated_by = actor_id
        return self.experiment_repo.save(experiment)

    def pause_experiment(self, experiment_id: UUID, actor_id: str) -> PolicyExperiment:
        experiment = self._require_experiment(experiment_id)
        experiment.status = PolicyExperimentStatus.paused
        experiment.updated_by = actor_id
        return self.experiment_repo.save(experiment)

    def complete_experiment(self, experiment_id: UUID, actor_id: str) -> PolicyExperiment:
        experiment = self._require_experiment(experiment_id)
        experiment.status = PolicyExperimentStatus.completed
        experiment.updated_by = actor_id
        return self.experiment_repo.save(experiment)

    def get_with_arms(self, experiment_id: UUID) -> Dict[str, Any]:
        experiment = self._require_experiment(experiment_id)
        arms = self.arm_repo.list_by_experiment_id(experiment.id)
        return {
            "experiment": experiment,
            "arms": arms,
        }

    def _require_experiment(self, experiment_id: UUID) -> PolicyExperiment:
        experiment = self.experiment_repo.get(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_id}")
        return experiment
backend/app/services/policy_exposure_assignment_service.py
from __future__ import annotations

from typing import Any, Dict

from app.models.policy_experiment_exposure import PolicyExperimentExposure
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_experiment_exposure_repository import PolicyExperimentExposureRepository
from app.services.policy_context_signature_service import PolicyContextSignatureService
from app.services.policy_bandit_allocator_service import PolicyBanditAllocatorService


class PolicyExposureAssignmentService:
    def __init__(
        self,
        experiment_repo: PolicyExperimentRepository,
        arm_repo: PolicyExperimentArmRepository,
        exposure_repo: PolicyExperimentExposureRepository,
        context_signature_service: PolicyContextSignatureService,
        bandit_allocator_service: PolicyBanditAllocatorService,
    ) -> None:
        self.experiment_repo = experiment_repo
        self.arm_repo = arm_repo
        self.exposure_repo = exposure_repo
        self.context_signature_service = context_signature_service
        self.bandit_allocator_service = bandit_allocator_service

    def assign(
        self,
        experiment_key: str,
        subject_key: str,
        subject_type: str,
        context_json: Dict[str, Any],
    ) -> PolicyExperimentExposure:
        experiment = self.experiment_repo.get_by_key(experiment_key)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_key}")

        existing = self.exposure_repo.get_by_subject_key(experiment.id, subject_key)
        if existing is not None:
            return existing

        active_arms = list(self.arm_repo.list_active_by_experiment_id(experiment.id))
        chosen_arm = self.bandit_allocator_service.choose_arm(active_arms)

        context_signature = self.context_signature_service.build_context_signature(context_json)
        cohort_key = self._build_cohort_key(subject_key, context_json)

        exposure = PolicyExperimentExposure(
            experiment_id=experiment.id,
            arm_id=chosen_arm.id,
            subject_key=subject_key,
            subject_type=subject_type,
            cohort_key=cohort_key,
            context_hash=context_signature,
            context_json=context_json,
            allocation_score=chosen_arm.current_weight,
        )
        return self.exposure_repo.create(exposure)

    def _build_cohort_key(self, subject_key: str, context_json: Dict[str, Any]) -> str:
        queue = context_json.get("queue", "unknown")
        severity = context_json.get("severity", "unknown")
        shift = context_json.get("shift", "unknown")
        project = context_json.get("project", "unknown")
        bucket = self.context_signature_service.build_subject_bucket(subject_key)
        return f"{queue}:{severity}:{shift}:{project}:bucket-{bucket}"
backend/app/services/policy_outcome_learning_service.py
from __future__ import annotations

from app.models.policy_outcome_observation import PolicyOutcomeObservation
from app.repositories.policy_experiment_exposure_repository import PolicyExperimentExposureRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_outcome_observation_repository import PolicyOutcomeObservationRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository
from app.services.policy_variant_scoring_service import PolicyVariantScoringService
from app.services.policy_bandit_allocator_service import PolicyBanditAllocatorService
from app.services.policy_cross_bundle_learning_memory_service import PolicyCrossBundleLearningMemoryService


class PolicyOutcomeLearningService:
    def __init__(
        self,
        exposure_repo: PolicyExperimentExposureRepository,
        arm_repo: PolicyExperimentArmRepository,
        observation_repo: PolicyOutcomeObservationRepository,
        memory_repo: PolicyLearningMemoryRepository,
        scoring_service: PolicyVariantScoringService,
        bandit_allocator_service: PolicyBanditAllocatorService,
    ) -> None:
        self.exposure_repo = exposure_repo
        self.arm_repo = arm_repo
        self.observation_repo = observation_repo
        self.scoring_service = scoring_service
        self.bandit_allocator_service = bandit_allocator_service
        self.cross_bundle_memory_service = PolicyCrossBundleLearningMemoryService(memory_repo)

    def observe(
        self,
        exposure_id,
        sla_breach_delta,
        churn_delta,
        rework_delta,
        conflict_delta,
        rebalance_success_delta,
        execution_cost_delta,
        control_baseline_json,
        pre_rollout_baseline_json,
        diff_in_diff_json,
        metadata_json,
    ) -> PolicyOutcomeObservation:
        exposure = self.exposure_repo.get(exposure_id)
        if exposure is None:
            raise ValueError(f"Exposure not found: {exposure_id}")

        arm = self.arm_repo.get(exposure.arm_id)
        if arm is None:
            raise ValueError(f"Arm not found for exposure: {exposure.arm_id}")

        net_benefit_score = self.scoring_service.compute_net_benefit_score(
            sla_breach_delta=sla_breach_delta,
            churn_delta=churn_delta,
            rework_delta=rework_delta,
            conflict_delta=conflict_delta,
            rebalance_success_delta=rebalance_success_delta,
            execution_cost_delta=execution_cost_delta,
        )
        success_label = self.scoring_service.to_success_label(net_benefit_score)

        observation = PolicyOutcomeObservation(
            exposure_id=exposure.id,
            sla_breach_delta=sla_breach_delta,
            churn_delta=churn_delta,
            rework_delta=rework_delta,
            conflict_delta=conflict_delta,
            rebalance_success_delta=rebalance_success_delta,
            execution_cost_delta=execution_cost_delta,
            net_benefit_score=net_benefit_score,
            success_label=success_label,
            control_baseline_json=control_baseline_json,
            pre_rollout_baseline_json=pre_rollout_baseline_json,
            diff_in_diff_json=diff_in_diff_json,
            metadata_json=metadata_json,
        )
        self.observation_repo.create(observation)

        self.bandit_allocator_service.update_posterior(arm, success_label)
        arm.latest_score = net_benefit_score
        self.arm_repo.save(arm)

        self.cross_bundle_memory_service.update_memory(
            context_signature=exposure.context_hash or "unknown",
            bundle_id=arm.bundle_id,
            arm_key=arm.arm_key,
            success_label=success_label,
            net_benefit_score=net_benefit_score,
            sla_delta=sla_breach_delta,
            churn_delta=churn_delta,
            rebalance_delta=rebalance_success_delta,
            cost_delta=execution_cost_delta,
        )

        return observation
backend/app/services/policy_experiment_decision_service.py
from __future__ import annotations

from typing import Dict, Any, List

from app.models.policy_experiment import PolicyExperiment
from app.models.policy_experiment_arm import PolicyExperimentArm, PolicyExperimentArmStatus


class PolicyExperimentDecisionService:
    def decide(self, experiment: PolicyExperiment, arms: List[PolicyExperimentArm]) -> Dict[str, Any]:
        eligible = [a for a in arms if a.total_exposures >= experiment.min_sample_size_per_arm]
        if not eligible:
            return {
                "ready": False,
                "winner_arm_id": None,
                "winner_arm_key": None,
                "reason": "not_enough_samples",
            }

        ranked = sorted(
            eligible,
            key=lambda a: ((a.latest_score or 0.0), a.total_successes, -a.total_failures),
            reverse=True,
        )
        winner = ranked[0]

        return {
            "ready": True,
            "winner_arm_id": str(winner.id),
            "winner_arm_key": winner.arm_key,
            "winner_bundle_id": winner.bundle_id,
            "winner_latest_score": winner.latest_score,
            "ranked_arm_keys": [arm.arm_key for arm in ranked],
        }

    def mark_winner_loser_states(self, winner_arm_key: str, arms: List[PolicyExperimentArm]) -> List[PolicyExperimentArm]:
        for arm in arms:
            if arm.arm_key == winner_arm_key:
                arm.status = PolicyExperimentArmStatus.winner
            else:
                if arm.status == PolicyExperimentArmStatus.active:
                    arm.status = PolicyExperimentArmStatus.loser
        return arms
backend/app/services/policy_rollout_bandit_orchestration_service.py
from __future__ import annotations

from typing import Any, Dict, Optional

from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.services.policy_experiment_decision_service import PolicyExperimentDecisionService


class PolicyRolloutBanditOrchestrationService:
    """
    Khung orchestration.
    Repo thật có thể nối tiếp:
    - canary scheduler
    - realized metrics ingestion
    - rollback guard
    - bundle lifecycle promotion
    - operator approval gate
    """

    def __init__(
        self,
        experiment_repo: PolicyExperimentRepository,
        arm_repo: PolicyExperimentArmRepository,
        decision_service: PolicyExperimentDecisionService,
        rollback_guard_service=None,
        bundle_lifecycle_service=None,
        alert_service=None,
    ) -> None:
        self.experiment_repo = experiment_repo
        self.arm_repo = arm_repo
        self.decision_service = decision_service
        self.rollback_guard_service = rollback_guard_service
        self.bundle_lifecycle_service = bundle_lifecycle_service
        self.alert_service = alert_service

    def evaluate_running_experiment(self, experiment_id) -> Dict[str, Any]:
        experiment = self.experiment_repo.get(experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_id}")

        arms = list(self.arm_repo.list_by_experiment_id(experiment.id))
        decision = self.decision_service.decide(experiment, arms)

        rollback_result: Optional[Dict[str, Any]] = None
        if self.rollback_guard_service is not None:
            rollback_result = self.rollback_guard_service.evaluate_experiment_guardrails(
                experiment=experiment,
                arms=arms,
            )

        if rollback_result and rollback_result.get("should_rollback"):
            if self.alert_service is not None:
                self.alert_service.emit(
                    event_type="policy_experiment_auto_rollback",
                    payload={
                        "experiment_id": str(experiment.id),
                        "reason": rollback_result.get("reason"),
                    },
                )
            return {
                "decision": decision,
                "rollback": rollback_result,
            }

        if decision.get("ready") and experiment.auto_promote_enabled and self.bundle_lifecycle_service is not None:
            self.bundle_lifecycle_service.promote_bundle(
                bundle_id=decision["winner_bundle_id"],
                reason="bandit_experiment_winner",
                metadata={
                    "experiment_id": str(experiment.id),
                    "winner_arm_key": decision["winner_arm_key"],
                },
            )

        return {
            "decision": decision,
            "rollback": rollback_result,
        }
backend/app/api/policy_experiments.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_actor_id
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_experiment_exposure_repository import PolicyExperimentExposureRepository
from app.repositories.policy_outcome_observation_repository import PolicyOutcomeObservationRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository
from app.schemas.policy_experiment import (
    PolicyExperimentCreateRequest,
    PolicyExperimentExposureAssignRequest,
    PolicyOutcomeObservationCreateRequest,
)
from app.services.policy_experiment_service import PolicyExperimentService
from app.services.policy_context_signature_service import PolicyContextSignatureService
from app.services.policy_bandit_allocator_service import PolicyBanditAllocatorService
from app.services.policy_exposure_assignment_service import PolicyExposureAssignmentService
from app.services.policy_variant_scoring_service import PolicyVariantScoringService
from app.services.policy_outcome_learning_service import PolicyOutcomeLearningService
from app.services.policy_experiment_decision_service import PolicyExperimentDecisionService
from app.services.policy_rollout_bandit_orchestration_service import PolicyRolloutBanditOrchestrationService

router = APIRouter(prefix="/policy-experiments", tags=["policy-experiments"])


@router.post("")
def create_policy_experiment(
    payload: PolicyExperimentCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    experiment_repo = PolicyExperimentRepository(db)
    arm_repo = PolicyExperimentArmRepository(db)

    service = PolicyExperimentService(experiment_repo, arm_repo)
    experiment = service.create_experiment(payload, actor_id=actor_id)
    db.commit()
    return {"id": str(experiment.id), "experiment_key": experiment.experiment_key}


@router.post("/{experiment_id}/start")
def start_policy_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    experiment_repo = PolicyExperimentRepository(db)
    arm_repo = PolicyExperimentArmRepository(db)
    service = PolicyExperimentService(experiment_repo, arm_repo)

    try:
        experiment = service.start_experiment(experiment_id, actor_id=actor_id)
        db.commit()
        return {"id": str(experiment.id), "status": experiment.status.value}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/assign")
def assign_experiment_arm(
    payload: PolicyExperimentExposureAssignRequest,
    db: Session = Depends(get_db),
):
    service = PolicyExposureAssignmentService(
        experiment_repo=PolicyExperimentRepository(db),
        arm_repo=PolicyExperimentArmRepository(db),
        exposure_repo=PolicyExperimentExposureRepository(db),
        context_signature_service=PolicyContextSignatureService(),
        bandit_allocator_service=PolicyBanditAllocatorService(),
    )
    try:
        exposure = service.assign(
            experiment_key=payload.experiment_key,
            subject_key=payload.subject_key,
            subject_type=payload.subject_type,
            context_json=payload.context_json,
        )
        db.commit()
        return {
            "exposure_id": str(exposure.id),
            "experiment_id": str(exposure.experiment_id),
            "arm_id": str(exposure.arm_id),
            "cohort_key": exposure.cohort_key,
            "context_hash": exposure.context_hash,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/observe")
def observe_experiment_outcome(
    payload: PolicyOutcomeObservationCreateRequest,
    db: Session = Depends(get_db),
):
    service = PolicyOutcomeLearningService(
        exposure_repo=PolicyExperimentExposureRepository(db),
        arm_repo=PolicyExperimentArmRepository(db),
        observation_repo=PolicyOutcomeObservationRepository(db),
        memory_repo=PolicyLearningMemoryRepository(db),
        scoring_service=PolicyVariantScoringService(),
        bandit_allocator_service=PolicyBanditAllocatorService(),
    )
    try:
        observation = service.observe(
            exposure_id=payload.exposure_id,
            sla_breach_delta=payload.sla_breach_delta,
            churn_delta=payload.churn_delta,
            rework_delta=payload.rework_delta,
            conflict_delta=payload.conflict_delta,
            rebalance_success_delta=payload.rebalance_success_delta,
            execution_cost_delta=payload.execution_cost_delta,
            control_baseline_json=payload.control_baseline_json,
            pre_rollout_baseline_json=payload.pre_rollout_baseline_json,
            diff_in_diff_json=payload.diff_in_diff_json,
            metadata_json=payload.metadata_json,
        )
        db.commit()
        return {
            "observation_id": str(observation.id),
            "net_benefit_score": observation.net_benefit_score,
            "success_label": observation.success_label,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{experiment_id}/evaluate")
def evaluate_policy_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
):
    service = PolicyRolloutBanditOrchestrationService(
        experiment_repo=PolicyExperimentRepository(db),
        arm_repo=PolicyExperimentArmRepository(db),
        decision_service=PolicyExperimentDecisionService(),
    )
    try:
        result = service.evaluate_running_experiment(experiment_id)
        db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
backend/app/workers/policy_experiment_evaluation_worker.py
from __future__ import annotations

from app.db.session import SessionLocal
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.services.policy_experiment_decision_service import PolicyExperimentDecisionService
from app.services.policy_rollout_bandit_orchestration_service import PolicyRolloutBanditOrchestrationService


def evaluate_running_policy_experiments() -> dict:
    db = SessionLocal()
    try:
        experiment_repo = PolicyExperimentRepository(db)
        running = experiment_repo.list_running()

        results = []
        orchestrator = PolicyRolloutBanditOrchestrationService(
            experiment_repo=experiment_repo,
            arm_repo=PolicyExperimentArmRepository(db),
            decision_service=PolicyExperimentDecisionService(),
        )

        for experiment in running:
            result = orchestrator.evaluate_running_experiment(experiment.id)
            results.append(
                {
                    "experiment_id": str(experiment.id),
                    "experiment_key": experiment.experiment_key,
                    "result": result,
                }
            )

        db.commit()
        return {"evaluated": len(results), "results": results}
    finally:
        db.close()
backend/alembic/versions/20260412_0030_policy_experimentation_bandit_memory.py
"""policy experimentation bandit memory

Revision ID: 20260412_0030
Revises: 20260412_0029
Create Date: 2026-04-12 10:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260412_0030"
down_revision = "20260412_0029"
branch_labels = None
depends_on = None


policy_experiment_status_enum = sa.Enum(
    "draft",
    "running",
    "paused",
    "completed",
    "canceled",
    name="policyexperimentstatus",
)

policy_experiment_objective_enum = sa.Enum(
    "maximize_net_benefit",
    "minimize_sla_breach",
    "maximize_rebalance_success",
    "minimize_churn_rework",
    "minimize_cost",
    name="policyexperimentobjective",
)

policy_experiment_arm_status_enum = sa.Enum(
    "active",
    "paused",
    "retired",
    "winner",
    "loser",
    name="policyexperimentarmstatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    policy_experiment_status_enum.create(bind, checkfirst=True)
    policy_experiment_objective_enum.create(bind, checkfirst=True)
    policy_experiment_arm_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "policy_experiment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("experiment_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", policy_experiment_status_enum, nullable=False),
        sa.Column("objective", policy_experiment_objective_enum, nullable=False),
        sa.Column("targeting_filters", sa.JSON(), nullable=False),
        sa.Column("allocation_strategy", sa.String(length=64), nullable=False),
        sa.Column("control_arm_key", sa.String(length=255), nullable=True),
        sa.Column("min_sample_size_per_arm", sa.Integer(), nullable=False),
        sa.Column("confidence_threshold", sa.Integer(), nullable=False),
        sa.Column("auto_promote_enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_pause_on_regression", sa.Boolean(), nullable=False),
        sa.Column("auto_rollback_enabled", sa.Boolean(), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=True),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_experiment_experiment_key", "policy_experiment", ["experiment_key"], unique=True)

    op.create_table(
        "policy_experiment_arm",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_experiment.id"), nullable=False),
        sa.Column("arm_key", sa.String(length=255), nullable=False),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("is_control", sa.Boolean(), nullable=False),
        sa.Column("status", policy_experiment_arm_status_enum, nullable=False),
        sa.Column("initial_weight", sa.Float(), nullable=False),
        sa.Column("current_weight", sa.Float(), nullable=False),
        sa.Column("min_weight", sa.Float(), nullable=False),
        sa.Column("max_weight", sa.Float(), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False),
        sa.Column("beta", sa.Float(), nullable=False),
        sa.Column("total_exposures", sa.Integer(), nullable=False),
        sa.Column("total_successes", sa.Integer(), nullable=False),
        sa.Column("total_failures", sa.Integer(), nullable=False),
        sa.Column("latest_score", sa.Float(), nullable=True),
        sa.Column("latest_regret", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_experiment_arm_experiment_id", "policy_experiment_arm", ["experiment_id"], unique=False)
    op.create_index("ix_policy_experiment_arm_arm_key", "policy_experiment_arm", ["arm_key"], unique=False)
    op.create_index("ix_policy_experiment_arm_bundle_id", "policy_experiment_arm", ["bundle_id"], unique=False)

    op.create_table(
        "policy_experiment_exposure",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_experiment.id"), nullable=False),
        sa.Column("arm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_experiment_arm.id"), nullable=False),
        sa.Column("subject_key", sa.String(length=255), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("cohort_key", sa.String(length=255), nullable=True),
        sa.Column("context_hash", sa.String(length=255), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("allocation_score", sa.Float(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("experiment_id", "subject_key", name="uq_policy_experiment_subject_once"),
    )
    op.create_index("ix_policy_experiment_exposure_experiment_id", "policy_experiment_exposure", ["experiment_id"], unique=False)
    op.create_index("ix_policy_experiment_exposure_arm_id", "policy_experiment_exposure", ["arm_id"], unique=False)
    op.create_index("ix_policy_experiment_exposure_subject_key", "policy_experiment_exposure", ["subject_key"], unique=False)
    op.create_index("ix_policy_experiment_exposure_cohort_key", "policy_experiment_exposure", ["cohort_key"], unique=False)
    op.create_index("ix_policy_experiment_exposure_context_hash", "policy_experiment_exposure", ["context_hash"], unique=False)

    op.create_table(
        "policy_outcome_observation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("exposure_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_experiment_exposure.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("sla_breach_delta", sa.Float(), nullable=True),
        sa.Column("churn_delta", sa.Float(), nullable=True),
        sa.Column("rework_delta", sa.Float(), nullable=True),
        sa.Column("conflict_delta", sa.Float(), nullable=True),
        sa.Column("rebalance_success_delta", sa.Float(), nullable=True),
        sa.Column("execution_cost_delta", sa.Float(), nullable=True),
        sa.Column("net_benefit_score", sa.Float(), nullable=True),
        sa.Column("success_label", sa.Boolean(), nullable=False),
        sa.Column("control_baseline_json", sa.JSON(), nullable=False),
        sa.Column("pre_rollout_baseline_json", sa.JSON(), nullable=False),
        sa.Column("diff_in_diff_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_policy_outcome_observation_exposure_id", "policy_outcome_observation", ["exposure_id"], unique=False)

    op.create_table(
        "policy_learning_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("memory_key", sa.String(length=255), nullable=False),
        sa.Column("context_signature", sa.String(length=255), nullable=False),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("arm_key", sa.String(length=255), nullable=False),
        sa.Column("win_count", sa.Integer(), nullable=False),
        sa.Column("loss_count", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("avg_net_benefit", sa.Float(), nullable=False),
        sa.Column("avg_sla_delta", sa.Float(), nullable=False),
        sa.Column("avg_churn_delta", sa.Float(), nullable=False),
        sa.Column("avg_rebalance_delta", sa.Float(), nullable=False),
        sa.Column("avg_cost_delta", sa.Float(), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("memory_key", name="uq_policy_learning_memory_key"),
    )
    op.create_index("ix_policy_learning_memory_memory_key", "policy_learning_memory", ["memory_key"], unique=True)
    op.create_index("ix_policy_learning_memory_context_signature", "policy_learning_memory", ["context_signature"], unique=False)
    op.create_index("ix_policy_learning_memory_bundle_id", "policy_learning_memory", ["bundle_id"], unique=False)
    op.create_index("ix_policy_learning_memory_arm_key", "policy_learning_memory", ["arm_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_policy_learning_memory_arm_key", table_name="policy_learning_memory")
    op.drop_index("ix_policy_learning_memory_bundle_id", table_name="policy_learning_memory")
    op.drop_index("ix_policy_learning_memory_context_signature", table_name="policy_learning_memory")
    op.drop_index("ix_policy_learning_memory_memory_key", table_name="policy_learning_memory")
    op.drop_table("policy_learning_memory")

    op.drop_index("ix_policy_outcome_observation_exposure_id", table_name="policy_outcome_observation")
    op.drop_table("policy_outcome_observation")

    op.drop_index("ix_policy_experiment_exposure_context_hash", table_name="policy_experiment_exposure")
    op.drop_index("ix_policy_experiment_exposure_cohort_key", table_name="policy_experiment_exposure")
    op.drop_index("ix_policy_experiment_exposure_subject_key", table_name="policy_experiment_exposure")
    op.drop_index("ix_policy_experiment_exposure_arm_id", table_name="policy_experiment_exposure")
    op.drop_index("ix_policy_experiment_exposure_experiment_id", table_name="policy_experiment_exposure")
    op.drop_table("policy_experiment_exposure")

    op.drop_index("ix_policy_experiment_arm_bundle_id", table_name="policy_experiment_arm")
    op.drop_index("ix_policy_experiment_arm_arm_key", table_name="policy_experiment_arm")
    op.drop_index("ix_policy_experiment_arm_experiment_id", table_name="policy_experiment_arm")
    op.drop_table("policy_experiment_arm")

    op.drop_index("ix_policy_experiment_experiment_key", table_name="policy_experiment")
    op.drop_table("policy_experiment")

    bind = op.get_bind()
    policy_experiment_arm_status_enum.drop(bind, checkfirst=True)
    policy_experiment_objective_enum.drop(bind, checkfirst=True)
    policy_experiment_status_enum.drop(bind, checkfirst=True)
backend/tests/services/test_policy_bandit_allocator_service.py
from app.models.policy_experiment_arm import PolicyExperimentArm
from app.services.policy_bandit_allocator_service import PolicyBanditAllocatorService


def test_update_posterior_success():
    service = PolicyBanditAllocatorService()
    arm = PolicyExperimentArm(
        arm_key="variant_a",
        bundle_id="bundle-a",
        alpha=1.0,
        beta=1.0,
        total_exposures=0,
        total_successes=0,
        total_failures=0,
    )

    updated = service.update_posterior(arm, True)

    assert updated.alpha == 2.0
    assert updated.beta == 1.0
    assert updated.total_exposures == 1
    assert updated.total_successes == 1
    assert updated.total_failures == 0
backend/tests/services/test_policy_variant_scoring_service.py
from app.services.policy_variant_scoring_service import PolicyVariantScoringService


def test_compute_net_benefit_score_positive_case():
    service = PolicyVariantScoringService()

    score = service.compute_net_benefit_score(
        sla_breach_delta=-0.20,
        churn_delta=-0.10,
        rework_delta=-0.10,
        conflict_delta=-0.05,
        rebalance_success_delta=0.25,
        execution_cost_delta=-0.05,
    )

    assert score > 0
    assert service.to_success_label(score) is True
backend/tests/services/test_policy_context_signature_service.py
from app.services.policy_context_signature_service import PolicyContextSignatureService


def test_context_signature_is_stable():
    service = PolicyContextSignatureService()
    context = {
        "queue": "queue-a",
        "severity": "high",
        "shift": "night",
        "project": "project-x",
        "reviewer_bucket": "r1",
        "review_case_bucket": "c7",
    }

    sig1 = service.build_context_signature(context)
    sig2 = service.build_context_signature(context)

    assert sig1 == sig2
    assert len(sig1) == 24
4) ĐIỂM MAP QUAN TRỌNG KHI DÁN VÀO REPO THẬT
A. Nối vào bundle lifecycle thật
Trong repo thật, winner_bundle_id nên nối vào service hiện có, ví dụ:
PolicyBundleLifecycleService.promote_bundle(...)
PolicyBundleLifecycleService.retire_bundle(...)
PolicyCanaryReleaseService.rollout_bundle(...)
Ở bản trên mình để hook tại:
PolicyRolloutBanditOrchestrationService(... bundle_lifecycle_service=...)
B. Nối realized outcome ingestion thật
Hiện observe(...) nhận delta trực tiếp.
Repo thật nên có thêm lớp ingest như:
backend/app/services/policy_realized_metric_aggregation_service.py
đọc từ:
SLA metrics
churn/rework/conflict facts
staffing cost
execution cost
rebalance success tables
rồi build ra:
{
  "sla_breach_delta": ...,
  "churn_delta": ...,
  "rework_delta": ...,
  "conflict_delta": ...,
  "rebalance_success_delta": ...,
  "execution_cost_delta": ...
}
C. Outcome attribution thật
Bản trên dùng:
control baseline
pre-rollout baseline
diff-in-diff payload
Repo thật nên tính trong service riêng:
backend/app/services/policy_outcome_attribution_service.py
gồm:
delta vs control cohort
delta vs pre-rollout baseline
diff-in-diff nếu nhiều cohort
Sau đó mới gọi PolicyOutcomeLearningService.observe(...).
D. Rollback thật
Khi regression xuất hiện, repo thật nên nối thêm:
rollback active bundle về prior bundle
mark release = rolled_back
emit audit event
emit alert
freeze auto-promote
Bản trên đã chừa sẵn hook:
rollback_guard_service
alert_service
bundle_lifecycle_service
E. Hash bucket targeting thật
Ở bản này cohort đang xây từ:
queue
severity
shift
project
subject hash bucket
Repo thật có thể thay _build_cohort_key(...) bằng:
reviewer hash bucket
review_case_id hash bucket
project-specific cohort split
shift-local randomization
5) CÁCH NỐI ROUTER VÀO APP
Trong backend/app/main.py hoặc router registry:
from app.api.policy_experiments import router as policy_experiment_router

app.include_router(policy_experiment_router)
6) FLOW THỰC THI SAU KHI DÁN PATCH
Bước 1 — tạo experiment
POST /policy-experiments
{
  "experiment_key": "bundle-routing-exp-001",
  "name": "Bundle routing experiment 001",
  "description": "Compare control vs adaptive staffing policy",
  "objective": "maximize_net_benefit",
  "targeting_filters": {
    "queue": ["fraud_review", "ops_review"],
    "severity": ["high", "critical"],
    "shift": ["night"]
  },
  "allocation_strategy": "thompson_sampling",
  "control_arm_key": "control",
  "min_sample_size_per_arm": 50,
  "confidence_threshold": 95,
  "auto_promote_enabled": true,
  "auto_pause_on_regression": true,
  "auto_rollback_enabled": true,
  "arms": [
    {
      "arm_key": "control",
      "bundle_id": "bundle-control-v3",
      "is_control": true,
      "initial_weight": 0.5
    },
    {
      "arm_key": "variant_a",
      "bundle_id": "bundle-variant-a-v1",
      "is_control": false,
      "initial_weight": 0.5
    }
  ]
}
Bước 2 — start experiment
POST /policy-experiments/{experiment_id}/start
Bước 3 — assign exposure khi case vào queue
POST /policy-experiments/assign
{
  "experiment_key": "bundle-routing-exp-001",
  "subject_key": "review-case-12345",
  "subject_type": "review_case",
  "context_json": {
    "queue": "fraud_review",
    "severity": "critical",
    "shift": "night",
    "project": "apollo",
    "reviewer_bucket": "r2",
    "review_case_bucket": "c17"
  }
}
Hệ sẽ trả arm được chọn.
Bước 4 — ingest outcome thật
POST /policy-experiments/observe
{
  "exposure_id": "REPLACE_UUID",
  "sla_breach_delta": -0.15,
  "churn_delta": -0.04,
  "rework_delta": -0.08,
  "conflict_delta": -0.02,
  "rebalance_success_delta": 0.22,
  "execution_cost_delta": -0.03,
  "control_baseline_json": {
    "sla_breach_rate": 0.31
  },
  "pre_rollout_baseline_json": {
    "sla_breach_rate": 0.36
  },
  "diff_in_diff_json": {
    "estimated_treatment_effect": 0.12
  },
  "metadata_json": {
    "window": "24h"
  }
}
Khi observe:
outcome được lưu
posterior arm được update
learning memory được update
Bước 5 — evaluate experiment định kỳ
Worker hoặc cron gọi:
evaluate_running_policy_experiments()
hoặc API:
POST /policy-experiments/{experiment_id}/evaluate
7) BƯỚC NÂNG CẤP MẠNH NHẤT NGAY SAU BẢN NÀY
Sau patch này, hệ đã có:
experiment arms
bandit allocation
exposure tracking
outcome learning
cross-bundle learning memory
bản PHASE 3 — CONTEXTUAL BANDIT + POLICY FEATURE STORE + OFFLINE POLICY REPLAY EVALUATOR theo đúng kiểu full code file-by-file paste-ready.
Mục tiêu của phase này:
từ global bandit
sang contextual bandit
có feature store cho policy context
có offline replay evaluator
có segment-level learning memory
chọn policy variant theo context thật, không còn một phân phối chung cho toàn hệ
1) HỆ ĐÃ NÂNG LÊN MỨC NÀO SAU PHASE NÀY
Sau phase này, hệ đi từ:
cùng một bandit cho mọi queue / severity / shift / project
sang:
mỗi context có tín hiệu riêng
mỗi arm có hiệu quả khác nhau theo segment
rollout được chọn theo policy context
có replay evaluator để test trên data lịch sử trước khi rollout thật
memory không chỉ lưu bundle thắng/thua chung, mà lưu theo segment/context signature
2) THIẾT KẾ NGẮN GỌN
Thêm 5 khối mới:
PolicyFeatureSnapshot
snapshot feature cho subject/context tại thời điểm assign hoặc evaluate
PolicyFeatureStoreService
normalize + build feature vector / segment key / context signature
PolicyContextualBanditService
chọn arm theo:
global posterior
segment memory prior
contextual feature score
PolicyReplayEvaluatorService
chạy replay offline trên historical decisions/outcomes
ước tính:
regret
win rate
expected net benefit
safety regression rate
PolicySegmentLearningMemory
memory học theo segment cụ thể thay vì chỉ global context hash
3) FILE-BY-FILE
backend/app/models/policy_feature_snapshot.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyFeatureSnapshot(Base):
    __tablename__ = "policy_feature_snapshot"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    experiment_id = Column(UUID(as_uuid=True), ForeignKey("policy_experiment.id"), nullable=True, index=True)
    exposure_id = Column(UUID(as_uuid=True), ForeignKey("policy_experiment_exposure.id"), nullable=True, index=True)

    subject_key = Column(String(255), nullable=False, index=True)
    subject_type = Column(String(64), nullable=False, default="review_case")

    context_signature = Column(String(255), nullable=False, index=True)
    segment_key = Column(String(255), nullable=False, index=True)

    feature_vector_json = Column(JSON, nullable=False, default=dict)
    raw_context_json = Column(JSON, nullable=False, default=dict)
    feature_version = Column(String(64), nullable=False, default="v1")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
backend/app/models/policy_segment_learning_memory.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, Integer, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicySegmentLearningMemory(Base):
    __tablename__ = "policy_segment_learning_memory"
    __table_args__ = (
        UniqueConstraint("segment_memory_key", name="uq_policy_segment_learning_memory_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    segment_memory_key = Column(String(255), nullable=False, index=True)
    context_signature = Column(String(255), nullable=False, index=True)
    segment_key = Column(String(255), nullable=False, index=True)

    bundle_id = Column(String(255), nullable=False, index=True)
    arm_key = Column(String(255), nullable=False, index=True)

    sample_count = Column(Integer, nullable=False, default=0)
    win_count = Column(Integer, nullable=False, default=0)
    loss_count = Column(Integer, nullable=False, default=0)

    avg_net_benefit = Column(Float, nullable=False, default=0.0)
    avg_sla_delta = Column(Float, nullable=False, default=0.0)
    avg_churn_delta = Column(Float, nullable=False, default=0.0)
    avg_rebalance_delta = Column(Float, nullable=False, default=0.0)
    avg_cost_delta = Column(Float, nullable=False, default=0.0)

    confidence_score = Column(Float, nullable=False, default=0.0)
    metadata_json = Column(JSON, nullable=False, default=dict)

    last_observed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/models/policy_replay_evaluation.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, Integer, JSON, Enum, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyReplayEvaluationStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class PolicyReplayEvaluation(Base):
    __tablename__ = "policy_replay_evaluation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    evaluation_key = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    experiment_key = Column(String(255), nullable=True, index=True)
    status = Column(Enum(PolicyReplayEvaluationStatus), nullable=False, default=PolicyReplayEvaluationStatus.pending)

    replay_window_start = Column(DateTime, nullable=True)
    replay_window_end = Column(DateTime, nullable=True)
    targeting_filters = Column(JSON, nullable=False, default=dict)
    replay_config_json = Column(JSON, nullable=False, default=dict)

    total_events = Column(Integer, nullable=False, default=0)
    matched_events = Column(Integer, nullable=False, default=0)
    expected_net_benefit = Column(Float, nullable=True)
    expected_win_rate = Column(Float, nullable=True)
    expected_regret = Column(Float, nullable=True)
    regression_risk_rate = Column(Float, nullable=True)

    summary_json = Column(JSON, nullable=False, default=dict)
    created_by = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/repositories/policy_feature_snapshot_repository.py
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_feature_snapshot import PolicyFeatureSnapshot


class PolicyFeatureSnapshotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, snapshot: PolicyFeatureSnapshot) -> PolicyFeatureSnapshot:
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def get(self, snapshot_id: UUID) -> Optional[PolicyFeatureSnapshot]:
        return (
            self.db.query(PolicyFeatureSnapshot)
            .filter(PolicyFeatureSnapshot.id == snapshot_id)
            .one_or_none()
        )

    def list_by_experiment_id(self, experiment_id: UUID) -> Sequence[PolicyFeatureSnapshot]:
        return (
            self.db.query(PolicyFeatureSnapshot)
            .filter(PolicyFeatureSnapshot.experiment_id == experiment_id)
            .all()
        )

    def list_by_segment_key(self, segment_key: str) -> Sequence[PolicyFeatureSnapshot]:
        return (
            self.db.query(PolicyFeatureSnapshot)
            .filter(PolicyFeatureSnapshot.segment_key == segment_key)
            .all()
        )
backend/app/repositories/policy_segment_learning_memory_repository.py
from __future__ import annotations

from typing import Optional, Sequence
from sqlalchemy.orm import Session

from app.models.policy_segment_learning_memory import PolicySegmentLearningMemory


class PolicySegmentLearningMemoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_segment_memory_key(self, segment_memory_key: str) -> Optional[PolicySegmentLearningMemory]:
        return (
            self.db.query(PolicySegmentLearningMemory)
            .filter(PolicySegmentLearningMemory.segment_memory_key == segment_memory_key)
            .one_or_none()
        )

    def list_by_segment_key(self, segment_key: str) -> Sequence[PolicySegmentLearningMemory]:
        return (
            self.db.query(PolicySegmentLearningMemory)
            .filter(PolicySegmentLearningMemory.segment_key == segment_key)
            .order_by(PolicySegmentLearningMemory.avg_net_benefit.desc())
            .all()
        )

    def create(self, memory: PolicySegmentLearningMemory) -> PolicySegmentLearningMemory:
        self.db.add(memory)
        self.db.flush()
        return memory

    def save(self, memory: PolicySegmentLearningMemory) -> PolicySegmentLearningMemory:
        self.db.add(memory)
        self.db.flush()
        return memory
backend/app/repositories/policy_replay_evaluation_repository.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_replay_evaluation import PolicyReplayEvaluation


class PolicyReplayEvaluationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, evaluation: PolicyReplayEvaluation) -> PolicyReplayEvaluation:
        self.db.add(evaluation)
        self.db.flush()
        return evaluation

    def get(self, evaluation_id: UUID) -> Optional[PolicyReplayEvaluation]:
        return (
            self.db.query(PolicyReplayEvaluation)
            .filter(PolicyReplayEvaluation.id == evaluation_id)
            .one_or_none()
        )

    def get_by_key(self, evaluation_key: str) -> Optional[PolicyReplayEvaluation]:
        return (
            self.db.query(PolicyReplayEvaluation)
            .filter(PolicyReplayEvaluation.evaluation_key == evaluation_key)
            .one_or_none()
        )

    def save(self, evaluation: PolicyReplayEvaluation) -> PolicyReplayEvaluation:
        self.db.add(evaluation)
        self.db.flush()
        return evaluation
backend/app/schemas/policy_contextual_bandit.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PolicyReplayEvaluationCreateRequest(BaseModel):
    evaluation_key: str
    name: str
    description: Optional[str] = None
    experiment_key: Optional[str] = None
    replay_window_start: Optional[datetime] = None
    replay_window_end: Optional[datetime] = None
    targeting_filters: Dict[str, Any] = Field(default_factory=dict)
    replay_config_json: Dict[str, Any] = Field(default_factory=dict)


class PolicyContextualAssignPreviewRequest(BaseModel):
    experiment_key: str
    subject_key: str
    subject_type: str = "review_case"
    context_json: Dict[str, Any] = Field(default_factory=dict)
backend/app/services/policy_feature_store_service.py
from __future__ import annotations

from typing import Any, Dict


class PolicyFeatureStoreService:
    """
    Normalize context -> feature vector.
    Repo thật có thể nối với:
    - reviewer profile
    - queue load
    - project risk profile
    - historical SLA health
    - staffing pressure
    - conflict propensity
    """

    def build_feature_vector(self, context: Dict[str, Any]) -> Dict[str, Any]:
        queue = context.get("queue", "unknown")
        severity = context.get("severity", "unknown")
        shift = context.get("shift", "unknown")
        project = context.get("project", "unknown")
        reviewer_bucket = context.get("reviewer_bucket", "unknown")
        review_case_bucket = context.get("review_case_bucket", "unknown")

        return {
            "queue": queue,
            "severity": severity,
            "shift": shift,
            "project": project,
            "reviewer_bucket": reviewer_bucket,
            "review_case_bucket": review_case_bucket,
            "queue_severity": f"{queue}:{severity}",
            "queue_shift": f"{queue}:{shift}",
            "project_severity": f"{project}:{severity}",
        }

    def build_segment_key(self, feature_vector: Dict[str, Any]) -> str:
        return "|".join(
            [
                f"q={feature_vector.get('queue', 'unknown')}",
                f"s={feature_vector.get('severity', 'unknown')}",
                f"sh={feature_vector.get('shift', 'unknown')}",
                f"p={feature_vector.get('project', 'unknown')}",
            ]
        )
backend/app/services/policy_contextual_prior_service.py
from __future__ import annotations

from typing import Dict, Tuple

from app.repositories.policy_segment_learning_memory_repository import PolicySegmentLearningMemoryRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository


class PolicyContextualPriorService:
    def __init__(
        self,
        segment_memory_repo: PolicySegmentLearningMemoryRepository,
        global_memory_repo: PolicyLearningMemoryRepository,
    ) -> None:
        self.segment_memory_repo = segment_memory_repo
        self.global_memory_repo = global_memory_repo

    def get_prior_bonus(
        self,
        context_signature: str,
        segment_key: str,
        bundle_id: str,
        arm_key: str,
    ) -> Tuple[float, Dict]:
        segment_memory_key = f"{segment_key}:{bundle_id}:{arm_key}"
        global_memory_key = f"{context_signature}:{bundle_id}:{arm_key}"

        segment_memory = self.segment_memory_repo.get_by_segment_memory_key(segment_memory_key)
        global_memory = self.global_memory_repo.get_by_memory_key(global_memory_key)

        bonus = 0.0
        debug = {
            "segment_bonus": 0.0,
            "global_bonus": 0.0,
        }

        if segment_memory is not None and segment_memory.sample_count > 0:
            segment_bonus = min(segment_memory.avg_net_benefit * 0.20, 5.0)
            bonus += segment_bonus
            debug["segment_bonus"] = segment_bonus

        if global_memory is not None and global_memory.sample_count > 0:
            global_bonus = min(global_memory.avg_net_benefit * 0.10, 3.0)
            bonus += global_bonus
            debug["global_bonus"] = global_bonus

        return bonus, debug
backend/app/services/policy_contextual_bandit_service.py
from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

from app.models.policy_experiment_arm import PolicyExperimentArm
from app.services.policy_contextual_prior_service import PolicyContextualPriorService


class PolicyContextualBanditService:
    """
    Score = Thompson sample + contextual prior bonus.
    """

    def __init__(self, contextual_prior_service: PolicyContextualPriorService) -> None:
        self.contextual_prior_service = contextual_prior_service

    def choose_arm(
        self,
        arms: List[PolicyExperimentArm],
        context_signature: str,
        segment_key: str,
    ) -> Tuple[PolicyExperimentArm, Dict[str, Any]]:
        if not arms:
            raise ValueError("No active experiment arms available")

        ranked = []

        for arm in arms:
            sample = random.betavariate(max(arm.alpha, 0.001), max(arm.beta, 0.001))
            prior_bonus, debug_prior = self.contextual_prior_service.get_prior_bonus(
                context_signature=context_signature,
                segment_key=segment_key,
                bundle_id=arm.bundle_id,
                arm_key=arm.arm_key,
            )
            final_score = (sample * arm.current_weight) + prior_bonus
            ranked.append(
                {
                    "arm": arm,
                    "thompson_sample": sample,
                    "prior_bonus": prior_bonus,
                    "final_score": final_score,
                    "debug_prior": debug_prior,
                }
            )

        ranked.sort(key=lambda item: item["final_score"], reverse=True)
        winner = ranked[0]

        return winner["arm"], {
            "selected_arm_key": winner["arm"].arm_key,
            "selected_bundle_id": winner["arm"].bundle_id,
            "selected_score": winner["final_score"],
            "ranking": [
                {
                    "arm_key": item["arm"].arm_key,
                    "bundle_id": item["arm"].bundle_id,
                    "thompson_sample": item["thompson_sample"],
                    "prior_bonus": item["prior_bonus"],
                    "final_score": item["final_score"],
                    "debug_prior": item["debug_prior"],
                }
                for item in ranked
            ],
        }
backend/app/services/policy_feature_snapshot_service.py
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from app.models.policy_feature_snapshot import PolicyFeatureSnapshot
from app.repositories.policy_feature_snapshot_repository import PolicyFeatureSnapshotRepository
from app.services.policy_feature_store_service import PolicyFeatureStoreService
from app.services.policy_context_signature_service import PolicyContextSignatureService


class PolicyFeatureSnapshotService:
    def __init__(
        self,
        snapshot_repo: PolicyFeatureSnapshotRepository,
        feature_store_service: PolicyFeatureStoreService,
        context_signature_service: PolicyContextSignatureService,
    ) -> None:
        self.snapshot_repo = snapshot_repo
        self.feature_store_service = feature_store_service
        self.context_signature_service = context_signature_service

    def create_snapshot(
        self,
        subject_key: str,
        subject_type: str,
        raw_context_json: Dict[str, Any],
        experiment_id: Optional[UUID] = None,
        exposure_id: Optional[UUID] = None,
    ) -> PolicyFeatureSnapshot:
        feature_vector = self.feature_store_service.build_feature_vector(raw_context_json)
        context_signature = self.context_signature_service.build_context_signature(raw_context_json)
        segment_key = self.feature_store_service.build_segment_key(feature_vector)

        snapshot = PolicyFeatureSnapshot(
            experiment_id=experiment_id,
            exposure_id=exposure_id,
            subject_key=subject_key,
            subject_type=subject_type,
            context_signature=context_signature,
            segment_key=segment_key,
            feature_vector_json=feature_vector,
            raw_context_json=raw_context_json,
            feature_version="v1",
        )
        return self.snapshot_repo.create(snapshot)
backend/app/services/policy_segment_learning_memory_service.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.policy_segment_learning_memory import PolicySegmentLearningMemory
from app.repositories.policy_segment_learning_memory_repository import PolicySegmentLearningMemoryRepository


class PolicySegmentLearningMemoryService:
    def __init__(self, repo: PolicySegmentLearningMemoryRepository) -> None:
        self.repo = repo

    def update_memory(
        self,
        segment_key: str,
        context_signature: str,
        bundle_id: str,
        arm_key: str,
        success_label: bool,
        net_benefit_score: float,
        sla_delta: Optional[float],
        churn_delta: Optional[float],
        rebalance_delta: Optional[float],
        cost_delta: Optional[float],
    ) -> PolicySegmentLearningMemory:
        segment_memory_key = f"{segment_key}:{bundle_id}:{arm_key}"
        memory = self.repo.get_by_segment_memory_key(segment_memory_key)

        if memory is None:
            memory = PolicySegmentLearningMemory(
                segment_memory_key=segment_memory_key,
                context_signature=context_signature,
                segment_key=segment_key,
                bundle_id=bundle_id,
                arm_key=arm_key,
            )
            self.repo.create(memory)

        prev_n = memory.sample_count
        new_n = prev_n + 1

        def rolling_avg(old: float, val: float) -> float:
            return ((old * prev_n) + val) / new_n

        memory.sample_count = new_n
        if success_label:
            memory.win_count += 1
        else:
            memory.loss_count += 1

        memory.avg_net_benefit = rolling_avg(memory.avg_net_benefit, net_benefit_score)
        memory.avg_sla_delta = rolling_avg(memory.avg_sla_delta, float(sla_delta or 0.0))
        memory.avg_churn_delta = rolling_avg(memory.avg_churn_delta, float(churn_delta or 0.0))
        memory.avg_rebalance_delta = rolling_avg(memory.avg_rebalance_delta, float(rebalance_delta or 0.0))
        memory.avg_cost_delta = rolling_avg(memory.avg_cost_delta, float(cost_delta or 0.0))
        memory.confidence_score = min(new_n / 100.0, 1.0)
        memory.last_observed_at = datetime.utcnow()

        return self.repo.save(memory)
backend/app/services/policy_contextual_exposure_assignment_service.py
from __future__ import annotations

from typing import Any, Dict

from app.models.policy_experiment_exposure import PolicyExperimentExposure
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_experiment_exposure_repository import PolicyExperimentExposureRepository
from app.repositories.policy_feature_snapshot_repository import PolicyFeatureSnapshotRepository
from app.repositories.policy_segment_learning_memory_repository import PolicySegmentLearningMemoryRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository
from app.services.policy_context_signature_service import PolicyContextSignatureService
from app.services.policy_feature_store_service import PolicyFeatureStoreService
from app.services.policy_feature_snapshot_service import PolicyFeatureSnapshotService
from app.services.policy_contextual_prior_service import PolicyContextualPriorService
from app.services.policy_contextual_bandit_service import PolicyContextualBanditService


class PolicyContextualExposureAssignmentService:
    def __init__(
        self,
        experiment_repo: PolicyExperimentRepository,
        arm_repo: PolicyExperimentArmRepository,
        exposure_repo: PolicyExperimentExposureRepository,
        feature_snapshot_repo: PolicyFeatureSnapshotRepository,
        segment_memory_repo: PolicySegmentLearningMemoryRepository,
        global_memory_repo: PolicyLearningMemoryRepository,
        context_signature_service: PolicyContextSignatureService,
        feature_store_service: PolicyFeatureStoreService,
    ) -> None:
        self.experiment_repo = experiment_repo
        self.arm_repo = arm_repo
        self.exposure_repo = exposure_repo
        self.context_signature_service = context_signature_service
        self.feature_store_service = feature_store_service

        self.feature_snapshot_service = PolicyFeatureSnapshotService(
            snapshot_repo=feature_snapshot_repo,
            feature_store_service=feature_store_service,
            context_signature_service=context_signature_service,
        )
        prior_service = PolicyContextualPriorService(
            segment_memory_repo=segment_memory_repo,
            global_memory_repo=global_memory_repo,
        )
        self.contextual_bandit_service = PolicyContextualBanditService(prior_service)

    def assign(
        self,
        experiment_key: str,
        subject_key: str,
        subject_type: str,
        context_json: Dict[str, Any],
    ) -> Dict[str, Any]:
        experiment = self.experiment_repo.get_by_key(experiment_key)
        if experiment is None:
            raise ValueError(f"Experiment not found: {experiment_key}")

        existing = self.exposure_repo.get_by_subject_key(experiment.id, subject_key)
        if existing is not None:
            return {
                "exposure": existing,
                "selection_debug": {"reason": "existing_exposure_reused"},
                "feature_snapshot": None,
            }

        active_arms = list(self.arm_repo.list_active_by_experiment_id(experiment.id))
        context_signature = self.context_signature_service.build_context_signature(context_json)
        feature_vector = self.feature_store_service.build_feature_vector(context_json)
        segment_key = self.feature_store_service.build_segment_key(feature_vector)

        chosen_arm, selection_debug = self.contextual_bandit_service.choose_arm(
            arms=active_arms,
            context_signature=context_signature,
            segment_key=segment_key,
        )

        exposure = PolicyExperimentExposure(
            experiment_id=experiment.id,
            arm_id=chosen_arm.id,
            subject_key=subject_key,
            subject_type=subject_type,
            cohort_key=segment_key,
            context_hash=context_signature,
            context_json=context_json,
            allocation_score=selection_debug["selected_score"],
        )
        exposure = self.exposure_repo.create(exposure)

        snapshot = self.feature_snapshot_service.create_snapshot(
            subject_key=subject_key,
            subject_type=subject_type,
            raw_context_json=context_json,
            experiment_id=experiment.id,
            exposure_id=exposure.id,
        )

        return {
            "exposure": exposure,
            "selection_debug": selection_debug,
            "feature_snapshot": snapshot,
        }
backend/app/services/policy_contextual_outcome_learning_service.py
from __future__ import annotations

from app.repositories.policy_experiment_exposure_repository import PolicyExperimentExposureRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_outcome_observation_repository import PolicyOutcomeObservationRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository
from app.repositories.policy_segment_learning_memory_repository import PolicySegmentLearningMemoryRepository
from app.repositories.policy_feature_snapshot_repository import PolicyFeatureSnapshotRepository
from app.services.policy_variant_scoring_service import PolicyVariantScoringService
from app.services.policy_bandit_allocator_service import PolicyBanditAllocatorService
from app.services.policy_cross_bundle_learning_memory_service import PolicyCrossBundleLearningMemoryService
from app.services.policy_segment_learning_memory_service import PolicySegmentLearningMemoryService
from app.models.policy_outcome_observation import PolicyOutcomeObservation


class PolicyContextualOutcomeLearningService:
    def __init__(
        self,
        exposure_repo: PolicyExperimentExposureRepository,
        arm_repo: PolicyExperimentArmRepository,
        observation_repo: PolicyOutcomeObservationRepository,
        global_memory_repo: PolicyLearningMemoryRepository,
        segment_memory_repo: PolicySegmentLearningMemoryRepository,
        feature_snapshot_repo: PolicyFeatureSnapshotRepository,
        scoring_service: PolicyVariantScoringService,
        bandit_allocator_service: PolicyBanditAllocatorService,
    ) -> None:
        self.exposure_repo = exposure_repo
        self.arm_repo = arm_repo
        self.observation_repo = observation_repo
        self.feature_snapshot_repo = feature_snapshot_repo
        self.scoring_service = scoring_service
        self.bandit_allocator_service = bandit_allocator_service
        self.global_memory_service = PolicyCrossBundleLearningMemoryService(global_memory_repo)
        self.segment_memory_service = PolicySegmentLearningMemoryService(segment_memory_repo)

    def observe(
        self,
        exposure_id,
        sla_breach_delta,
        churn_delta,
        rework_delta,
        conflict_delta,
        rebalance_success_delta,
        execution_cost_delta,
        control_baseline_json,
        pre_rollout_baseline_json,
        diff_in_diff_json,
        metadata_json,
    ) -> PolicyOutcomeObservation:
        exposure = self.exposure_repo.get(exposure_id)
        if exposure is None:
            raise ValueError(f"Exposure not found: {exposure_id}")

        arm = self.arm_repo.get(exposure.arm_id)
        if arm is None:
            raise ValueError(f"Arm not found for exposure: {exposure.arm_id}")

        snapshots = self.feature_snapshot_repo.list_by_experiment_id(exposure.experiment_id)
        snapshot = next((s for s in snapshots if s.exposure_id == exposure.id), None)
        segment_key = snapshot.segment_key if snapshot else "unknown"

        net_benefit_score = self.scoring_service.compute_net_benefit_score(
            sla_breach_delta=sla_breach_delta,
            churn_delta=churn_delta,
            rework_delta=rework_delta,
            conflict_delta=conflict_delta,
            rebalance_success_delta=rebalance_success_delta,
            execution_cost_delta=execution_cost_delta,
        )
        success_label = self.scoring_service.to_success_label(net_benefit_score)

        observation = PolicyOutcomeObservation(
            exposure_id=exposure.id,
            sla_breach_delta=sla_breach_delta,
            churn_delta=churn_delta,
            rework_delta=rework_delta,
            conflict_delta=conflict_delta,
            rebalance_success_delta=rebalance_success_delta,
            execution_cost_delta=execution_cost_delta,
            net_benefit_score=net_benefit_score,
            success_label=success_label,
            control_baseline_json=control_baseline_json,
            pre_rollout_baseline_json=pre_rollout_baseline_json,
            diff_in_diff_json=diff_in_diff_json,
            metadata_json=metadata_json,
        )
        self.observation_repo.create(observation)

        self.bandit_allocator_service.update_posterior(arm, success_label)
        arm.latest_score = net_benefit_score
        self.arm_repo.save(arm)

        self.global_memory_service.update_memory(
            context_signature=exposure.context_hash or "unknown",
            bundle_id=arm.bundle_id,
            arm_key=arm.arm_key,
            success_label=success_label,
            net_benefit_score=net_benefit_score,
            sla_delta=sla_breach_delta,
            churn_delta=churn_delta,
            rebalance_delta=rebalance_success_delta,
            cost_delta=execution_cost_delta,
        )

        self.segment_memory_service.update_memory(
            segment_key=segment_key,
            context_signature=exposure.context_hash or "unknown",
            bundle_id=arm.bundle_id,
            arm_key=arm.arm_key,
            success_label=success_label,
            net_benefit_score=net_benefit_score,
            sla_delta=sla_breach_delta,
            churn_delta=churn_delta,
            rebalance_delta=rebalance_success_delta,
            cost_delta=execution_cost_delta,
        )

        return observation
backend/app/services/policy_replay_evaluator_service.py
from __future__ import annotations

from typing import Any, Dict, List

from app.models.policy_replay_evaluation import PolicyReplayEvaluation, PolicyReplayEvaluationStatus
from app.models.policy_experiment_arm import PolicyExperimentArm
from app.repositories.policy_replay_evaluation_repository import PolicyReplayEvaluationRepository
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_segment_learning_memory_repository import PolicySegmentLearningMemoryRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository
from app.services.policy_feature_store_service import PolicyFeatureStoreService
from app.services.policy_context_signature_service import PolicyContextSignatureService
from app.services.policy_contextual_prior_service import PolicyContextualPriorService
from app.services.policy_contextual_bandit_service import PolicyContextualBanditService


class PolicyReplayEvaluatorService:
    """
    Bản khung offline replay.
    Repo thật nên feed historical items từ:
    - historical queue decisions
    - case outcomes
    - staffing events
    - SLA facts
    """

    def __init__(
        self,
        replay_repo: PolicyReplayEvaluationRepository,
        experiment_repo: PolicyExperimentRepository,
        arm_repo: PolicyExperimentArmRepository,
        segment_memory_repo: PolicySegmentLearningMemoryRepository,
        global_memory_repo: PolicyLearningMemoryRepository,
        feature_store_service: PolicyFeatureStoreService,
        context_signature_service: PolicyContextSignatureService,
    ) -> None:
        self.replay_repo = replay_repo
        self.experiment_repo = experiment_repo
        self.arm_repo = arm_repo
        self.feature_store_service = feature_store_service
        self.context_signature_service = context_signature_service

        prior_service = PolicyContextualPriorService(
            segment_memory_repo=segment_memory_repo,
            global_memory_repo=global_memory_repo,
        )
        self.contextual_bandit_service = PolicyContextualBanditService(prior_service)

    def create_evaluation(
        self,
        evaluation_key: str,
        name: str,
        description: str | None,
        experiment_key: str | None,
        replay_window_start,
        replay_window_end,
        targeting_filters: Dict[str, Any],
        replay_config_json: Dict[str, Any],
        created_by: str,
    ) -> PolicyReplayEvaluation:
        evaluation = PolicyReplayEvaluation(
            evaluation_key=evaluation_key,
            name=name,
            description=description,
            experiment_key=experiment_key,
            replay_window_start=replay_window_start,
            replay_window_end=replay_window_end,
            targeting_filters=targeting_filters,
            replay_config_json=replay_config_json,
            status=PolicyReplayEvaluationStatus.pending,
            created_by=created_by,
        )
        return self.replay_repo.create(evaluation)

    def run_replay(
        self,
        evaluation_key: str,
        historical_events: List[Dict[str, Any]],
    ) -> PolicyReplayEvaluation:
        evaluation = self.replay_repo.get_by_key(evaluation_key)
        if evaluation is None:
            raise ValueError(f"Replay evaluation not found: {evaluation_key}")

        evaluation.status = PolicyReplayEvaluationStatus.running
        self.replay_repo.save(evaluation)

        experiment = None
        arms: List[PolicyExperimentArm] = []
        if evaluation.experiment_key:
            experiment = self.experiment_repo.get_by_key(evaluation.experiment_key)
            if experiment is not None:
                arms = list(self.arm_repo.list_active_by_experiment_id(experiment.id))

        total_events = len(historical_events)
        matched_events = 0
        total_net_benefit = 0.0
        total_success = 0
        total_regret = 0.0
        regression_count = 0

        replay_rows = []

        for event in historical_events:
            context_json = event.get("context_json", {})
            observed_arm_key = event.get("observed_arm_key")
            observed_net_benefit = float(event.get("observed_net_benefit", 0.0))
            realized_regression = bool(event.get("realized_regression", False))

            if not arms:
                continue

            context_signature = self.context_signature_service.build_context_signature(context_json)
            feature_vector = self.feature_store_service.build_feature_vector(context_json)
            segment_key = self.feature_store_service.build_segment_key(feature_vector)

            chosen_arm, debug = self.contextual_bandit_service.choose_arm(
                arms=arms,
                context_signature=context_signature,
                segment_key=segment_key,
            )
            matched = chosen_arm.arm_key == observed_arm_key

            matched_events += 1 if matched else 0
            total_net_benefit += observed_net_benefit if matched else 0.0
            total_success += 1 if observed_net_benefit >= 0 else 0
            regression_count += 1 if realized_regression else 0

            best_known = max(observed_net_benefit, 0.0)
            regret = max(best_known - (observed_net_benefit if matched else 0.0), 0.0)
            total_regret += regret

            replay_rows.append(
                {
                    "subject_key": event.get("subject_key"),
                    "observed_arm_key": observed_arm_key,
                    "replayed_arm_key": chosen_arm.arm_key,
                    "matched": matched,
                    "observed_net_benefit": observed_net_benefit,
                    "regret": regret,
                    "selection_debug": debug,
                }
            )

        evaluation.total_events = total_events
        evaluation.matched_events = matched_events
        evaluation.expected_net_benefit = (total_net_benefit / matched_events) if matched_events else 0.0
        evaluation.expected_win_rate = (total_success / matched_events) if matched_events else 0.0
        evaluation.expected_regret = (total_regret / matched_events) if matched_events else 0.0
        evaluation.regression_risk_rate = (regression_count / total_events) if total_events else 0.0
        evaluation.summary_json = {
            "rows": replay_rows[:500],
            "truncated": len(replay_rows) > 500,
        }
        evaluation.status = PolicyReplayEvaluationStatus.completed

        return self.replay_repo.save(evaluation)
backend/app/api/policy_contextual_bandit.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_actor_id
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_experiment_exposure_repository import PolicyExperimentExposureRepository
from app.repositories.policy_feature_snapshot_repository import PolicyFeatureSnapshotRepository
from app.repositories.policy_segment_learning_memory_repository import PolicySegmentLearningMemoryRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository
from app.repositories.policy_outcome_observation_repository import PolicyOutcomeObservationRepository
from app.repositories.policy_replay_evaluation_repository import PolicyReplayEvaluationRepository
from app.schemas.policy_contextual_bandit import (
    PolicyReplayEvaluationCreateRequest,
    PolicyContextualAssignPreviewRequest,
)
from app.schemas.policy_experiment import PolicyOutcomeObservationCreateRequest
from app.services.policy_context_signature_service import PolicyContextSignatureService
from app.services.policy_feature_store_service import PolicyFeatureStoreService
from app.services.policy_contextual_exposure_assignment_service import PolicyContextualExposureAssignmentService
from app.services.policy_contextual_outcome_learning_service import PolicyContextualOutcomeLearningService
from app.services.policy_variant_scoring_service import PolicyVariantScoringService
from app.services.policy_bandit_allocator_service import PolicyBanditAllocatorService
from app.services.policy_replay_evaluator_service import PolicyReplayEvaluatorService

router = APIRouter(prefix="/policy-contextual-bandit", tags=["policy-contextual-bandit"])


@router.post("/assign")
def assign_contextual_arm(
    payload: PolicyContextualAssignPreviewRequest,
    db: Session = Depends(get_db),
):
    service = PolicyContextualExposureAssignmentService(
        experiment_repo=PolicyExperimentRepository(db),
        arm_repo=PolicyExperimentArmRepository(db),
        exposure_repo=PolicyExperimentExposureRepository(db),
        feature_snapshot_repo=PolicyFeatureSnapshotRepository(db),
        segment_memory_repo=PolicySegmentLearningMemoryRepository(db),
        global_memory_repo=PolicyLearningMemoryRepository(db),
        context_signature_service=PolicyContextSignatureService(),
        feature_store_service=PolicyFeatureStoreService(),
    )

    try:
        result = service.assign(
            experiment_key=payload.experiment_key,
            subject_key=payload.subject_key,
            subject_type=payload.subject_type,
            context_json=payload.context_json,
        )
        db.commit()

        exposure = result["exposure"]
        snapshot = result["feature_snapshot"]
        return {
            "exposure_id": str(exposure.id),
            "experiment_id": str(exposure.experiment_id),
            "arm_id": str(exposure.arm_id),
            "cohort_key": exposure.cohort_key,
            "context_hash": exposure.context_hash,
            "allocation_score": exposure.allocation_score,
            "feature_snapshot_id": str(snapshot.id) if snapshot else None,
            "selection_debug": result["selection_debug"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/observe")
def observe_contextual_outcome(
    payload: PolicyOutcomeObservationCreateRequest,
    db: Session = Depends(get_db),
):
    service = PolicyContextualOutcomeLearningService(
        exposure_repo=PolicyExperimentExposureRepository(db),
        arm_repo=PolicyExperimentArmRepository(db),
        observation_repo=PolicyOutcomeObservationRepository(db),
        global_memory_repo=PolicyLearningMemoryRepository(db),
        segment_memory_repo=PolicySegmentLearningMemoryRepository(db),
        feature_snapshot_repo=PolicyFeatureSnapshotRepository(db),
        scoring_service=PolicyVariantScoringService(),
        bandit_allocator_service=PolicyBanditAllocatorService(),
    )

    try:
        observation = service.observe(
            exposure_id=payload.exposure_id,
            sla_breach_delta=payload.sla_breach_delta,
            churn_delta=payload.churn_delta,
            rework_delta=payload.rework_delta,
            conflict_delta=payload.conflict_delta,
            rebalance_success_delta=payload.rebalance_success_delta,
            execution_cost_delta=payload.execution_cost_delta,
            control_baseline_json=payload.control_baseline_json,
            pre_rollout_baseline_json=payload.pre_rollout_baseline_json,
            diff_in_diff_json=payload.diff_in_diff_json,
            metadata_json=payload.metadata_json,
        )
        db.commit()
        return {
            "observation_id": str(observation.id),
            "net_benefit_score": observation.net_benefit_score,
            "success_label": observation.success_label,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/replay")
def create_replay_evaluation(
    payload: PolicyReplayEvaluationCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicyReplayEvaluatorService(
        replay_repo=PolicyReplayEvaluationRepository(db),
        experiment_repo=PolicyExperimentRepository(db),
        arm_repo=PolicyExperimentArmRepository(db),
        segment_memory_repo=PolicySegmentLearningMemoryRepository(db),
        global_memory_repo=PolicyLearningMemoryRepository(db),
        feature_store_service=PolicyFeatureStoreService(),
        context_signature_service=PolicyContextSignatureService(),
    )

    evaluation = service.create_evaluation(
        evaluation_key=payload.evaluation_key,
        name=payload.name,
        description=payload.description,
        experiment_key=payload.experiment_key,
        replay_window_start=payload.replay_window_start,
        replay_window_end=payload.replay_window_end,
        targeting_filters=payload.targeting_filters,
        replay_config_json=payload.replay_config_json,
        created_by=actor_id,
    )
    db.commit()

    return {
        "evaluation_id": str(evaluation.id),
        "evaluation_key": evaluation.evaluation_key,
        "status": evaluation.status.value,
    }
backend/app/workers/policy_replay_evaluation_worker.py
from __future__ import annotations

from app.db.session import SessionLocal
from app.repositories.policy_replay_evaluation_repository import PolicyReplayEvaluationRepository
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_segment_learning_memory_repository import PolicySegmentLearningMemoryRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository
from app.services.policy_feature_store_service import PolicyFeatureStoreService
from app.services.policy_context_signature_service import PolicyContextSignatureService
from app.services.policy_replay_evaluator_service import PolicyReplayEvaluatorService


def run_policy_replay_evaluation(evaluation_key: str, historical_events: list[dict]) -> dict:
    db = SessionLocal()
    try:
        service = PolicyReplayEvaluatorService(
            replay_repo=PolicyReplayEvaluationRepository(db),
            experiment_repo=PolicyExperimentRepository(db),
            arm_repo=PolicyExperimentArmRepository(db),
            segment_memory_repo=PolicySegmentLearningMemoryRepository(db),
            global_memory_repo=PolicyLearningMemoryRepository(db),
            feature_store_service=PolicyFeatureStoreService(),
            context_signature_service=PolicyContextSignatureService(),
        )
        evaluation = service.run_replay(
            evaluation_key=evaluation_key,
            historical_events=historical_events,
        )
        db.commit()
        return {
            "evaluation_id": str(evaluation.id),
            "evaluation_key": evaluation.evaluation_key,
            "status": evaluation.status.value,
            "expected_net_benefit": evaluation.expected_net_benefit,
            "expected_win_rate": evaluation.expected_win_rate,
            "expected_regret": evaluation.expected_regret,
            "regression_risk_rate": evaluation.regression_risk_rate,
        }
    finally:
        db.close()
backend/alembic/versions/20260412_0031_contextual_bandit_feature_store_replay.py
"""contextual bandit feature store replay

Revision ID: 20260412_0031
Revises: 20260412_0030
Create Date: 2026-04-12 11:15:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260412_0031"
down_revision = "20260412_0030"
branch_labels = None
depends_on = None


policy_replay_evaluation_status_enum = sa.Enum(
    "pending",
    "running",
    "completed",
    "failed",
    name="policyreplayevaluationstatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    policy_replay_evaluation_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "policy_feature_snapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_experiment.id"), nullable=True),
        sa.Column("exposure_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_experiment_exposure.id"), nullable=True),
        sa.Column("subject_key", sa.String(length=255), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("context_signature", sa.String(length=255), nullable=False),
        sa.Column("segment_key", sa.String(length=255), nullable=False),
        sa.Column("feature_vector_json", sa.JSON(), nullable=False),
        sa.Column("raw_context_json", sa.JSON(), nullable=False),
        sa.Column("feature_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_feature_snapshot_experiment_id", "policy_feature_snapshot", ["experiment_id"], unique=False)
    op.create_index("ix_policy_feature_snapshot_exposure_id", "policy_feature_snapshot", ["exposure_id"], unique=False)
    op.create_index("ix_policy_feature_snapshot_subject_key", "policy_feature_snapshot", ["subject_key"], unique=False)
    op.create_index("ix_policy_feature_snapshot_context_signature", "policy_feature_snapshot", ["context_signature"], unique=False)
    op.create_index("ix_policy_feature_snapshot_segment_key", "policy_feature_snapshot", ["segment_key"], unique=False)

    op.create_table(
        "policy_segment_learning_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("segment_memory_key", sa.String(length=255), nullable=False),
        sa.Column("context_signature", sa.String(length=255), nullable=False),
        sa.Column("segment_key", sa.String(length=255), nullable=False),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("arm_key", sa.String(length=255), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("win_count", sa.Integer(), nullable=False),
        sa.Column("loss_count", sa.Integer(), nullable=False),
        sa.Column("avg_net_benefit", sa.Float(), nullable=False),
        sa.Column("avg_sla_delta", sa.Float(), nullable=False),
        sa.Column("avg_churn_delta", sa.Float(), nullable=False),
        sa.Column("avg_rebalance_delta", sa.Float(), nullable=False),
        sa.Column("avg_cost_delta", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("segment_memory_key", name="uq_policy_segment_learning_memory_key"),
    )
    op.create_index("ix_policy_segment_learning_memory_segment_memory_key", "policy_segment_learning_memory", ["segment_memory_key"], unique=True)
    op.create_index("ix_policy_segment_learning_memory_context_signature", "policy_segment_learning_memory", ["context_signature"], unique=False)
    op.create_index("ix_policy_segment_learning_memory_segment_key", "policy_segment_learning_memory", ["segment_key"], unique=False)
    op.create_index("ix_policy_segment_learning_memory_bundle_id", "policy_segment_learning_memory", ["bundle_id"], unique=False)
    op.create_index("ix_policy_segment_learning_memory_arm_key", "policy_segment_learning_memory", ["arm_key"], unique=False)

    op.create_table(
        "policy_replay_evaluation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("evaluation_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("experiment_key", sa.String(length=255), nullable=True),
        sa.Column("status", policy_replay_evaluation_status_enum, nullable=False),
        sa.Column("replay_window_start", sa.DateTime(), nullable=True),
        sa.Column("replay_window_end", sa.DateTime(), nullable=True),
        sa.Column("targeting_filters", sa.JSON(), nullable=False),
        sa.Column("replay_config_json", sa.JSON(), nullable=False),
        sa.Column("total_events", sa.Integer(), nullable=False),
        sa.Column("matched_events", sa.Integer(), nullable=False),
        sa.Column("expected_net_benefit", sa.Float(), nullable=True),
        sa.Column("expected_win_rate", sa.Float(), nullable=True),
        sa.Column("expected_regret", sa.Float(), nullable=True),
        sa.Column("regression_risk_rate", sa.Float(), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_replay_evaluation_evaluation_key", "policy_replay_evaluation", ["evaluation_key"], unique=True)
    op.create_index("ix_policy_replay_evaluation_experiment_key", "policy_replay_evaluation", ["experiment_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_policy_replay_evaluation_experiment_key", table_name="policy_replay_evaluation")
    op.drop_index("ix_policy_replay_evaluation_evaluation_key", table_name="policy_replay_evaluation")
    op.drop_table("policy_replay_evaluation")

    op.drop_index("ix_policy_segment_learning_memory_arm_key", table_name="policy_segment_learning_memory")
    op.drop_index("ix_policy_segment_learning_memory_bundle_id", table_name="policy_segment_learning_memory")
    op.drop_index("ix_policy_segment_learning_memory_segment_key", table_name="policy_segment_learning_memory")
    op.drop_index("ix_policy_segment_learning_memory_context_signature", table_name="policy_segment_learning_memory")
    op.drop_index("ix_policy_segment_learning_memory_segment_memory_key", table_name="policy_segment_learning_memory")
    op.drop_table("policy_segment_learning_memory")

    op.drop_index("ix_policy_feature_snapshot_segment_key", table_name="policy_feature_snapshot")
    op.drop_index("ix_policy_feature_snapshot_context_signature", table_name="policy_feature_snapshot")
    op.drop_index("ix_policy_feature_snapshot_subject_key", table_name="policy_feature_snapshot")
    op.drop_index("ix_policy_feature_snapshot_exposure_id", table_name="policy_feature_snapshot")
    op.drop_index("ix_policy_feature_snapshot_experiment_id", table_name="policy_feature_snapshot")
    op.drop_table("policy_feature_snapshot")

    bind = op.get_bind()
    policy_replay_evaluation_status_enum.drop(bind, checkfirst=True)
backend/tests/services/test_policy_feature_store_service.py
from app.services.policy_feature_store_service import PolicyFeatureStoreService


def test_build_feature_vector_and_segment_key():
    service = PolicyFeatureStoreService()

    features = service.build_feature_vector(
        {
            "queue": "fraud_review",
            "severity": "critical",
            "shift": "night",
            "project": "apollo",
            "reviewer_bucket": "r2",
            "review_case_bucket": "c7",
        }
    )
    segment_key = service.build_segment_key(features)

    assert features["queue_severity"] == "fraud_review:critical"
    assert "q=fraud_review" in segment_key
    assert "s=critical" in segment_key
backend/tests/services/test_policy_contextual_prior_service.py
from unittest.mock import Mock

from app.services.policy_contextual_prior_service import PolicyContextualPriorService


def test_get_prior_bonus_uses_segment_and_global_memory():
    segment_repo = Mock()
    global_repo = Mock()

    segment_repo.get_by_segment_memory_key.return_value = type(
        "SegmentMemory",
        (),
        {"sample_count": 20, "avg_net_benefit": 8.0},
    )()
    global_repo.get_by_memory_key.return_value = type(
        "GlobalMemory",
        (),
        {"sample_count": 50, "avg_net_benefit": 4.0},
    )()

    service = PolicyContextualPriorService(
        segment_memory_repo=segment_repo,
        global_memory_repo=global_repo,
    )

    bonus, debug = service.get_prior_bonus(
        context_signature="ctx-1",
        segment_key="seg-1",
        bundle_id="bundle-a",
        arm_key="arm-a",
    )

    assert bonus > 0
    assert debug["segment_bonus"] > 0
    assert debug["global_bonus"] > 0
backend/tests/services/test_policy_contextual_bandit_service.py
from unittest.mock import Mock

from app.models.policy_experiment_arm import PolicyExperimentArm
from app.services.policy_contextual_bandit_service import PolicyContextualBanditService


def test_choose_arm_returns_debug_ranking():
    prior_service = Mock()
    prior_service.get_prior_bonus.side_effect = [
        (1.0, {"segment_bonus": 1.0, "global_bonus": 0.0}),
        (0.1, {"segment_bonus": 0.1, "global_bonus": 0.0}),
    ]

    service = PolicyContextualBanditService(prior_service)

    arm_a = PolicyExperimentArm(
        arm_key="a",
        bundle_id="bundle-a",
        alpha=1.0,
        beta=1.0,
        current_weight=1.0,
    )
    arm_b = PolicyExperimentArm(
        arm_key="b",
        bundle_id="bundle-b",
        alpha=1.0,
        beta=1.0,
        current_weight=1.0,
    )

    selected, debug = service.choose_arm(
        arms=[arm_a, arm_b],
        context_signature="ctx",
        segment_key="seg",
    )

    assert selected.arm_key in {"a", "b"}
    assert len(debug["ranking"]) == 2
4) CÁCH NỐI ROUTER VÀO APP
Trong backend/app/main.py hoặc router registry:
from app.api.policy_contextual_bandit import router as policy_contextual_bandit_router

app.include_router(policy_contextual_bandit_router)
5) FLOW THỰC TẾ SAU PATCH NÀY
A. Contextual assign
Thay vì gọi assign global bandit cũ, repo thật có thể gọi:
POST /policy-contextual-bandit/assign
{
  "experiment_key": "bundle-routing-exp-001",
  "subject_key": "review-case-20260412-001",
  "subject_type": "review_case",
  "context_json": {
    "queue": "fraud_review",
    "severity": "critical",
    "shift": "night",
    "project": "apollo",
    "reviewer_bucket": "r2",
    "review_case_bucket": "c7"
  }
}
Hệ sẽ:
build feature vector
build segment key
lấy segment memory + global memory
cộng prior bonus vào Thompson sample
chọn arm theo context
B. Contextual observe
POST /policy-contextual-bandit/observe
Cách payload giống observe cũ.
Khác ở chỗ:
ngoài global learning memory
còn update thêm segment learning memory
C. Replay evaluator offline
tạo evaluation
POST /policy-contextual-bandit/replay
{
  "evaluation_key": "replay-fraud-night-001",
  "name": "Replay Fraud Critical Night",
  "description": "Replay contextual routing on historical fraud cases",
  "experiment_key": "bundle-routing-exp-001",
  "targeting_filters": {
    "queue": ["fraud_review"],
    "severity": ["critical"],
    "shift": ["night"]
  },
  "replay_config_json": {
    "mode": "off_policy_replay",
    "use_segment_memory": true
  }
}
worker replay
Worker thật có thể gọi:
run_policy_replay_evaluation(
    evaluation_key="replay-fraud-night-001",
    historical_events=[
        {
            "subject_key": "case-1",
            "context_json": {
                "queue": "fraud_review",
                "severity": "critical",
                "shift": "night",
                "project": "apollo",
                "reviewer_bucket": "r2",
                "review_case_bucket": "c7"
            },
            "observed_arm_key": "variant_a",
            "observed_net_benefit": 4.2,
            "realized_regression": False
        }
    ]
)
6) ĐIỂM MAP QUAN TRỌNG KHI DÁN VÀO REPO THẬT
A. Feature store thật
Hiện PolicyFeatureStoreService mới build feature từ context_json.
Repo thật nên map thêm từ:
reviewer performance profile
queue pressure
current staffing saturation
project risk tier
historical conflict likelihood
shift-specific SLA stress
execution complexity bucket
Tức là build_feature_vector(...) nên hút thêm từ DB/read models thay vì chỉ dựa vào request payload.
B. Replay data source thật
PolicyReplayEvaluatorService.run_replay(...) hiện nhận historical_events trực tiếp.
Repo thật nên nối với:
historical assignments
actual outcomes
audit trails
staffing events
SLA facts
Tức là thêm một repository như:
PolicyReplayDatasetRepository
HistoricalPolicyDecisionRepository
C. Off-policy evaluation thật
Bản này mới là replay khung đơn giản.
Repo thật nên nâng tiếp bằng:
inverse propensity scoring
doubly robust estimator
replay by matched cohort
windowed replay by queue/shift/project
counterfactual safety envelope
D. Segment key refinement
Hiện segment key gồm:
queue
severity
shift
project
Repo thật nên có thể thêm:
reviewer experience tier
queue load band
case complexity band
customer risk tier
governance sensitivity class
E. Memory decay / freshness
Hiện memory tăng đều.
Repo thật nên thêm:
recency decay
stale memory demotion
minimum freshness threshold
separate train/eval windows
7) KẾT QUẢ SAU PATCH NÀY
Sau phase này, hệ của bạn đi từ:
closed-loop policy delivery system
sang:
context-aware policy optimization system
Cụ thể hệ có:
A. Contextual arm selection
Không còn phát policy theo một bandit chung. Hệ chọn arm theo context thật.
B. Policy feature store
Có lớp chuẩn hóa feature để policy decision không còn mù ngữ cảnh.
C. Segment learning memory
Biết policy nào thắng trong segment nào, thay vì chỉ biết thắng toàn cục.
D. Offline replay evaluator
Có thể test policy trên dữ liệu lịch sử trước khi rollout thật.
E. Stronger policy memory
Không chỉ “bundle nào tốt”, mà là “bundle nào tốt trong bối cảnh nào”.
bản PHASE 3 — OFF-POLICY ESTIMATION + SAFETY ENVELOPE SIMULATOR + POLICY PROMOTION COMMITTEE theo đúng kiểu full code file-by-file paste-ready.
Phase này nâng hệ từ:
replay offline
contextual bandit
segment memory
sang:
counterfactual estimation nghiêm túc hơn
pre-promotion safety simulation
committee-based promotion decision
auto-reject policy uplift ảo nhưng risk cao
promotion decision ở mức governance-grade
1) HỆ SẼ CÓ THÊM NHỮNG GÌ
Thêm 4 khối lớn:
Off-policy estimator
ước lượng expected uplift bằng:
direct method
IPS
doubly robust
Safety envelope simulator
simulate rollout dưới các ngưỡng:
SLA regression
churn/rework/conflict regression
cost overrun
rebalance degradation
Promotion committee
không promote chỉ vì bandit winner
cần qua committee decision:
estimated uplift
replay evidence
safety score
regression risk
governance veto
Promotion gate outcome
approved / rejected / manual_review
emit rationale rõ ràng
có audit-ready decision trail
2) FILE-BY-FILE
backend/app/models/policy_off_policy_evaluation.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, Integer, JSON, Enum, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyOffPolicyEvaluationStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class PolicyOffPolicyEvaluation(Base):
    __tablename__ = "policy_off_policy_evaluation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    evaluation_key = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    experiment_key = Column(String(255), nullable=True, index=True)
    status = Column(Enum(PolicyOffPolicyEvaluationStatus), nullable=False, default=PolicyOffPolicyEvaluationStatus.pending)

    method = Column(String(64), nullable=False, default="doubly_robust")
    targeting_filters = Column(JSON, nullable=False, default=dict)
    config_json = Column(JSON, nullable=False, default=dict)

    total_samples = Column(Integer, nullable=False, default=0)
    matched_samples = Column(Integer, nullable=False, default=0)

    direct_method_estimate = Column(Float, nullable=True)
    ips_estimate = Column(Float, nullable=True)
    doubly_robust_estimate = Column(Float, nullable=True)
    regret_estimate = Column(Float, nullable=True)
    regression_risk_rate = Column(Float, nullable=True)

    summary_json = Column(JSON, nullable=False, default=dict)
    created_by = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/models/policy_safety_simulation.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, JSON, Enum, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicySafetySimulationStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class PolicySafetySimulation(Base):
    __tablename__ = "policy_safety_simulation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    simulation_key = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    experiment_key = Column(String(255), nullable=True, index=True)
    bundle_id = Column(String(255), nullable=False, index=True)
    arm_key = Column(String(255), nullable=False, index=True)

    status = Column(Enum(PolicySafetySimulationStatus), nullable=False, default=PolicySafetySimulationStatus.pending)
    config_json = Column(JSON, nullable=False, default=dict)

    sla_regression_probability = Column(Float, nullable=True)
    churn_regression_probability = Column(Float, nullable=True)
    rework_regression_probability = Column(Float, nullable=True)
    rebalance_degradation_probability = Column(Float, nullable=True)
    cost_overrun_probability = Column(Float, nullable=True)

    safety_score = Column(Float, nullable=True)
    within_envelope = Column(Boolean, nullable=True)

    summary_json = Column(JSON, nullable=False, default=dict)
    created_by = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/models/policy_promotion_committee_decision.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, JSON, Enum, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyPromotionCommitteeDecisionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    manual_review = "manual_review"


class PolicyPromotionCommitteeDecision(Base):
    __tablename__ = "policy_promotion_committee_decision"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    decision_key = Column(String(255), nullable=False, unique=True, index=True)
    experiment_key = Column(String(255), nullable=True, index=True)
    bundle_id = Column(String(255), nullable=False, index=True)
    arm_key = Column(String(255), nullable=False, index=True)

    status = Column(Enum(PolicyPromotionCommitteeDecisionStatus), nullable=False, default=PolicyPromotionCommitteeDecisionStatus.pending)

    estimated_uplift_score = Column(Float, nullable=True)
    replay_confidence_score = Column(Float, nullable=True)
    safety_score = Column(Float, nullable=True)
    regression_risk_score = Column(Float, nullable=True)
    governance_score = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)

    auto_rejected = Column(Boolean, nullable=False, default=False)
    requires_manual_review = Column(Boolean, nullable=False, default=False)

    rationale_json = Column(JSON, nullable=False, default=dict)
    committee_votes_json = Column(JSON, nullable=False, default=dict)
    created_by = Column(String(255), nullable=True)
    decided_by = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/repositories/policy_off_policy_evaluation_repository.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_off_policy_evaluation import PolicyOffPolicyEvaluation


class PolicyOffPolicyEvaluationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, model: PolicyOffPolicyEvaluation) -> PolicyOffPolicyEvaluation:
        self.db.add(model)
        self.db.flush()
        return model

    def get(self, evaluation_id: UUID) -> Optional[PolicyOffPolicyEvaluation]:
        return (
            self.db.query(PolicyOffPolicyEvaluation)
            .filter(PolicyOffPolicyEvaluation.id == evaluation_id)
            .one_or_none()
        )

    def get_by_key(self, evaluation_key: str) -> Optional[PolicyOffPolicyEvaluation]:
        return (
            self.db.query(PolicyOffPolicyEvaluation)
            .filter(PolicyOffPolicyEvaluation.evaluation_key == evaluation_key)
            .one_or_none()
        )

    def save(self, model: PolicyOffPolicyEvaluation) -> PolicyOffPolicyEvaluation:
        self.db.add(model)
        self.db.flush()
        return model
backend/app/repositories/policy_safety_simulation_repository.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_safety_simulation import PolicySafetySimulation


class PolicySafetySimulationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, model: PolicySafetySimulation) -> PolicySafetySimulation:
        self.db.add(model)
        self.db.flush()
        return model

    def get(self, simulation_id: UUID) -> Optional[PolicySafetySimulation]:
        return (
            self.db.query(PolicySafetySimulation)
            .filter(PolicySafetySimulation.id == simulation_id)
            .one_or_none()
        )

    def get_by_key(self, simulation_key: str) -> Optional[PolicySafetySimulation]:
        return (
            self.db.query(PolicySafetySimulation)
            .filter(PolicySafetySimulation.simulation_key == simulation_key)
            .one_or_none()
        )

    def save(self, model: PolicySafetySimulation) -> PolicySafetySimulation:
        self.db.add(model)
        self.db.flush()
        return model
backend/app/repositories/policy_promotion_committee_decision_repository.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_promotion_committee_decision import PolicyPromotionCommitteeDecision


class PolicyPromotionCommitteeDecisionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, model: PolicyPromotionCommitteeDecision) -> PolicyPromotionCommitteeDecision:
        self.db.add(model)
        self.db.flush()
        return model

    def get(self, decision_id: UUID) -> Optional[PolicyPromotionCommitteeDecision]:
        return (
            self.db.query(PolicyPromotionCommitteeDecision)
            .filter(PolicyPromotionCommitteeDecision.id == decision_id)
            .one_or_none()
        )

    def get_by_key(self, decision_key: str) -> Optional[PolicyPromotionCommitteeDecision]:
        return (
            self.db.query(PolicyPromotionCommitteeDecision)
            .filter(PolicyPromotionCommitteeDecision.decision_key == decision_key)
            .one_or_none()
        )

    def save(self, model: PolicyPromotionCommitteeDecision) -> PolicyPromotionCommitteeDecision:
        self.db.add(model)
        self.db.flush()
        return model
backend/app/schemas/policy_promotion_governance.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PolicyOffPolicyEvaluationCreateRequest(BaseModel):
    evaluation_key: str
    name: str
    description: Optional[str] = None
    experiment_key: Optional[str] = None
    method: str = "doubly_robust"
    targeting_filters: Dict[str, Any] = Field(default_factory=dict)
    config_json: Dict[str, Any] = Field(default_factory=dict)


class PolicySafetySimulationCreateRequest(BaseModel):
    simulation_key: str
    name: str
    description: Optional[str] = None
    experiment_key: Optional[str] = None
    bundle_id: str
    arm_key: str
    config_json: Dict[str, Any] = Field(default_factory=dict)


class PolicyPromotionCommitteeDecisionCreateRequest(BaseModel):
    decision_key: str
    experiment_key: Optional[str] = None
    bundle_id: str
    arm_key: str
    estimated_uplift_score: float
    replay_confidence_score: float
    safety_score: float
    regression_risk_score: float
    governance_score: float
    committee_votes_json: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class HistoricalPolicyEvent(BaseModel):
    subject_key: str
    context_json: Dict[str, Any] = Field(default_factory=dict)
    observed_arm_key: str
    observed_bundle_id: Optional[str] = None
    observed_net_benefit: float = 0.0
    logging_propensity: float = 1.0
    direct_model_prediction: float = 0.0
    realized_regression: bool = False


class PolicyOffPolicyEvaluationRunRequest(BaseModel):
    evaluation_key: str
    historical_events: List[HistoricalPolicyEvent]


class PolicySafetySimulationRunRequest(BaseModel):
    simulation_key: str
    scenario_events: List[HistoricalPolicyEvent]
backend/app/services/policy_off_policy_estimation_service.py
from __future__ import annotations

from typing import Any, Dict, List

from app.models.policy_off_policy_evaluation import (
    PolicyOffPolicyEvaluation,
    PolicyOffPolicyEvaluationStatus,
)
from app.repositories.policy_off_policy_evaluation_repository import PolicyOffPolicyEvaluationRepository
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_segment_learning_memory_repository import PolicySegmentLearningMemoryRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository
from app.services.policy_feature_store_service import PolicyFeatureStoreService
from app.services.policy_context_signature_service import PolicyContextSignatureService
from app.services.policy_contextual_prior_service import PolicyContextualPriorService
from app.services.policy_contextual_bandit_service import PolicyContextualBanditService


class PolicyOffPolicyEstimationService:
    def __init__(
        self,
        off_policy_repo: PolicyOffPolicyEvaluationRepository,
        experiment_repo: PolicyExperimentRepository,
        arm_repo: PolicyExperimentArmRepository,
        segment_memory_repo: PolicySegmentLearningMemoryRepository,
        global_memory_repo: PolicyLearningMemoryRepository,
        feature_store_service: PolicyFeatureStoreService,
        context_signature_service: PolicyContextSignatureService,
    ) -> None:
        self.off_policy_repo = off_policy_repo
        self.experiment_repo = experiment_repo
        self.arm_repo = arm_repo
        self.feature_store_service = feature_store_service
        self.context_signature_service = context_signature_service

        prior_service = PolicyContextualPriorService(
            segment_memory_repo=segment_memory_repo,
            global_memory_repo=global_memory_repo,
        )
        self.contextual_bandit_service = PolicyContextualBanditService(prior_service)

    def create_evaluation(
        self,
        evaluation_key: str,
        name: str,
        description: str | None,
        experiment_key: str | None,
        method: str,
        targeting_filters: Dict[str, Any],
        config_json: Dict[str, Any],
        created_by: str,
    ) -> PolicyOffPolicyEvaluation:
        model = PolicyOffPolicyEvaluation(
            evaluation_key=evaluation_key,
            name=name,
            description=description,
            experiment_key=experiment_key,
            method=method,
            targeting_filters=targeting_filters,
            config_json=config_json,
            created_by=created_by,
            status=PolicyOffPolicyEvaluationStatus.pending,
        )
        return self.off_policy_repo.create(model)

    def run_evaluation(
        self,
        evaluation_key: str,
        historical_events: List[Dict[str, Any]],
    ) -> PolicyOffPolicyEvaluation:
        evaluation = self.off_policy_repo.get_by_key(evaluation_key)
        if evaluation is None:
            raise ValueError(f"Off-policy evaluation not found: {evaluation_key}")

        evaluation.status = PolicyOffPolicyEvaluationStatus.running
        self.off_policy_repo.save(evaluation)

        arms = []
        if evaluation.experiment_key:
            experiment = self.experiment_repo.get_by_key(evaluation.experiment_key)
            if experiment is not None:
                arms = list(self.arm_repo.list_active_by_experiment_id(experiment.id))

        total_samples = len(historical_events)
        matched_samples = 0

        dm_sum = 0.0
        ips_sum = 0.0
        dr_sum = 0.0
        regret_sum = 0.0
        regression_count = 0

        rows = []

        for event in historical_events:
            context_json = event.get("context_json", {})
            observed_arm_key = event.get("observed_arm_key")
            observed_reward = float(event.get("observed_net_benefit", 0.0))
            propensity = max(float(event.get("logging_propensity", 1.0)), 1e-6)
            dm_prediction = float(event.get("direct_model_prediction", 0.0))
            realized_regression = bool(event.get("realized_regression", False))

            if not arms:
                continue

            context_signature = self.context_signature_service.build_context_signature(context_json)
            feature_vector = self.feature_store_service.build_feature_vector(context_json)
            segment_key = self.feature_store_service.build_segment_key(feature_vector)

            chosen_arm, debug = self.contextual_bandit_service.choose_arm(
                arms=arms,
                context_signature=context_signature,
                segment_key=segment_key,
            )

            matched = chosen_arm.arm_key == observed_arm_key
            if matched:
                matched_samples += 1

            dm = dm_prediction
            ips = (observed_reward / propensity) if matched else 0.0
            dr = dm + ((observed_reward - dm_prediction) / propensity if matched else 0.0)

            best_reference = max(observed_reward, dm_prediction, 0.0)
            regret = max(best_reference - (observed_reward if matched else dm), 0.0)

            dm_sum += dm
            ips_sum += ips
            dr_sum += dr
            regret_sum += regret
            regression_count += 1 if realized_regression else 0

            rows.append(
                {
                    "subject_key": event.get("subject_key"),
                    "observed_arm_key": observed_arm_key,
                    "chosen_arm_key": chosen_arm.arm_key,
                    "matched": matched,
                    "observed_reward": observed_reward,
                    "dm": dm,
                    "ips": ips,
                    "dr": dr,
                    "regret": regret,
                    "selection_debug": debug,
                }
            )

        denom = total_samples if total_samples else 1
        evaluation.total_samples = total_samples
        evaluation.matched_samples = matched_samples
        evaluation.direct_method_estimate = dm_sum / denom
        evaluation.ips_estimate = ips_sum / denom
        evaluation.doubly_robust_estimate = dr_sum / denom
        evaluation.regret_estimate = regret_sum / denom
        evaluation.regression_risk_rate = regression_count / denom
        evaluation.summary_json = {
            "rows": rows[:500],
            "truncated": len(rows) > 500,
        }
        evaluation.status = PolicyOffPolicyEvaluationStatus.completed

        return self.off_policy_repo.save(evaluation)
backend/app/services/policy_safety_envelope_simulator_service.py
from __future__ import annotations

from typing import Any, Dict, List

from app.models.policy_safety_simulation import (
    PolicySafetySimulation,
    PolicySafetySimulationStatus,
)
from app.repositories.policy_safety_simulation_repository import PolicySafetySimulationRepository


class PolicySafetyEnvelopeSimulatorService:
    def __init__(self, simulation_repo: PolicySafetySimulationRepository) -> None:
        self.simulation_repo = simulation_repo

    def create_simulation(
        self,
        simulation_key: str,
        name: str,
        description: str | None,
        experiment_key: str | None,
        bundle_id: str,
        arm_key: str,
        config_json: Dict[str, Any],
        created_by: str,
    ) -> PolicySafetySimulation:
        model = PolicySafetySimulation(
            simulation_key=simulation_key,
            name=name,
            description=description,
            experiment_key=experiment_key,
            bundle_id=bundle_id,
            arm_key=arm_key,
            config_json=config_json,
            created_by=created_by,
            status=PolicySafetySimulationStatus.pending,
        )
        return self.simulation_repo.create(model)

    def run_simulation(
        self,
        simulation_key: str,
        scenario_events: List[Dict[str, Any]],
    ) -> PolicySafetySimulation:
        simulation = self.simulation_repo.get_by_key(simulation_key)
        if simulation is None:
            raise ValueError(f"Safety simulation not found: {simulation_key}")

        simulation.status = PolicySafetySimulationStatus.running
        self.simulation_repo.save(simulation)

        cfg = simulation.config_json or {}
        sla_threshold = float(cfg.get("max_sla_regression_probability", 0.20))
        churn_threshold = float(cfg.get("max_churn_regression_probability", 0.20))
        rework_threshold = float(cfg.get("max_rework_regression_probability", 0.20))
        rebalance_threshold = float(cfg.get("max_rebalance_degradation_probability", 0.20))
        cost_threshold = float(cfg.get("max_cost_overrun_probability", 0.20))

        total = len(scenario_events) or 1

        sla_bad = 0
        churn_bad = 0
        rework_bad = 0
        rebalance_bad = 0
        cost_bad = 0

        rows = []

        for event in scenario_events:
            sla_delta = float(event.get("sla_breach_delta", 0.0))
            churn_delta = float(event.get("churn_delta", 0.0))
            rework_delta = float(event.get("rework_delta", 0.0))
            rebalance_delta = float(event.get("rebalance_success_delta", 0.0))
            cost_delta = float(event.get("execution_cost_delta", 0.0))

            sla_flag = sla_delta > 0
            churn_flag = churn_delta > 0
            rework_flag = rework_delta > 0
            rebalance_flag = rebalance_delta < 0
            cost_flag = cost_delta > 0

            sla_bad += 1 if sla_flag else 0
            churn_bad += 1 if churn_flag else 0
            rework_bad += 1 if rework_flag else 0
            rebalance_bad += 1 if rebalance_flag else 0
            cost_bad += 1 if cost_flag else 0

            rows.append(
                {
                    "subject_key": event.get("subject_key"),
                    "sla_flag": sla_flag,
                    "churn_flag": churn_flag,
                    "rework_flag": rework_flag,
                    "rebalance_flag": rebalance_flag,
                    "cost_flag": cost_flag,
                }
            )

        sla_prob = sla_bad / total
        churn_prob = churn_bad / total
        rework_prob = rework_bad / total
        rebalance_prob = rebalance_bad / total
        cost_prob = cost_bad / total

        penalties = (
            max(sla_prob - sla_threshold, 0.0)
            + max(churn_prob - churn_threshold, 0.0)
            + max(rework_prob - rework_threshold, 0.0)
            + max(rebalance_prob - rebalance_threshold, 0.0)
            + max(cost_prob - cost_threshold, 0.0)
        )

        safety_score = max(1.0 - penalties, 0.0)
        within_envelope = (
            sla_prob <= sla_threshold
            and churn_prob <= churn_threshold
            and rework_prob <= rework_threshold
            and rebalance_prob <= rebalance_threshold
            and cost_prob <= cost_threshold
        )

        simulation.sla_regression_probability = sla_prob
        simulation.churn_regression_probability = churn_prob
        simulation.rework_regression_probability = rework_prob
        simulation.rebalance_degradation_probability = rebalance_prob
        simulation.cost_overrun_probability = cost_prob
        simulation.safety_score = safety_score
        simulation.within_envelope = within_envelope
        simulation.summary_json = {
            "rows": rows[:500],
            "truncated": len(rows) > 500,
            "thresholds": {
                "sla": sla_threshold,
                "churn": churn_threshold,
                "rework": rework_threshold,
                "rebalance": rebalance_threshold,
                "cost": cost_threshold,
            },
        }
        simulation.status = PolicySafetySimulationStatus.completed

        return self.simulation_repo.save(simulation)
backend/app/services/policy_promotion_committee_service.py
from __future__ import annotations

from typing import Any, Dict

from app.models.policy_promotion_committee_decision import (
    PolicyPromotionCommitteeDecision,
    PolicyPromotionCommitteeDecisionStatus,
)
from app.repositories.policy_promotion_committee_decision_repository import (
    PolicyPromotionCommitteeDecisionRepository,
)
from app.repositories.policy_off_policy_evaluation_repository import (
    PolicyOffPolicyEvaluationRepository,
)
from app.repositories.policy_safety_simulation_repository import (
    PolicySafetySimulationRepository,
)


class PolicyPromotionCommitteeService:
    def __init__(
        self,
        decision_repo: PolicyPromotionCommitteeDecisionRepository,
        off_policy_repo: PolicyOffPolicyEvaluationRepository,
        safety_repo: PolicySafetySimulationRepository,
        bundle_lifecycle_service=None,
        alert_service=None,
        audit_service=None,
    ) -> None:
        self.decision_repo = decision_repo
        self.off_policy_repo = off_policy_repo
        self.safety_repo = safety_repo
        self.bundle_lifecycle_service = bundle_lifecycle_service
        self.alert_service = alert_service
        self.audit_service = audit_service

    def create_decision(
        self,
        decision_key: str,
        experiment_key: str | None,
        bundle_id: str,
        arm_key: str,
        estimated_uplift_score: float,
        replay_confidence_score: float,
        safety_score: float,
        regression_risk_score: float,
        governance_score: float,
        committee_votes_json: Dict[str, Any],
        created_by: str,
        notes: str | None,
    ) -> PolicyPromotionCommitteeDecision:
        final_score = (
            (estimated_uplift_score * 0.35)
            + (replay_confidence_score * 0.20)
            + (safety_score * 0.25)
            + (governance_score * 0.20)
            - (regression_risk_score * 0.30)
        )

        auto_rejected = False
        requires_manual_review = False
        status = PolicyPromotionCommitteeDecisionStatus.pending

        rationale = {
            "auto_reject_reasons": [],
            "manual_review_reasons": [],
            "weights": {
                "uplift": 0.35,
                "replay_confidence": 0.20,
                "safety": 0.25,
                "governance": 0.20,
                "regression_penalty": 0.30,
            },
        }

        if estimated_uplift_score <= 0:
            auto_rejected = True
            status = PolicyPromotionCommitteeDecisionStatus.rejected
            rationale["auto_reject_reasons"].append("non_positive_estimated_uplift")

        if safety_score < 0.60:
            auto_rejected = True
            status = PolicyPromotionCommitteeDecisionStatus.rejected
            rationale["auto_reject_reasons"].append("safety_score_below_threshold")

        if regression_risk_score > 0.40:
            auto_rejected = True
            status = PolicyPromotionCommitteeDecisionStatus.rejected
            rationale["auto_reject_reasons"].append("regression_risk_too_high")

        if not auto_rejected:
            if replay_confidence_score < 0.50:
                requires_manual_review = True
                status = PolicyPromotionCommitteeDecisionStatus.manual_review
                rationale["manual_review_reasons"].append("low_replay_confidence")

            elif final_score >= 0.65:
                status = PolicyPromotionCommitteeDecisionStatus.approved
            else:
                status = PolicyPromotionCommitteeDecisionStatus.manual_review
                requires_manual_review = True
                rationale["manual_review_reasons"].append("borderline_final_score")

        model = PolicyPromotionCommitteeDecision(
            decision_key=decision_key,
            experiment_key=experiment_key,
            bundle_id=bundle_id,
            arm_key=arm_key,
            status=status,
            estimated_uplift_score=estimated_uplift_score,
            replay_confidence_score=replay_confidence_score,
            safety_score=safety_score,
            regression_risk_score=regression_risk_score,
            governance_score=governance_score,
            final_score=final_score,
            auto_rejected=auto_rejected,
            requires_manual_review=requires_manual_review,
            rationale_json=rationale,
            committee_votes_json=committee_votes_json,
            created_by=created_by,
            notes=notes,
        )
        self.decision_repo.create(model)

        if self.audit_service is not None:
            self.audit_service.emit(
                event_type="policy_promotion_committee_decision_created",
                payload={
                    "decision_key": decision_key,
                    "bundle_id": bundle_id,
                    "arm_key": arm_key,
                    "status": status.value,
                    "final_score": final_score,
                    "rationale": rationale,
                },
            )

        if status == PolicyPromotionCommitteeDecisionStatus.approved and self.bundle_lifecycle_service is not None:
            self.bundle_lifecycle_service.promote_bundle(
                bundle_id=bundle_id,
                reason="promotion_committee_approved",
                metadata={
                    "decision_key": decision_key,
                    "arm_key": arm_key,
                    "final_score": final_score,
                },
            )

        if auto_rejected and self.alert_service is not None:
            self.alert_service.emit(
                event_type="policy_promotion_auto_rejected",
                payload={
                    "decision_key": decision_key,
                    "bundle_id": bundle_id,
                    "arm_key": arm_key,
                    "rationale": rationale,
                },
            )

        return model
backend/app/services/policy_promotion_readiness_service.py
from __future__ import annotations

from typing import Any, Dict

from app.repositories.policy_off_policy_evaluation_repository import PolicyOffPolicyEvaluationRepository
from app.repositories.policy_safety_simulation_repository import PolicySafetySimulationRepository


class PolicyPromotionReadinessService:
    def __init__(
        self,
        off_policy_repo: PolicyOffPolicyEvaluationRepository,
        safety_repo: PolicySafetySimulationRepository,
    ) -> None:
        self.off_policy_repo = off_policy_repo
        self.safety_repo = safety_repo

    def build_committee_inputs(
        self,
        off_policy_evaluation_key: str,
        safety_simulation_key: str,
    ) -> Dict[str, Any]:
        off_policy = self.off_policy_repo.get_by_key(off_policy_evaluation_key)
        if off_policy is None:
            raise ValueError(f"Off-policy evaluation not found: {off_policy_evaluation_key}")

        safety = self.safety_repo.get_by_key(safety_simulation_key)
        if safety is None:
            raise ValueError(f"Safety simulation not found: {safety_simulation_key}")

        estimated_uplift = float(off_policy.doubly_robust_estimate or 0.0)

        replay_confidence = 0.0
        if off_policy.total_samples > 0:
            coverage = min((off_policy.matched_samples / off_policy.total_samples), 1.0)
            replay_confidence = max(0.0, min(1.0, coverage * (1.0 - float(off_policy.regression_risk_rate or 0.0))))

        safety_score = float(safety.safety_score or 0.0)
        regression_risk_score = float(off_policy.regression_risk_rate or 0.0)

        governance_score = 1.0 if bool(safety.within_envelope) else 0.4

        return {
            "estimated_uplift_score": estimated_uplift,
            "replay_confidence_score": replay_confidence,
            "safety_score": safety_score,
            "regression_risk_score": regression_risk_score,
            "governance_score": governance_score,
            "bundle_id": safety.bundle_id,
            "arm_key": safety.arm_key,
            "experiment_key": safety.experiment_key,
            "evidence": {
                "off_policy_evaluation_key": off_policy.evaluation_key,
                "safety_simulation_key": safety.simulation_key,
                "dr_estimate": off_policy.doubly_robust_estimate,
                "ips_estimate": off_policy.ips_estimate,
                "dm_estimate": off_policy.direct_method_estimate,
                "safety_within_envelope": safety.within_envelope,
            },
        }
backend/app/api/policy_promotion_governance.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_actor_id
from app.repositories.policy_off_policy_evaluation_repository import PolicyOffPolicyEvaluationRepository
from app.repositories.policy_safety_simulation_repository import PolicySafetySimulationRepository
from app.repositories.policy_promotion_committee_decision_repository import (
    PolicyPromotionCommitteeDecisionRepository,
)
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_segment_learning_memory_repository import PolicySegmentLearningMemoryRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository
from app.schemas.policy_promotion_governance import (
    PolicyOffPolicyEvaluationCreateRequest,
    PolicySafetySimulationCreateRequest,
    PolicyPromotionCommitteeDecisionCreateRequest,
    PolicyOffPolicyEvaluationRunRequest,
    PolicySafetySimulationRunRequest,
)
from app.services.policy_off_policy_estimation_service import PolicyOffPolicyEstimationService
from app.services.policy_safety_envelope_simulator_service import PolicySafetyEnvelopeSimulatorService
from app.services.policy_promotion_committee_service import PolicyPromotionCommitteeService
from app.services.policy_promotion_readiness_service import PolicyPromotionReadinessService
from app.services.policy_feature_store_service import PolicyFeatureStoreService
from app.services.policy_context_signature_service import PolicyContextSignatureService

router = APIRouter(prefix="/policy-promotion-governance", tags=["policy-promotion-governance"])


@router.post("/off-policy")
def create_off_policy_evaluation(
    payload: PolicyOffPolicyEvaluationCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicyOffPolicyEstimationService(
        off_policy_repo=PolicyOffPolicyEvaluationRepository(db),
        experiment_repo=PolicyExperimentRepository(db),
        arm_repo=PolicyExperimentArmRepository(db),
        segment_memory_repo=PolicySegmentLearningMemoryRepository(db),
        global_memory_repo=PolicyLearningMemoryRepository(db),
        feature_store_service=PolicyFeatureStoreService(),
        context_signature_service=PolicyContextSignatureService(),
    )
    model = service.create_evaluation(
        evaluation_key=payload.evaluation_key,
        name=payload.name,
        description=payload.description,
        experiment_key=payload.experiment_key,
        method=payload.method,
        targeting_filters=payload.targeting_filters,
        config_json=payload.config_json,
        created_by=actor_id,
    )
    db.commit()
    return {
        "evaluation_id": str(model.id),
        "evaluation_key": model.evaluation_key,
        "status": model.status.value,
    }


@router.post("/off-policy/run")
def run_off_policy_evaluation(
    payload: PolicyOffPolicyEvaluationRunRequest,
    db: Session = Depends(get_db),
):
    service = PolicyOffPolicyEstimationService(
        off_policy_repo=PolicyOffPolicyEvaluationRepository(db),
        experiment_repo=PolicyExperimentRepository(db),
        arm_repo=PolicyExperimentArmRepository(db),
        segment_memory_repo=PolicySegmentLearningMemoryRepository(db),
        global_memory_repo=PolicyLearningMemoryRepository(db),
        feature_store_service=PolicyFeatureStoreService(),
        context_signature_service=PolicyContextSignatureService(),
    )
    try:
        model = service.run_evaluation(
            evaluation_key=payload.evaluation_key,
            historical_events=[e.model_dump() for e in payload.historical_events],
        )
        db.commit()
        return {
            "evaluation_id": str(model.id),
            "status": model.status.value,
            "direct_method_estimate": model.direct_method_estimate,
            "ips_estimate": model.ips_estimate,
            "doubly_robust_estimate": model.doubly_robust_estimate,
            "regret_estimate": model.regret_estimate,
            "regression_risk_rate": model.regression_risk_rate,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/safety-simulation")
def create_safety_simulation(
    payload: PolicySafetySimulationCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicySafetyEnvelopeSimulatorService(
        simulation_repo=PolicySafetySimulationRepository(db),
    )
    model = service.create_simulation(
        simulation_key=payload.simulation_key,
        name=payload.name,
        description=payload.description,
        experiment_key=payload.experiment_key,
        bundle_id=payload.bundle_id,
        arm_key=payload.arm_key,
        config_json=payload.config_json,
        created_by=actor_id,
    )
    db.commit()
    return {
        "simulation_id": str(model.id),
        "simulation_key": model.simulation_key,
        "status": model.status.value,
    }


@router.post("/safety-simulation/run")
def run_safety_simulation(
    payload: PolicySafetySimulationRunRequest,
    db: Session = Depends(get_db),
):
    service = PolicySafetyEnvelopeSimulatorService(
        simulation_repo=PolicySafetySimulationRepository(db),
    )
    try:
        model = service.run_simulation(
            simulation_key=payload.simulation_key,
            scenario_events=[e.model_dump() for e in payload.scenario_events],
        )
        db.commit()
        return {
            "simulation_id": str(model.id),
            "status": model.status.value,
            "sla_regression_probability": model.sla_regression_probability,
            "churn_regression_probability": model.churn_regression_probability,
            "rework_regression_probability": model.rework_regression_probability,
            "rebalance_degradation_probability": model.rebalance_degradation_probability,
            "cost_overrun_probability": model.cost_overrun_probability,
            "safety_score": model.safety_score,
            "within_envelope": model.within_envelope,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/committee-decision")
def create_committee_decision(
    payload: PolicyPromotionCommitteeDecisionCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicyPromotionCommitteeService(
        decision_repo=PolicyPromotionCommitteeDecisionRepository(db),
        off_policy_repo=PolicyOffPolicyEvaluationRepository(db),
        safety_repo=PolicySafetySimulationRepository(db),
    )
    model = service.create_decision(
        decision_key=payload.decision_key,
        experiment_key=payload.experiment_key,
        bundle_id=payload.bundle_id,
        arm_key=payload.arm_key,
        estimated_uplift_score=payload.estimated_uplift_score,
        replay_confidence_score=payload.replay_confidence_score,
        safety_score=payload.safety_score,
        regression_risk_score=payload.regression_risk_score,
        governance_score=payload.governance_score,
        committee_votes_json=payload.committee_votes_json,
        created_by=actor_id,
        notes=payload.notes,
    )
    db.commit()
    return {
        "decision_id": str(model.id),
        "decision_key": model.decision_key,
        "status": model.status.value,
        "final_score": model.final_score,
        "auto_rejected": model.auto_rejected,
        "requires_manual_review": model.requires_manual_review,
    }


@router.post("/committee-decision/from-evidence")
def create_committee_decision_from_evidence(
    decision_key: str,
    off_policy_evaluation_key: str,
    safety_simulation_key: str,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    readiness_service = PolicyPromotionReadinessService(
        off_policy_repo=PolicyOffPolicyEvaluationRepository(db),
        safety_repo=PolicySafetySimulationRepository(db),
    )
    committee_service = PolicyPromotionCommitteeService(
        decision_repo=PolicyPromotionCommitteeDecisionRepository(db),
        off_policy_repo=PolicyOffPolicyEvaluationRepository(db),
        safety_repo=PolicySafetySimulationRepository(db),
    )

    try:
        inputs = readiness_service.build_committee_inputs(
            off_policy_evaluation_key=off_policy_evaluation_key,
            safety_simulation_key=safety_simulation_key,
        )
        model = committee_service.create_decision(
            decision_key=decision_key,
            experiment_key=inputs["experiment_key"],
            bundle_id=inputs["bundle_id"],
            arm_key=inputs["arm_key"],
            estimated_uplift_score=inputs["estimated_uplift_score"],
            replay_confidence_score=inputs["replay_confidence_score"],
            safety_score=inputs["safety_score"],
            regression_risk_score=inputs["regression_risk_score"],
            governance_score=inputs["governance_score"],
            committee_votes_json={"evidence": inputs["evidence"]},
            created_by=actor_id,
            notes="Generated from off-policy evaluation + safety simulation evidence",
        )
        db.commit()
        return {
            "decision_id": str(model.id),
            "decision_key": model.decision_key,
            "status": model.status.value,
            "final_score": model.final_score,
            "auto_rejected": model.auto_rejected,
            "requires_manual_review": model.requires_manual_review,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
backend/app/workers/policy_promotion_governance_worker.py
from __future__ import annotations

from app.db.session import SessionLocal
from app.repositories.policy_off_policy_evaluation_repository import PolicyOffPolicyEvaluationRepository
from app.repositories.policy_safety_simulation_repository import PolicySafetySimulationRepository
from app.repositories.policy_promotion_committee_decision_repository import (
    PolicyPromotionCommitteeDecisionRepository,
)
from app.repositories.policy_experiment_repository import PolicyExperimentRepository
from app.repositories.policy_experiment_arm_repository import PolicyExperimentArmRepository
from app.repositories.policy_segment_learning_memory_repository import PolicySegmentLearningMemoryRepository
from app.repositories.policy_learning_memory_repository import PolicyLearningMemoryRepository
from app.services.policy_off_policy_estimation_service import PolicyOffPolicyEstimationService
from app.services.policy_safety_envelope_simulator_service import PolicySafetyEnvelopeSimulatorService
from app.services.policy_promotion_committee_service import PolicyPromotionCommitteeService
from app.services.policy_promotion_readiness_service import PolicyPromotionReadinessService
from app.services.policy_feature_store_service import PolicyFeatureStoreService
from app.services.policy_context_signature_service import PolicyContextSignatureService


def run_off_policy_and_committee(
    evaluation_key: str,
    historical_events: list[dict],
    simulation_key: str,
    scenario_events: list[dict],
    decision_key: str,
    actor_id: str = "system",
) -> dict:
    db = SessionLocal()
    try:
        off_policy_service = PolicyOffPolicyEstimationService(
            off_policy_repo=PolicyOffPolicyEvaluationRepository(db),
            experiment_repo=PolicyExperimentRepository(db),
            arm_repo=PolicyExperimentArmRepository(db),
            segment_memory_repo=PolicySegmentLearningMemoryRepository(db),
            global_memory_repo=PolicyLearningMemoryRepository(db),
            feature_store_service=PolicyFeatureStoreService(),
            context_signature_service=PolicyContextSignatureService(),
        )
        safety_service = PolicySafetyEnvelopeSimulatorService(
            simulation_repo=PolicySafetySimulationRepository(db),
        )
        readiness_service = PolicyPromotionReadinessService(
            off_policy_repo=PolicyOffPolicyEvaluationRepository(db),
            safety_repo=PolicySafetySimulationRepository(db),
        )
        committee_service = PolicyPromotionCommitteeService(
            decision_repo=PolicyPromotionCommitteeDecisionRepository(db),
            off_policy_repo=PolicyOffPolicyEvaluationRepository(db),
            safety_repo=PolicySafetySimulationRepository(db),
        )

        off_policy = off_policy_service.run_evaluation(
            evaluation_key=evaluation_key,
            historical_events=historical_events,
        )
        safety = safety_service.run_simulation(
            simulation_key=simulation_key,
            scenario_events=scenario_events,
        )
        inputs = readiness_service.build_committee_inputs(
            off_policy_evaluation_key=off_policy.evaluation_key,
            safety_simulation_key=safety.simulation_key,
        )
        decision = committee_service.create_decision(
            decision_key=decision_key,
            experiment_key=inputs["experiment_key"],
            bundle_id=inputs["bundle_id"],
            arm_key=inputs["arm_key"],
            estimated_uplift_score=inputs["estimated_uplift_score"],
            replay_confidence_score=inputs["replay_confidence_score"],
            safety_score=inputs["safety_score"],
            regression_risk_score=inputs["regression_risk_score"],
            governance_score=inputs["governance_score"],
            committee_votes_json={"evidence": inputs["evidence"]},
            created_by=actor_id,
            notes="Automated governance pipeline decision",
        )

        db.commit()
        return {
            "off_policy_evaluation_key": off_policy.evaluation_key,
            "simulation_key": safety.simulation_key,
            "decision_key": decision.decision_key,
            "decision_status": decision.status.value,
            "final_score": decision.final_score,
            "auto_rejected": decision.auto_rejected,
            "requires_manual_review": decision.requires_manual_review,
        }
    finally:
        db.close()
backend/alembic/versions/20260412_0032_off_policy_safety_committee.py
"""off policy safety committee

Revision ID: 20260412_0032
Revises: 20260412_0031
Create Date: 2026-04-12 12:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260412_0032"
down_revision = "20260412_0031"
branch_labels = None
depends_on = None


policy_off_policy_evaluation_status_enum = sa.Enum(
    "pending",
    "running",
    "completed",
    "failed",
    name="policyoffpolicyevaluationstatus",
)

policy_safety_simulation_status_enum = sa.Enum(
    "pending",
    "running",
    "completed",
    "failed",
    name="policysafetysimulationstatus",
)

policy_promotion_committee_decision_status_enum = sa.Enum(
    "pending",
    "approved",
    "rejected",
    "manual_review",
    name="policypromotioncommitteedecisionstatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    policy_off_policy_evaluation_status_enum.create(bind, checkfirst=True)
    policy_safety_simulation_status_enum.create(bind, checkfirst=True)
    policy_promotion_committee_decision_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "policy_off_policy_evaluation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("evaluation_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("experiment_key", sa.String(length=255), nullable=True),
        sa.Column("status", policy_off_policy_evaluation_status_enum, nullable=False),
        sa.Column("method", sa.String(length=64), nullable=False),
        sa.Column("targeting_filters", sa.JSON(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("total_samples", sa.Integer(), nullable=False),
        sa.Column("matched_samples", sa.Integer(), nullable=False),
        sa.Column("direct_method_estimate", sa.Float(), nullable=True),
        sa.Column("ips_estimate", sa.Float(), nullable=True),
        sa.Column("doubly_robust_estimate", sa.Float(), nullable=True),
        sa.Column("regret_estimate", sa.Float(), nullable=True),
        sa.Column("regression_risk_rate", sa.Float(), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_off_policy_evaluation_evaluation_key", "policy_off_policy_evaluation", ["evaluation_key"], unique=True)
    op.create_index("ix_policy_off_policy_evaluation_experiment_key", "policy_off_policy_evaluation", ["experiment_key"], unique=False)

    op.create_table(
        "policy_safety_simulation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("simulation_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("experiment_key", sa.String(length=255), nullable=True),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("arm_key", sa.String(length=255), nullable=False),
        sa.Column("status", policy_safety_simulation_status_enum, nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("sla_regression_probability", sa.Float(), nullable=True),
        sa.Column("churn_regression_probability", sa.Float(), nullable=True),
        sa.Column("rework_regression_probability", sa.Float(), nullable=True),
        sa.Column("rebalance_degradation_probability", sa.Float(), nullable=True),
        sa.Column("cost_overrun_probability", sa.Float(), nullable=True),
        sa.Column("safety_score", sa.Float(), nullable=True),
        sa.Column("within_envelope", sa.Boolean(), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_safety_simulation_simulation_key", "policy_safety_simulation", ["simulation_key"], unique=True)
    op.create_index("ix_policy_safety_simulation_experiment_key", "policy_safety_simulation", ["experiment_key"], unique=False)
    op.create_index("ix_policy_safety_simulation_bundle_id", "policy_safety_simulation", ["bundle_id"], unique=False)
    op.create_index("ix_policy_safety_simulation_arm_key", "policy_safety_simulation", ["arm_key"], unique=False)

    op.create_table(
        "policy_promotion_committee_decision",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("decision_key", sa.String(length=255), nullable=False),
        sa.Column("experiment_key", sa.String(length=255), nullable=True),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("arm_key", sa.String(length=255), nullable=False),
        sa.Column("status", policy_promotion_committee_decision_status_enum, nullable=False),
        sa.Column("estimated_uplift_score", sa.Float(), nullable=True),
        sa.Column("replay_confidence_score", sa.Float(), nullable=True),
        sa.Column("safety_score", sa.Float(), nullable=True),
        sa.Column("regression_risk_score", sa.Float(), nullable=True),
        sa.Column("governance_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("auto_rejected", sa.Boolean(), nullable=False),
        sa.Column("requires_manual_review", sa.Boolean(), nullable=False),
        sa.Column("rationale_json", sa.JSON(), nullable=False),
        sa.Column("committee_votes_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_promotion_committee_decision_decision_key", "policy_promotion_committee_decision", ["decision_key"], unique=True)
    op.create_index("ix_policy_promotion_committee_decision_experiment_key", "policy_promotion_committee_decision", ["experiment_key"], unique=False)
    op.create_index("ix_policy_promotion_committee_decision_bundle_id", "policy_promotion_committee_decision", ["bundle_id"], unique=False)
    op.create_index("ix_policy_promotion_committee_decision_arm_key", "policy_promotion_committee_decision", ["arm_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_policy_promotion_committee_decision_arm_key", table_name="policy_promotion_committee_decision")
    op.drop_index("ix_policy_promotion_committee_decision_bundle_id", table_name="policy_promotion_committee_decision")
    op.drop_index("ix_policy_promotion_committee_decision_experiment_key", table_name="policy_promotion_committee_decision")
    op.drop_index("ix_policy_promotion_committee_decision_decision_key", table_name="policy_promotion_committee_decision")
    op.drop_table("policy_promotion_committee_decision")

    op.drop_index("ix_policy_safety_simulation_arm_key", table_name="policy_safety_simulation")
    op.drop_index("ix_policy_safety_simulation_bundle_id", table_name="policy_safety_simulation")
    op.drop_index("ix_policy_safety_simulation_experiment_key", table_name="policy_safety_simulation")
    op.drop_index("ix_policy_safety_simulation_simulation_key", table_name="policy_safety_simulation")
    op.drop_table("policy_safety_simulation")

    op.drop_index("ix_policy_off_policy_evaluation_experiment_key", table_name="policy_off_policy_evaluation")
    op.drop_index("ix_policy_off_policy_evaluation_evaluation_key", table_name="policy_off_policy_evaluation")
    op.drop_table("policy_off_policy_evaluation")

    bind = op.get_bind()
    policy_promotion_committee_decision_status_enum.drop(bind, checkfirst=True)
    policy_safety_simulation_status_enum.drop(bind, checkfirst=True)
    policy_off_policy_evaluation_status_enum.drop(bind, checkfirst=True)
backend/tests/services/test_policy_off_policy_estimation_service.py
from unittest.mock import Mock

from app.services.policy_off_policy_estimation_service import PolicyOffPolicyEstimationService


def test_off_policy_service_runs_with_mocked_bandit_dependencies():
    off_policy_repo = Mock()
    experiment_repo = Mock()
    arm_repo = Mock()
    segment_memory_repo = Mock()
    global_memory_repo = Mock()

    feature_store = Mock()
    feature_store.build_feature_vector.return_value = {
        "queue": "fraud_review",
        "severity": "critical",
        "shift": "night",
        "project": "apollo",
    }
    feature_store.build_segment_key.return_value = "q=fraud_review|s=critical|sh=night|p=apollo"

    context_sig = Mock()
    context_sig.build_context_signature.return_value = "ctx123"

    evaluation = type(
        "Eval",
        (),
        {
            "evaluation_key": "eval1",
            "experiment_key": "exp1",
            "status": None,
            "total_samples": 0,
            "matched_samples": 0,
            "direct_method_estimate": None,
            "ips_estimate": None,
            "doubly_robust_estimate": None,
            "regret_estimate": None,
            "regression_risk_rate": None,
            "summary_json": {},
        },
    )()

    off_policy_repo.get_by_key.return_value = evaluation
    off_policy_repo.save.side_effect = lambda x: x

    experiment = type("Experiment", (), {"id": "exp-id"})()
    experiment_repo.get_by_key.return_value = experiment

    arm = type(
        "Arm",
        (),
        {
            "arm_key": "variant_a",
            "bundle_id": "bundle-a",
            "alpha": 1.0,
            "beta": 1.0,
            "current_weight": 1.0,
        },
    )()
    arm_repo.list_active_by_experiment_id.return_value = [arm]

    segment_memory_repo.get_by_segment_memory_key.return_value = None
    global_memory_repo.get_by_memory_key.return_value = None

    service = PolicyOffPolicyEstimationService(
        off_policy_repo=off_policy_repo,
        experiment_repo=experiment_repo,
        arm_repo=arm_repo,
        segment_memory_repo=segment_memory_repo,
        global_memory_repo=global_memory_repo,
        feature_store_service=feature_store,
        context_signature_service=context_sig,
    )

    result = service.run_evaluation(
        "eval1",
        [
            {
                "subject_key": "case-1",
                "context_json": {"queue": "fraud_review"},
                "observed_arm_key": "variant_a",
                "observed_net_benefit": 3.0,
                "logging_propensity": 1.0,
                "direct_model_prediction": 2.5,
                "realized_regression": False,
            }
        ],
    )

    assert result.total_samples == 1
backend/tests/services/test_policy_safety_envelope_simulator_service.py
from unittest.mock import Mock

from app.services.policy_safety_envelope_simulator_service import PolicySafetyEnvelopeSimulatorService


def test_safety_simulation_flags_out_of_envelope():
    repo = Mock()
    model = type(
        "Simulation",
        (),
        {
            "simulation_key": "sim-1",
            "status": None,
            "config_json": {
                "max_sla_regression_probability": 0.10,
                "max_churn_regression_probability": 0.10,
                "max_rework_regression_probability": 0.10,
                "max_rebalance_degradation_probability": 0.10,
                "max_cost_overrun_probability": 0.10,
            },
            "sla_regression_probability": None,
            "churn_regression_probability": None,
            "rework_regression_probability": None,
            "rebalance_degradation_probability": None,
            "cost_overrun_probability": None,
            "safety_score": None,
            "within_envelope": None,
            "summary_json": {},
        },
    )()
    repo.get_by_key.return_value = model
    repo.save.side_effect = lambda x: x

    service = PolicySafetyEnvelopeSimulatorService(repo)
    result = service.run_simulation(
        "sim-1",
        [
            {
                "subject_key": "a",
                "sla_breach_delta": 0.5,
                "churn_delta": 0.0,
                "rework_delta": 0.0,
                "rebalance_success_delta": 0.1,
                "execution_cost_delta": 0.0,
            }
        ],
    )

    assert result.within_envelope is False
backend/tests/services/test_policy_promotion_committee_service.py
from unittest.mock import Mock

from app.services.policy_promotion_committee_service import PolicyPromotionCommitteeService
from app.models.policy_promotion_committee_decision import PolicyPromotionCommitteeDecisionStatus


def test_committee_auto_rejects_high_risk_policy():
    repo = Mock()
    repo.create.side_effect = lambda x: x

    service = PolicyPromotionCommitteeService(
        decision_repo=repo,
        off_policy_repo=Mock(),
        safety_repo=Mock(),
    )

    model = service.create_decision(
        decision_key="decision-1",
        experiment_key="exp-1",
        bundle_id="bundle-a",
        arm_key="arm-a",
        estimated_uplift_score=0.8,
        replay_confidence_score=0.9,
        safety_score=0.55,
        regression_risk_score=0.5,
        governance_score=0.9,
        committee_votes_json={},
        created_by="tester",
        notes=None,
    )

    assert model.status == PolicyPromotionCommitteeDecisionStatus.rejected
    assert model.auto_rejected is True
3) CÁCH NỐI ROUTER VÀO APP
Trong backend/app/main.py hoặc router registry:
from app.api.policy_promotion_governance import router as policy_promotion_governance_router

app.include_router(policy_promotion_governance_router)
4) FLOW THỰC TẾ SAU PATCH NÀY
A. Tạo off-policy evaluation
POST /policy-promotion-governance/off-policy
{
  "evaluation_key": "ope-fraud-night-001",
  "name": "OPE Fraud Night",
  "description": "Counterfactual uplift estimation for fraud critical night",
  "experiment_key": "bundle-routing-exp-001",
  "method": "doubly_robust",
  "targeting_filters": {
    "queue": ["fraud_review"],
    "severity": ["critical"],
    "shift": ["night"]
  },
  "config_json": {
    "reward_column": "net_benefit"
  }
}
B. Chạy off-policy evaluation
POST /policy-promotion-governance/off-policy/run
{
  "evaluation_key": "ope-fraud-night-001",
  "historical_events": [
    {
      "subject_key": "case-001",
      "context_json": {
        "queue": "fraud_review",
        "severity": "critical",
        "shift": "night",
        "project": "apollo",
        "reviewer_bucket": "r2",
        "review_case_bucket": "c7"
      },
      "observed_arm_key": "variant_a",
      "observed_bundle_id": "bundle-a",
      "observed_net_benefit": 4.2,
      "logging_propensity": 0.5,
      "direct_model_prediction": 3.8,
      "realized_regression": false
    }
  ]
}
C. Tạo safety simulation
POST /policy-promotion-governance/safety-simulation
{
  "simulation_key": "safety-fraud-night-001",
  "name": "Safety Fraud Night",
  "description": "Safety envelope simulation before promotion",
  "experiment_key": "bundle-routing-exp-001",
  "bundle_id": "bundle-a",
  "arm_key": "variant_a",
  "config_json": {
    "max_sla_regression_probability": 0.15,
    "max_churn_regression_probability": 0.15,
    "max_rework_regression_probability": 0.15,
    "max_rebalance_degradation_probability": 0.20,
    "max_cost_overrun_probability": 0.20
  }
}
D. Chạy safety simulation
POST /policy-promotion-governance/safety-simulation/run
{
  "simulation_key": "safety-fraud-night-001",
  "scenario_events": [
    {
      "subject_key": "case-001",
      "context_json": {
        "queue": "fraud_review"
      },
      "observed_arm_key": "variant_a",
      "observed_net_benefit": 0.0,
      "logging_propensity": 1.0,
      "direct_model_prediction": 0.0,
      "realized_regression": false
    }
  ]
}
Lưu ý: scenario_events có thể mở rộng để chứa thêm:
sla_breach_delta
churn_delta
rework_delta
rebalance_success_delta
execution_cost_delta
vì simulator đang đọc trực tiếp các trường này.
E. Tạo committee decision từ evidence
POST /policy-promotion-governance/committee-decision/from-evidence?decision_key=committee-001&off_policy_evaluation_key=ope-fraud-night-001&safety_simulation_key=safety-fraud-night-001
Hệ sẽ:
đọc off-policy evidence
đọc safety simulation evidence
build governance inputs
ra decision:
approved
rejected
manual_review
5) LOGIC GOVERNANCE QUAN TRỌNG CỦA PHASE NÀY
A. Auto-reject policy uplift ảo nhưng risk cao
Trong PolicyPromotionCommitteeService:
Policy sẽ bị reject ngay nếu:
estimated_uplift_score <= 0
safety_score < 0.60
regression_risk_score > 0.40
Tức là bandit winner chưa đủ. Phải qua governance gate.
B. Manual review khi bằng chứng chưa đủ mạnh
Policy sẽ vào manual_review nếu:
replay confidence thấp
final score biên
chưa đủ chắc để promote tự động
Đây là lớp chuyển từ:
automation-first
sang:
governance-grade automation
C. Approved chỉ khi cả 4 trụ đều đủ tốt
Approved cần đồng thời có:
uplift dương
replay confidence đủ
safety ổn
regression risk không quá cao
6) ĐIỂM MAP QUAN TRỌNG KHI DÁN VÀO REPO THẬT
A. Off-policy estimator thật
Bản này đã có:
DM
IPS
DR
Repo thật nên map thêm:
clipping cho IPS weights
self-normalized IPS
segment-specific OPE
bootstrap confidence intervals
uncertainty bands
B. Direct model prediction thật
Hiện direct_model_prediction lấy từ input.
Repo thật nên có:
reward model riêng
uplift model riêng
regression risk model
cost impact model
Tức là OPE nên đọc từ model inference thật thay vì payload tay.
C. Safety simulation thật
Hiện simulator chỉ đếm xác suất regression từ scenario events.
Repo thật nên map thêm:
Monte Carlo rollout simulation
queue arrival/load scenarios
staffing saturation scenarios
provider degradation scenarios
worst-case envelope
p50 / p90 / p99 safety outcomes
D. Committee thật
Hiện committee là service logic.
Repo thật nên map thêm:
supervisor vote
governance approver vote
product owner vote
audit-trace by voter
veto class
approval quorum
E. Bundle lifecycle thật
Khi approved, service có thể nối vào:
promote_bundle(...)
mark_bundle_candidate_promoted(...)
freeze_loser_variants(...)
emit_notification(...)
record_audit_event(...)
7) KẾT QUẢ SAU PATCH NÀY
Sau phase này, hệ của bạn đi từ:
context-aware policy optimization system
sang:
governance-grade policy promotion system
Cụ thể hệ đã có:
A. Counterfactual estimation nghiêm túc hơn
Không chỉ replay matched đơn giản, mà có:
direct method
IPS
doubly robust
B. Safety envelope simulator
Không chỉ hỏi “policy có uplift không”, mà hỏi:
nếu promote thì có phá SLA không
có tăng churn/rework/conflict không
có làm rebalance xấu đi không
có đội cost không
C. Policy promotion committee
Không còn promote chỉ vì bandit winner.
Policy phải qua committee gate.
D. Auto-reject risky uplift
Policy có uplift ảo nhưng safety xấu hoặc regression risk cao sẽ bị reject.
E. Governance-grade promotion decision
Promotion giờ có:
evidence
rationale
scores
status
auditability
bản PHASE 3 — MULTI-STAGE POLICY PROMOTION PIPELINE + HUMAN APPROVAL WORKBENCH + ROLLBACK INVESTIGATION TIMELINE theo đúng kiểu full code file-by-file paste-ready.
Phase này nâng hệ từ:
có committee decision
có safety simulation
có OPE
sang:
pipeline promotion nhiều stage
manual review queue thật
human approval workbench
rollback investigation timeline
post-promotion monitoring gắn với evidence trước promote
1) HỆ SẼ CÓ THÊM NHỮNG GÌ
Thêm 5 lớp lớn:
Promotion pipeline instance
chạy policy candidate qua nhiều stage:
evidence_ready → committee_review → approval → canary_live → promote_live / rolled_back / rejected
Human approval workbench
reviewer queue
approve / reject / request changes / escalate
SLA cho review pending
Rollback investigation timeline
timeline hợp nhất:
committee decision
promotion events
canary regressions
rollback trigger
operator notes
Post-promotion monitoring link
gắn monitoring state với:
decision_key
off_policy_evaluation
safety simulation
promoted bundle
Enterprise operations state machine
không chỉ “decide”
mà “operate, monitor, investigate, approve, rollback”
2) FILE-BY-FILE
backend/app/models/policy_promotion_pipeline.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, Enum, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyPromotionPipelineStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    waiting_manual_review = "waiting_manual_review"
    approved = "approved"
    rejected = "rejected"
    canary_live = "canary_live"
    promoted_live = "promoted_live"
    rolled_back = "rolled_back"
    completed = "completed"
    failed = "failed"


class PolicyPromotionPipeline(Base):
    __tablename__ = "policy_promotion_pipeline"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    pipeline_key = Column(String(255), nullable=False, unique=True, index=True)
    experiment_key = Column(String(255), nullable=True, index=True)
    bundle_id = Column(String(255), nullable=False, index=True)
    arm_key = Column(String(255), nullable=False, index=True)

    decision_key = Column(String(255), nullable=True, index=True)
    off_policy_evaluation_key = Column(String(255), nullable=True, index=True)
    safety_simulation_key = Column(String(255), nullable=True, index=True)

    status = Column(Enum(PolicyPromotionPipelineStatus), nullable=False, default=PolicyPromotionPipelineStatus.pending)
    current_stage = Column(String(128), nullable=False, default="evidence_ready")

    stage_context_json = Column(JSON, nullable=False, default=dict)
    config_json = Column(JSON, nullable=False, default=dict)
    notes = Column(Text, nullable=True)

    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/models/policy_promotion_pipeline_stage_event.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyPromotionPipelineStageEvent(Base):
    __tablename__ = "policy_promotion_pipeline_stage_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("policy_promotion_pipeline.id"), nullable=False, index=True)

    stage_name = Column(String(128), nullable=False, index=True)
    event_type = Column(String(128), nullable=False, index=True)
    actor_id = Column(String(255), nullable=True, index=True)

    summary = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
backend/app/models/policy_manual_review_queue_item.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, Enum, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyManualReviewQueueItemStatus(str, enum.Enum):
    pending = "pending"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"
    changes_requested = "changes_requested"
    escalated = "escalated"
    closed = "closed"


class PolicyManualReviewQueueItem(Base):
    __tablename__ = "policy_manual_review_queue_item"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("policy_promotion_pipeline.id"), nullable=False, index=True)
    decision_key = Column(String(255), nullable=True, index=True)
    bundle_id = Column(String(255), nullable=False, index=True)
    arm_key = Column(String(255), nullable=False, index=True)

    status = Column(Enum(PolicyManualReviewQueueItemStatus), nullable=False, default=PolicyManualReviewQueueItemStatus.pending)
    assigned_reviewer_id = Column(String(255), nullable=True, index=True)
    escalation_reviewer_id = Column(String(255), nullable=True, index=True)

    priority = Column(String(64), nullable=False, default="normal")
    sla_due_at = Column(DateTime, nullable=True)
    review_context_json = Column(JSON, nullable=False, default=dict)
    notes = Column(Text, nullable=True)

    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/models/policy_manual_review_action.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyManualReviewAction(Base):
    __tablename__ = "policy_manual_review_action"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    queue_item_id = Column(UUID(as_uuid=True), ForeignKey("policy_manual_review_queue_item.id"), nullable=False, index=True)
    action_type = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(255), nullable=True, index=True)

    reason = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
backend/app/models/policy_rollback_investigation.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, Enum, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyRollbackInvestigationStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class PolicyRollbackInvestigation(Base):
    __tablename__ = "policy_rollback_investigation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("policy_promotion_pipeline.id"), nullable=False, index=True)
    bundle_id = Column(String(255), nullable=False, index=True)
    arm_key = Column(String(255), nullable=False, index=True)
    rollback_reason = Column(String(255), nullable=True, index=True)

    status = Column(Enum(PolicyRollbackInvestigationStatus), nullable=False, default=PolicyRollbackInvestigationStatus.open)
    opened_by = Column(String(255), nullable=True)
    assigned_owner_id = Column(String(255), nullable=True, index=True)

    evidence_json = Column(JSON, nullable=False, default=dict)
    resolution_summary = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/models/policy_rollback_investigation_timeline_event.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyRollbackInvestigationTimelineEvent(Base):
    __tablename__ = "policy_rollback_investigation_timeline_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    investigation_id = Column(UUID(as_uuid=True), ForeignKey("policy_rollback_investigation.id"), nullable=False, index=True)
    event_type = Column(String(128), nullable=False, index=True)
    actor_id = Column(String(255), nullable=True, index=True)

    summary = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
backend/app/models/policy_post_promotion_monitor.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, Enum, Float, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PolicyPostPromotionMonitorStatus(str, enum.Enum):
    active = "active"
    warning = "warning"
    rollback_candidate = "rollback_candidate"
    stable = "stable"
    closed = "closed"


class PolicyPostPromotionMonitor(Base):
    __tablename__ = "policy_post_promotion_monitor"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("policy_promotion_pipeline.id"), nullable=False, index=True)
    decision_key = Column(String(255), nullable=True, index=True)
    off_policy_evaluation_key = Column(String(255), nullable=True, index=True)
    safety_simulation_key = Column(String(255), nullable=True, index=True)

    bundle_id = Column(String(255), nullable=False, index=True)
    arm_key = Column(String(255), nullable=False, index=True)

    status = Column(Enum(PolicyPostPromotionMonitorStatus), nullable=False, default=PolicyPostPromotionMonitorStatus.active)

    observed_uplift = Column(Float, nullable=True)
    observed_regression_risk = Column(Float, nullable=True)
    observed_safety_score = Column(Float, nullable=True)

    latest_metrics_json = Column(JSON, nullable=False, default=dict)
    alert_state_json = Column(JSON, nullable=False, default=dict)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
backend/app/repositories/policy_promotion_pipeline_repository.py
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_promotion_pipeline import PolicyPromotionPipeline


class PolicyPromotionPipelineRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, model: PolicyPromotionPipeline) -> PolicyPromotionPipeline:
        self.db.add(model)
        self.db.flush()
        return model

    def get(self, pipeline_id: UUID) -> Optional[PolicyPromotionPipeline]:
        return self.db.query(PolicyPromotionPipeline).filter(PolicyPromotionPipeline.id == pipeline_id).one_or_none()

    def get_by_key(self, pipeline_key: str) -> Optional[PolicyPromotionPipeline]:
        return (
            self.db.query(PolicyPromotionPipeline)
            .filter(PolicyPromotionPipeline.pipeline_key == pipeline_key)
            .one_or_none()
        )

    def save(self, model: PolicyPromotionPipeline) -> PolicyPromotionPipeline:
        self.db.add(model)
        self.db.flush()
        return model

    def list_waiting_manual_review(self) -> Sequence[PolicyPromotionPipeline]:
        return (
            self.db.query(PolicyPromotionPipeline)
            .filter(PolicyPromotionPipeline.status == "waiting_manual_review")
            .all()
        )
backend/app/repositories/policy_promotion_pipeline_stage_event_repository.py
from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_promotion_pipeline_stage_event import PolicyPromotionPipelineStageEvent


class PolicyPromotionPipelineStageEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, model: PolicyPromotionPipelineStageEvent) -> PolicyPromotionPipelineStageEvent:
        self.db.add(model)
        self.db.flush()
        return model

    def list_by_pipeline_id(self, pipeline_id: UUID) -> Sequence[PolicyPromotionPipelineStageEvent]:
        return (
            self.db.query(PolicyPromotionPipelineStageEvent)
            .filter(PolicyPromotionPipelineStageEvent.pipeline_id == pipeline_id)
            .order_by(PolicyPromotionPipelineStageEvent.created_at.asc())
            .all()
        )
backend/app/repositories/policy_manual_review_queue_item_repository.py
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_manual_review_queue_item import PolicyManualReviewQueueItem


class PolicyManualReviewQueueItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, model: PolicyManualReviewQueueItem) -> PolicyManualReviewQueueItem:
        self.db.add(model)
        self.db.flush()
        return model

    def get(self, queue_item_id: UUID) -> Optional[PolicyManualReviewQueueItem]:
        return self.db.query(PolicyManualReviewQueueItem).filter(PolicyManualReviewQueueItem.id == queue_item_id).one_or_none()

    def list_pending(self) -> Sequence[PolicyManualReviewQueueItem]:
        return (
            self.db.query(PolicyManualReviewQueueItem)
            .filter(PolicyManualReviewQueueItem.status.in_(["pending", "in_review", "escalated"]))
            .order_by(PolicyManualReviewQueueItem.created_at.asc())
            .all()
        )

    def save(self, model: PolicyManualReviewQueueItem) -> PolicyManualReviewQueueItem:
        self.db.add(model)
        self.db.flush()
        return model
backend/app/repositories/policy_manual_review_action_repository.py
from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_manual_review_action import PolicyManualReviewAction


class PolicyManualReviewActionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, model: PolicyManualReviewAction) -> PolicyManualReviewAction:
        self.db.add(model)
        self.db.flush()
        return model

    def list_by_queue_item_id(self, queue_item_id: UUID) -> Sequence[PolicyManualReviewAction]:
        return (
            self.db.query(PolicyManualReviewAction)
            .filter(PolicyManualReviewAction.queue_item_id == queue_item_id)
            .order_by(PolicyManualReviewAction.created_at.asc())
            .all()
        )
backend/app/repositories/policy_rollback_investigation_repository.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_rollback_investigation import PolicyRollbackInvestigation


class PolicyRollbackInvestigationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, model: PolicyRollbackInvestigation) -> PolicyRollbackInvestigation:
        self.db.add(model)
        self.db.flush()
        return model

    def get(self, investigation_id: UUID) -> Optional[PolicyRollbackInvestigation]:
        return (
            self.db.query(PolicyRollbackInvestigation)
            .filter(PolicyRollbackInvestigation.id == investigation_id)
            .one_or_none()
        )

    def get_by_pipeline_id(self, pipeline_id: UUID) -> Optional[PolicyRollbackInvestigation]:
        return (
            self.db.query(PolicyRollbackInvestigation)
            .filter(PolicyRollbackInvestigation.pipeline_id == pipeline_id)
            .one_or_none()
        )

    def save(self, model: PolicyRollbackInvestigation) -> PolicyRollbackInvestigation:
        self.db.add(model)
        self.db.flush()
        return model
backend/app/repositories/policy_rollback_investigation_timeline_event_repository.py
from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_rollback_investigation_timeline_event import PolicyRollbackInvestigationTimelineEvent


class PolicyRollbackInvestigationTimelineEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, model: PolicyRollbackInvestigationTimelineEvent) -> PolicyRollbackInvestigationTimelineEvent:
        self.db.add(model)
        self.db.flush()
        return model

    def list_by_investigation_id(self, investigation_id: UUID) -> Sequence[PolicyRollbackInvestigationTimelineEvent]:
        return (
            self.db.query(PolicyRollbackInvestigationTimelineEvent)
            .filter(PolicyRollbackInvestigationTimelineEvent.investigation_id == investigation_id)
            .order_by(PolicyRollbackInvestigationTimelineEvent.created_at.asc())
            .all()
        )
backend/app/repositories/policy_post_promotion_monitor_repository.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.policy_post_promotion_monitor import PolicyPostPromotionMonitor


class PolicyPostPromotionMonitorRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, model: PolicyPostPromotionMonitor) -> PolicyPostPromotionMonitor:
        self.db.add(model)
        self.db.flush()
        return model

    def get(self, monitor_id: UUID) -> Optional[PolicyPostPromotionMonitor]:
        return (
            self.db.query(PolicyPostPromotionMonitor)
            .filter(PolicyPostPromotionMonitor.id == monitor_id)
            .one_or_none()
        )

    def get_by_pipeline_id(self, pipeline_id: UUID) -> Optional[PolicyPostPromotionMonitor]:
        return (
            self.db.query(PolicyPostPromotionMonitor)
            .filter(PolicyPostPromotionMonitor.pipeline_id == pipeline_id)
            .one_or_none()
        )

    def save(self, model: PolicyPostPromotionMonitor) -> PolicyPostPromotionMonitor:
        self.db.add(model)
        self.db.flush()
        return model
backend/app/schemas/policy_promotion_operations.py
from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PolicyPromotionPipelineCreateRequest(BaseModel):
    pipeline_key: str
    experiment_key: Optional[str] = None
    bundle_id: str
    arm_key: str
    decision_key: Optional[str] = None
    off_policy_evaluation_key: Optional[str] = None
    safety_simulation_key: Optional[str] = None
    config_json: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class PolicyPromotionPipelineAdvanceRequest(BaseModel):
    pipeline_key: str
    next_stage: str
    payload_json: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None


class PolicyManualReviewQueueCreateRequest(BaseModel):
    pipeline_key: str
    decision_key: Optional[str] = None
    bundle_id: str
    arm_key: str
    priority: str = "normal"
    review_context_json: Dict[str, Any] = Field(default_factory=dict)
    assigned_reviewer_id: Optional[str] = None
    escalation_reviewer_id: Optional[str] = None
    notes: Optional[str] = None


class PolicyManualReviewActionRequest(BaseModel):
    queue_item_id: str
    action_type: str
    reason: Optional[str] = None
    payload_json: Dict[str, Any] = Field(default_factory=dict)


class PolicyRollbackInvestigationOpenRequest(BaseModel):
    pipeline_key: str
    bundle_id: str
    arm_key: str
    rollback_reason: Optional[str] = None
    evidence_json: Dict[str, Any] = Field(default_factory=dict)
    assigned_owner_id: Optional[str] = None


class PolicyRollbackInvestigationEventRequest(BaseModel):
    investigation_id: str
    event_type: str
    summary: Optional[str] = None
    payload_json: Dict[str, Any] = Field(default_factory=dict)


class PolicyPostPromotionMonitorUpsertRequest(BaseModel):
    pipeline_key: str
    decision_key: Optional[str] = None
    off_policy_evaluation_key: Optional[str] = None
    safety_simulation_key: Optional[str] = None
    bundle_id: str
    arm_key: str
    observed_uplift: Optional[float] = None
    observed_regression_risk: Optional[float] = None
    observed_safety_score: Optional[float] = None
    latest_metrics_json: Dict[str, Any] = Field(default_factory=dict)
    alert_state_json: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
backend/app/services/policy_promotion_pipeline_service.py
from __future__ import annotations

from typing import Dict, Any

from app.models.policy_promotion_pipeline import PolicyPromotionPipeline, PolicyPromotionPipelineStatus
from app.models.policy_promotion_pipeline_stage_event import PolicyPromotionPipelineStageEvent
from app.repositories.policy_promotion_pipeline_repository import PolicyPromotionPipelineRepository
from app.repositories.policy_promotion_pipeline_stage_event_repository import PolicyPromotionPipelineStageEventRepository


class PolicyPromotionPipelineService:
    def __init__(
        self,
        pipeline_repo: PolicyPromotionPipelineRepository,
        stage_event_repo: PolicyPromotionPipelineStageEventRepository,
        bundle_lifecycle_service=None,
        alert_service=None,
    ) -> None:
        self.pipeline_repo = pipeline_repo
        self.stage_event_repo = stage_event_repo
        self.bundle_lifecycle_service = bundle_lifecycle_service
        self.alert_service = alert_service

    def create_pipeline(
        self,
        pipeline_key: str,
        experiment_key: str | None,
        bundle_id: str,
        arm_key: str,
        decision_key: str | None,
        off_policy_evaluation_key: str | None,
        safety_simulation_key: str | None,
        config_json: Dict[str, Any],
        notes: str | None,
        actor_id: str,
    ) -> PolicyPromotionPipeline:
        model = PolicyPromotionPipeline(
            pipeline_key=pipeline_key,
            experiment_key=experiment_key,
            bundle_id=bundle_id,
            arm_key=arm_key,
            decision_key=decision_key,
            off_policy_evaluation_key=off_policy_evaluation_key,
            safety_simulation_key=safety_simulation_key,
            config_json=config_json,
            notes=notes,
            status=PolicyPromotionPipelineStatus.pending,
            current_stage="evidence_ready",
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.pipeline_repo.create(model)

        self.stage_event_repo.create(
            PolicyPromotionPipelineStageEvent(
                pipeline_id=model.id,
                stage_name="evidence_ready",
                event_type="pipeline_created",
                actor_id=actor_id,
                summary="Promotion pipeline created",
                payload_json={},
            )
        )
        return model

    def advance_stage(
        self,
        pipeline_key: str,
        next_stage: str,
        payload_json: Dict[str, Any],
        summary: str | None,
        actor_id: str,
    ) -> PolicyPromotionPipeline:
        pipeline = self.pipeline_repo.get_by_key(pipeline_key)
        if pipeline is None:
            raise ValueError(f"Pipeline not found: {pipeline_key}")

        pipeline.current_stage = next_stage
        pipeline.updated_by = actor_id
        pipeline.stage_context_json = payload_json or {}

        if next_stage == "committee_review":
            pipeline.status = PolicyPromotionPipelineStatus.running
        elif next_stage == "manual_review":
            pipeline.status = PolicyPromotionPipelineStatus.waiting_manual_review
        elif next_stage == "approved":
            pipeline.status = PolicyPromotionPipelineStatus.approved
        elif next_stage == "canary_live":
            pipeline.status = PolicyPromotionPipelineStatus.canary_live
        elif next_stage == "promoted_live":
            pipeline.status = PolicyPromotionPipelineStatus.promoted_live
            if self.bundle_lifecycle_service is not None:
                self.bundle_lifecycle_service.promote_bundle(
                    bundle_id=pipeline.bundle_id,
                    reason="promotion_pipeline_promoted_live",
                    metadata={"pipeline_key": pipeline.pipeline_key, "arm_key": pipeline.arm_key},
                )
        elif next_stage == "rolled_back":
            pipeline.status = PolicyPromotionPipelineStatus.rolled_back
            if self.bundle_lifecycle_service is not None:
                self.bundle_lifecycle_service.rollback_bundle(
                    bundle_id=pipeline.bundle_id,
                    reason="promotion_pipeline_rollback",
                    metadata={"pipeline_key": pipeline.pipeline_key, "arm_key": pipeline.arm_key},
                )
            if self.alert_service is not None:
                self.alert_service.emit(
                    event_type="policy_pipeline_rolled_back",
                    payload={"pipeline_key": pipeline.pipeline_key, "bundle_id": pipeline.bundle_id},
                )
        elif next_stage == "rejected":
            pipeline.status = PolicyPromotionPipelineStatus.rejected
        elif next_stage == "completed":
            pipeline.status = PolicyPromotionPipelineStatus.completed

        self.pipeline_repo.save(pipeline)

        self.stage_event_repo.create(
            PolicyPromotionPipelineStageEvent(
                pipeline_id=pipeline.id,
                stage_name=next_stage,
                event_type="stage_advanced",
                actor_id=actor_id,
                summary=summary,
                payload_json=payload_json or {},
            )
        )
        return pipeline
backend/app/services/policy_manual_review_workbench_service.py
from __future__ import annotations

from datetime import datetime, timedelta

from app.models.policy_manual_review_queue_item import PolicyManualReviewQueueItem, PolicyManualReviewQueueItemStatus
from app.models.policy_manual_review_action import PolicyManualReviewAction
from app.repositories.policy_promotion_pipeline_repository import PolicyPromotionPipelineRepository
from app.repositories.policy_promotion_pipeline_stage_event_repository import PolicyPromotionPipelineStageEventRepository
from app.repositories.policy_manual_review_queue_item_repository import PolicyManualReviewQueueItemRepository
from app.repositories.policy_manual_review_action_repository import PolicyManualReviewActionRepository
from app.models.policy_promotion_pipeline_stage_event import PolicyPromotionPipelineStageEvent


class PolicyManualReviewWorkbenchService:
    def __init__(
        self,
        pipeline_repo: PolicyPromotionPipelineRepository,
        stage_event_repo: PolicyPromotionPipelineStageEventRepository,
        queue_repo: PolicyManualReviewQueueItemRepository,
        action_repo: PolicyManualReviewActionRepository,
    ) -> None:
        self.pipeline_repo = pipeline_repo
        self.stage_event_repo = stage_event_repo
        self.queue_repo = queue_repo
        self.action_repo = action_repo

    def create_queue_item(
        self,
        pipeline_key: str,
        decision_key: str | None,
        bundle_id: str,
        arm_key: str,
        priority: str,
        review_context_json: dict,
        assigned_reviewer_id: str | None,
        escalation_reviewer_id: str | None,
        notes: str | None,
        actor_id: str,
    ) -> PolicyManualReviewQueueItem:
        pipeline = self.pipeline_repo.get_by_key(pipeline_key)
        if pipeline is None:
            raise ValueError(f"Pipeline not found: {pipeline_key}")

        sla_due_at = datetime.utcnow() + timedelta(hours=24 if priority == "normal" else 4)

        item = PolicyManualReviewQueueItem(
            pipeline_id=pipeline.id,
            decision_key=decision_key,
            bundle_id=bundle_id,
            arm_key=arm_key,
            priority=priority,
            review_context_json=review_context_json,
            assigned_reviewer_id=assigned_reviewer_id,
            escalation_reviewer_id=escalation_reviewer_id,
            notes=notes,
            sla_due_at=sla_due_at,
            created_by=actor_id,
            updated_by=actor_id,
            status=PolicyManualReviewQueueItemStatus.pending,
        )
        self.queue_repo.create(item)

        pipeline.status = "waiting_manual_review"
        pipeline.current_stage = "manual_review"
        self.pipeline_repo.save(pipeline)

        self.stage_event_repo.create(
            PolicyPromotionPipelineStageEvent(
                pipeline_id=pipeline.id,
                stage_name="manual_review",
                event_type="review_queue_created",
                actor_id=actor_id,
                summary="Manual review queue item created",
                payload_json={"queue_item_id": str(item.id), "priority": priority},
            )
        )
        return item

    def apply_action(
        self,
        queue_item_id,
        action_type: str,
        reason: str | None,
        payload_json: dict,
        actor_id: str,
    ) -> PolicyManualReviewQueueItem:
        item = self.queue_repo.get(queue_item_id)
        if item is None:
            raise ValueError(f"Queue item not found: {queue_item_id}")

        action = PolicyManualReviewAction(
            queue_item_id=item.id,
            action_type=action_type,
            actor_id=actor_id,
            reason=reason,
            payload_json=payload_json or {},
        )
        self.action_repo.create(action)

        pipeline = self.pipeline_repo.get(item.pipeline_id)
        if pipeline is None:
            raise ValueError(f"Pipeline not found for queue item: {queue_item_id}")

        if action_type == "claim":
            item.status = PolicyManualReviewQueueItemStatus.in_review
            if not item.assigned_reviewer_id:
                item.assigned_reviewer_id = actor_id
        elif action_type == "approve":
            item.status = PolicyManualReviewQueueItemStatus.approved
            pipeline.status = "approved"
            pipeline.current_stage = "approved"
        elif action_type == "reject":
            item.status = PolicyManualReviewQueueItemStatus.rejected
            pipeline.status = "rejected"
            pipeline.current_stage = "rejected"
        elif action_type == "request_changes":
            item.status = PolicyManualReviewQueueItemStatus.changes_requested
        elif action_type == "escalate":
            item.status = PolicyManualReviewQueueItemStatus.escalated
        elif action_type == "close":
            item.status = PolicyManualReviewQueueItemStatus.closed

        item.updated_by = actor_id
        self.queue_repo.save(item)
        self.pipeline_repo.save(pipeline)

        self.stage_event_repo.create(
            PolicyPromotionPipelineStageEvent(
                pipeline_id=pipeline.id,
                stage_name="manual_review",
                event_type=f"review_action_{action_type}",
                actor_id=actor_id,
                summary=reason,
                payload_json={"queue_item_id": str(item.id), **(payload_json or {})},
            )
        )
        return item
backend/app/services/policy_rollback_investigation_service.py
from __future__ import annotations

from app.models.policy_rollback_investigation import PolicyRollbackInvestigation, PolicyRollbackInvestigationStatus
from app.models.policy_rollback_investigation_timeline_event import PolicyRollbackInvestigationTimelineEvent
from app.repositories.policy_promotion_pipeline_repository import PolicyPromotionPipelineRepository
from app.repositories.policy_rollback_investigation_repository import PolicyRollbackInvestigationRepository
from app.repositories.policy_rollback_investigation_timeline_event_repository import PolicyRollbackInvestigationTimelineEventRepository


class PolicyRollbackInvestigationService:
    def __init__(
        self,
        pipeline_repo: PolicyPromotionPipelineRepository,
        investigation_repo: PolicyRollbackInvestigationRepository,
        timeline_repo: PolicyRollbackInvestigationTimelineEventRepository,
    ) -> None:
        self.pipeline_repo = pipeline_repo
        self.investigation_repo = investigation_repo
        self.timeline_repo = timeline_repo

    def open_investigation(
        self,
        pipeline_key: str,
        bundle_id: str,
        arm_key: str,
        rollback_reason: str | None,
        evidence_json: dict,
        assigned_owner_id: str | None,
        actor_id: str,
    ) -> PolicyRollbackInvestigation:
        pipeline = self.pipeline_repo.get_by_key(pipeline_key)
        if pipeline is None:
            raise ValueError(f"Pipeline not found: {pipeline_key}")

        existing = self.investigation_repo.get_by_pipeline_id(pipeline.id)
        if existing is not None:
            return existing

        model = PolicyRollbackInvestigation(
            pipeline_id=pipeline.id,
            bundle_id=bundle_id,
            arm_key=arm_key,
            rollback_reason=rollback_reason,
            evidence_json=evidence_json or {},
            assigned_owner_id=assigned_owner_id,
            opened_by=actor_id,
            status=PolicyRollbackInvestigationStatus.open,
        )
        self.investigation_repo.create(model)

        self.timeline_repo.create(
            PolicyRollbackInvestigationTimelineEvent(
                investigation_id=model.id,
                event_type="investigation_opened",
                actor_id=actor_id,
                summary="Rollback investigation opened",
                payload_json=evidence_json or {},
            )
        )
        return model

    def add_timeline_event(
        self,
        investigation_id,
        event_type: str,
        summary: str | None,
        payload_json: dict,
        actor_id: str,
    ) -> PolicyRollbackInvestigationTimelineEvent:
        investigation = self.investigation_repo.get(investigation_id)
        if investigation is None:
            raise ValueError(f"Investigation not found: {investigation_id}")

        if event_type == "started":
            investigation.status = PolicyRollbackInvestigationStatus.in_progress
            self.investigation_repo.save(investigation)
        elif event_type == "resolved":
            investigation.status = PolicyRollbackInvestigationStatus.resolved
            investigation.resolution_summary = summary
            self.investigation_repo.save(investigation)
        elif event_type == "closed":
            investigation.status = PolicyRollbackInvestigationStatus.closed
            self.investigation_repo.save(investigation)

        return self.timeline_repo.create(
            PolicyRollbackInvestigationTimelineEvent(
                investigation_id=investigation.id,
                event_type=event_type,
                actor_id=actor_id,
                summary=summary,
                payload_json=payload_json or {},
            )
        )
backend/app/services/policy_post_promotion_monitor_service.py
from __future__ import annotations

from app.models.policy_post_promotion_monitor import PolicyPostPromotionMonitor, PolicyPostPromotionMonitorStatus
from app.repositories.policy_promotion_pipeline_repository import PolicyPromotionPipelineRepository
from app.repositories.policy_promotion_pipeline_stage_event_repository import PolicyPromotionPipelineStageEventRepository
from app.repositories.policy_post_promotion_monitor_repository import PolicyPostPromotionMonitorRepository
from app.models.policy_promotion_pipeline_stage_event import PolicyPromotionPipelineStageEvent


class PolicyPostPromotionMonitorService:
    def __init__(
        self,
        pipeline_repo: PolicyPromotionPipelineRepository,
        stage_event_repo: PolicyPromotionPipelineStageEventRepository,
        monitor_repo: PolicyPostPromotionMonitorRepository,
    ) -> None:
        self.pipeline_repo = pipeline_repo
        self.stage_event_repo = stage_event_repo
        self.monitor_repo = monitor_repo

    def upsert_monitor(
        self,
        pipeline_key: str,
        decision_key: str | None,
        off_policy_evaluation_key: str | None,
        safety_simulation_key: str | None,
        bundle_id: str,
        arm_key: str,
        observed_uplift: float | None,
        observed_regression_risk: float | None,
        observed_safety_score: float | None,
        latest_metrics_json: dict,
        alert_state_json: dict,
        notes: str | None,
        actor_id: str,
    ) -> PolicyPostPromotionMonitor:
        pipeline = self.pipeline_repo.get_by_key(pipeline_key)
        if pipeline is None:
            raise ValueError(f"Pipeline not found: {pipeline_key}")

        monitor = self.monitor_repo.get_by_pipeline_id(pipeline.id)
        if monitor is None:
            monitor = PolicyPostPromotionMonitor(
                pipeline_id=pipeline.id,
                decision_key=decision_key,
                off_policy_evaluation_key=off_policy_evaluation_key,
                safety_simulation_key=safety_simulation_key,
                bundle_id=bundle_id,
                arm_key=arm_key,
            )
            self.monitor_repo.create(monitor)

        monitor.observed_uplift = observed_uplift
        monitor.observed_regression_risk = observed_regression_risk
        monitor.observed_safety_score = observed_safety_score
        monitor.latest_metrics_json = latest_metrics_json or {}
        monitor.alert_state_json = alert_state_json or {}
        monitor.notes = notes

        if (observed_regression_risk or 0.0) > 0.40:
            monitor.status = PolicyPostPromotionMonitorStatus.rollback_candidate
        elif (observed_safety_score or 1.0) < 0.60:
            monitor.status = PolicyPostPromotionMonitorStatus.warning
        elif (observed_uplift or 0.0) > 0 and (observed_regression_risk or 0.0) <= 0.20:
            monitor.status = PolicyPostPromotionMonitorStatus.stable
        else:
            monitor.status = PolicyPostPromotionMonitorStatus.active

        self.monitor_repo.save(monitor)

        self.stage_event_repo.create(
            PolicyPromotionPipelineStageEvent(
                pipeline_id=pipeline.id,
                stage_name="post_promotion_monitoring",
                event_type="monitor_updated",
                actor_id=actor_id,
                summary="Post-promotion monitor updated",
                payload_json={
                    "monitor_status": monitor.status.value,
                    "observed_uplift": observed_uplift,
                    "observed_regression_risk": observed_regression_risk,
                    "observed_safety_score": observed_safety_score,
                },
            )
        )
        return monitor
backend/app/services/policy_promotion_operations_orchestrator_service.py
from __future__ import annotations

from app.repositories.policy_promotion_pipeline_repository import PolicyPromotionPipelineRepository
from app.repositories.policy_promotion_pipeline_stage_event_repository import PolicyPromotionPipelineStageEventRepository
from app.repositories.policy_manual_review_queue_item_repository import PolicyManualReviewQueueItemRepository
from app.repositories.policy_manual_review_action_repository import PolicyManualReviewActionRepository
from app.repositories.policy_rollback_investigation_repository import PolicyRollbackInvestigationRepository
from app.repositories.policy_rollback_investigation_timeline_event_repository import PolicyRollbackInvestigationTimelineEventRepository
from app.repositories.policy_post_promotion_monitor_repository import PolicyPostPromotionMonitorRepository
from app.services.policy_promotion_pipeline_service import PolicyPromotionPipelineService
from app.services.policy_manual_review_workbench_service import PolicyManualReviewWorkbenchService
from app.services.policy_rollback_investigation_service import PolicyRollbackInvestigationService
from app.services.policy_post_promotion_monitor_service import PolicyPostPromotionMonitorService


class PolicyPromotionOperationsOrchestratorService:
    def __init__(self, db, bundle_lifecycle_service=None, alert_service=None) -> None:
        self.pipeline_service = PolicyPromotionPipelineService(
            pipeline_repo=PolicyPromotionPipelineRepository(db),
            stage_event_repo=PolicyPromotionPipelineStageEventRepository(db),
            bundle_lifecycle_service=bundle_lifecycle_service,
            alert_service=alert_service,
        )
        self.review_service = PolicyManualReviewWorkbenchService(
            pipeline_repo=PolicyPromotionPipelineRepository(db),
            stage_event_repo=PolicyPromotionPipelineStageEventRepository(db),
            queue_repo=PolicyManualReviewQueueItemRepository(db),
            action_repo=PolicyManualReviewActionRepository(db),
        )
        self.investigation_service = PolicyRollbackInvestigationService(
            pipeline_repo=PolicyPromotionPipelineRepository(db),
            investigation_repo=PolicyRollbackInvestigationRepository(db),
            timeline_repo=PolicyRollbackInvestigationTimelineEventRepository(db),
        )
        self.monitor_service = PolicyPostPromotionMonitorService(
            pipeline_repo=PolicyPromotionPipelineRepository(db),
            stage_event_repo=PolicyPromotionPipelineStageEventRepository(db),
            monitor_repo=PolicyPostPromotionMonitorRepository(db),
        )
backend/app/api/policy_promotion_operations.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_actor_id
from app.repositories.policy_promotion_pipeline_repository import PolicyPromotionPipelineRepository
from app.repositories.policy_promotion_pipeline_stage_event_repository import PolicyPromotionPipelineStageEventRepository
from app.repositories.policy_manual_review_queue_item_repository import PolicyManualReviewQueueItemRepository
from app.repositories.policy_manual_review_action_repository import PolicyManualReviewActionRepository
from app.repositories.policy_rollback_investigation_repository import PolicyRollbackInvestigationRepository
from app.repositories.policy_rollback_investigation_timeline_event_repository import PolicyRollbackInvestigationTimelineEventRepository
from app.repositories.policy_post_promotion_monitor_repository import PolicyPostPromotionMonitorRepository
from app.schemas.policy_promotion_operations import (
    PolicyPromotionPipelineCreateRequest,
    PolicyPromotionPipelineAdvanceRequest,
    PolicyManualReviewQueueCreateRequest,
    PolicyManualReviewActionRequest,
    PolicyRollbackInvestigationOpenRequest,
    PolicyRollbackInvestigationEventRequest,
    PolicyPostPromotionMonitorUpsertRequest,
)
from app.services.policy_promotion_pipeline_service import PolicyPromotionPipelineService
from app.services.policy_manual_review_workbench_service import PolicyManualReviewWorkbenchService
from app.services.policy_rollback_investigation_service import PolicyRollbackInvestigationService
from app.services.policy_post_promotion_monitor_service import PolicyPostPromotionMonitorService

router = APIRouter(prefix="/policy-promotion-operations", tags=["policy-promotion-operations"])


@router.post("/pipeline")
def create_promotion_pipeline(
    payload: PolicyPromotionPipelineCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicyPromotionPipelineService(
        pipeline_repo=PolicyPromotionPipelineRepository(db),
        stage_event_repo=PolicyPromotionPipelineStageEventRepository(db),
    )
    model = service.create_pipeline(
        pipeline_key=payload.pipeline_key,
        experiment_key=payload.experiment_key,
        bundle_id=payload.bundle_id,
        arm_key=payload.arm_key,
        decision_key=payload.decision_key,
        off_policy_evaluation_key=payload.off_policy_evaluation_key,
        safety_simulation_key=payload.safety_simulation_key,
        config_json=payload.config_json,
        notes=payload.notes,
        actor_id=actor_id,
    )
    db.commit()
    return {"pipeline_id": str(model.id), "pipeline_key": model.pipeline_key, "status": model.status.value}


@router.post("/pipeline/advance")
def advance_promotion_pipeline(
    payload: PolicyPromotionPipelineAdvanceRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicyPromotionPipelineService(
        pipeline_repo=PolicyPromotionPipelineRepository(db),
        stage_event_repo=PolicyPromotionPipelineStageEventRepository(db),
    )
    try:
        model = service.advance_stage(
            pipeline_key=payload.pipeline_key,
            next_stage=payload.next_stage,
            payload_json=payload.payload_json,
            summary=payload.summary,
            actor_id=actor_id,
        )
        db.commit()
        return {
            "pipeline_id": str(model.id),
            "pipeline_key": model.pipeline_key,
            "status": model.status.value,
            "current_stage": model.current_stage,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/manual-review/queue-item")
def create_manual_review_queue_item(
    payload: PolicyManualReviewQueueCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicyManualReviewWorkbenchService(
        pipeline_repo=PolicyPromotionPipelineRepository(db),
        stage_event_repo=PolicyPromotionPipelineStageEventRepository(db),
        queue_repo=PolicyManualReviewQueueItemRepository(db),
        action_repo=PolicyManualReviewActionRepository(db),
    )
    try:
        item = service.create_queue_item(
            pipeline_key=payload.pipeline_key,
            decision_key=payload.decision_key,
            bundle_id=payload.bundle_id,
            arm_key=payload.arm_key,
            priority=payload.priority,
            review_context_json=payload.review_context_json,
            assigned_reviewer_id=payload.assigned_reviewer_id,
            escalation_reviewer_id=payload.escalation_reviewer_id,
            notes=payload.notes,
            actor_id=actor_id,
        )
        db.commit()
        return {"queue_item_id": str(item.id), "status": item.status.value}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/manual-review/action")
def apply_manual_review_action(
    payload: PolicyManualReviewActionRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicyManualReviewWorkbenchService(
        pipeline_repo=PolicyPromotionPipelineRepository(db),
        stage_event_repo=PolicyPromotionPipelineStageEventRepository(db),
        queue_repo=PolicyManualReviewQueueItemRepository(db),
        action_repo=PolicyManualReviewActionRepository(db),
    )
    try:
        item = service.apply_action(
            queue_item_id=payload.queue_item_id,
            action_type=payload.action_type,
            reason=payload.reason,
            payload_json=payload.payload_json,
            actor_id=actor_id,
        )
        db.commit()
        return {"queue_item_id": str(item.id), "status": item.status.value}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/rollback-investigation/open")
def open_rollback_investigation(
    payload: PolicyRollbackInvestigationOpenRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicyRollbackInvestigationService(
        pipeline_repo=PolicyPromotionPipelineRepository(db),
        investigation_repo=PolicyRollbackInvestigationRepository(db),
        timeline_repo=PolicyRollbackInvestigationTimelineEventRepository(db),
    )
    try:
        model = service.open_investigation(
            pipeline_key=payload.pipeline_key,
            bundle_id=payload.bundle_id,
            arm_key=payload.arm_key,
            rollback_reason=payload.rollback_reason,
            evidence_json=payload.evidence_json,
            assigned_owner_id=payload.assigned_owner_id,
            actor_id=actor_id,
        )
        db.commit()
        return {"investigation_id": str(model.id), "status": model.status.value}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/rollback-investigation/event")
def add_rollback_investigation_event(
    payload: PolicyRollbackInvestigationEventRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicyRollbackInvestigationService(
        pipeline_repo=PolicyPromotionPipelineRepository(db),
        investigation_repo=PolicyRollbackInvestigationRepository(db),
        timeline_repo=PolicyRollbackInvestigationTimelineEventRepository(db),
    )
    try:
        event = service.add_timeline_event(
            investigation_id=payload.investigation_id,
            event_type=payload.event_type,
            summary=payload.summary,
            payload_json=payload.payload_json,
            actor_id=actor_id,
        )
        db.commit()
        return {"event_id": str(event.id), "event_type": event.event_type}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/post-promotion-monitor")
def upsert_post_promotion_monitor(
    payload: PolicyPostPromotionMonitorUpsertRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(get_actor_id),
):
    service = PolicyPostPromotionMonitorService(
        pipeline_repo=PolicyPromotionPipelineRepository(db),
        stage_event_repo=PolicyPromotionPipelineStageEventRepository(db),
        monitor_repo=PolicyPostPromotionMonitorRepository(db),
    )
    try:
        model = service.upsert_monitor(
            pipeline_key=payload.pipeline_key,
            decision_key=payload.decision_key,
            off_policy_evaluation_key=payload.off_policy_evaluation_key,
            safety_simulation_key=payload.safety_simulation_key,
            bundle_id=payload.bundle_id,
            arm_key=payload.arm_key,
            observed_uplift=payload.observed_uplift,
            observed_regression_risk=payload.observed_regression_risk,
            observed_safety_score=payload.observed_safety_score,
            latest_metrics_json=payload.latest_metrics_json,
            alert_state_json=payload.alert_state_json,
            notes=payload.notes,
            actor_id=actor_id,
        )
        db.commit()
        return {"monitor_id": str(model.id), "status": model.status.value}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
backend/app/workers/policy_promotion_operations_worker.py
from __future__ import annotations

from app.db.session import SessionLocal
from app.repositories.policy_promotion_pipeline_repository import PolicyPromotionPipelineRepository
from app.repositories.policy_promotion_pipeline_stage_event_repository import PolicyPromotionPipelineStageEventRepository
from app.repositories.policy_manual_review_queue_item_repository import PolicyManualReviewQueueItemRepository
from app.repositories.policy_manual_review_action_repository import PolicyManualReviewActionRepository
from app.repositories.policy_rollback_investigation_repository import PolicyRollbackInvestigationRepository
from app.repositories.policy_rollback_investigation_timeline_event_repository import PolicyRollbackInvestigationTimelineEventRepository
from app.repositories.policy_post_promotion_monitor_repository import PolicyPostPromotionMonitorRepository
from app.services.policy_promotion_pipeline_service import PolicyPromotionPipelineService
from app.services.policy_manual_review_workbench_service import PolicyManualReviewWorkbenchService
from app.services.policy_rollback_investigation_service import PolicyRollbackInvestigationService
from app.services.policy_post_promotion_monitor_service import PolicyPostPromotionMonitorService


def run_post_promotion_monitor_check(
    pipeline_key: str,
    metrics: dict,
    actor_id: str = "system",
) -> dict:
    db = SessionLocal()
    try:
        pipeline_repo = PolicyPromotionPipelineRepository(db)
        pipeline = pipeline_repo.get_by_key(pipeline_key)
        if pipeline is None:
            raise ValueError(f"Pipeline not found: {pipeline_key}")

        monitor_service = PolicyPostPromotionMonitorService(
            pipeline_repo=pipeline_repo,
            stage_event_repo=PolicyPromotionPipelineStageEventRepository(db),
            monitor_repo=PolicyPostPromotionMonitorRepository(db),
        )

        monitor = monitor_service.upsert_monitor(
            pipeline_key=pipeline_key,
            decision_key=pipeline.decision_key,
            off_policy_evaluation_key=pipeline.off_policy_evaluation_key,
            safety_simulation_key=pipeline.safety_simulation_key,
            bundle_id=pipeline.bundle_id,
            arm_key=pipeline.arm_key,
            observed_uplift=metrics.get("observed_uplift"),
            observed_regression_risk=metrics.get("observed_regression_risk"),
            observed_safety_score=metrics.get("observed_safety_score"),
            latest_metrics_json=metrics,
            alert_state_json=metrics.get("alert_state_json", {}),
            notes="Automated monitor refresh",
            actor_id=actor_id,
        )

        investigation_result = None
        if monitor.status.value == "rollback_candidate":
            investigation_service = PolicyRollbackInvestigationService(
                pipeline_repo=pipeline_repo,
                investigation_repo=PolicyRollbackInvestigationRepository(db),
                timeline_repo=PolicyRollbackInvestigationTimelineEventRepository(db),
            )
            inv = investigation_service.open_investigation(
                pipeline_key=pipeline_key,
                bundle_id=pipeline.bundle_id,
                arm_key=pipeline.arm_key,
                rollback_reason="post_promotion_regression_detected",
                evidence_json=metrics,
                assigned_owner_id=None,
                actor_id=actor_id,
            )
            investigation_result = {"investigation_id": str(inv.id), "status": inv.status.value}

        db.commit()
        return {
            "pipeline_key": pipeline_key,
            "monitor_status": monitor.status.value,
            "investigation": investigation_result,
        }
    finally:
        db.close()
backend/alembic/versions/20260412_0033_promotion_pipeline_review_investigation.py
"""promotion pipeline review investigation

Revision ID: 20260412_0033
Revises: 20260412_0032
Create Date: 2026-04-12 13:05:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260412_0033"
down_revision = "20260412_0032"
branch_labels = None
depends_on = None


policy_promotion_pipeline_status_enum = sa.Enum(
    "pending",
    "running",
    "waiting_manual_review",
    "approved",
    "rejected",
    "canary_live",
    "promoted_live",
    "rolled_back",
    "completed",
    "failed",
    name="policypromotionpipelinestatus",
)

policy_manual_review_queue_item_status_enum = sa.Enum(
    "pending",
    "in_review",
    "approved",
    "rejected",
    "changes_requested",
    "escalated",
    "closed",
    name="policymanualreviewqueueitemstatus",
)

policy_rollback_investigation_status_enum = sa.Enum(
    "open",
    "in_progress",
    "resolved",
    "closed",
    name="policyrollbackinvestigationstatus",
)

policy_post_promotion_monitor_status_enum = sa.Enum(
    "active",
    "warning",
    "rollback_candidate",
    "stable",
    "closed",
    name="policypostpromotionmonitorstatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    policy_promotion_pipeline_status_enum.create(bind, checkfirst=True)
    policy_manual_review_queue_item_status_enum.create(bind, checkfirst=True)
    policy_rollback_investigation_status_enum.create(bind, checkfirst=True)
    policy_post_promotion_monitor_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "policy_promotion_pipeline",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pipeline_key", sa.String(length=255), nullable=False),
        sa.Column("experiment_key", sa.String(length=255), nullable=True),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("arm_key", sa.String(length=255), nullable=False),
        sa.Column("decision_key", sa.String(length=255), nullable=True),
        sa.Column("off_policy_evaluation_key", sa.String(length=255), nullable=True),
        sa.Column("safety_simulation_key", sa.String(length=255), nullable=True),
        sa.Column("status", policy_promotion_pipeline_status_enum, nullable=False),
        sa.Column("current_stage", sa.String(length=128), nullable=False),
        sa.Column("stage_context_json", sa.JSON(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_promotion_pipeline_pipeline_key", "policy_promotion_pipeline", ["pipeline_key"], unique=True)
    op.create_index("ix_policy_promotion_pipeline_experiment_key", "policy_promotion_pipeline", ["experiment_key"], unique=False)
    op.create_index("ix_policy_promotion_pipeline_bundle_id", "policy_promotion_pipeline", ["bundle_id"], unique=False)
    op.create_index("ix_policy_promotion_pipeline_arm_key", "policy_promotion_pipeline", ["arm_key"], unique=False)
    op.create_index("ix_policy_promotion_pipeline_decision_key", "policy_promotion_pipeline", ["decision_key"], unique=False)

    op.create_table(
        "policy_promotion_pipeline_stage_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_promotion_pipeline.id"), nullable=False),
        sa.Column("stage_name", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_promotion_pipeline_stage_event_pipeline_id", "policy_promotion_pipeline_stage_event", ["pipeline_id"], unique=False)
    op.create_index("ix_policy_promotion_pipeline_stage_event_stage_name", "policy_promotion_pipeline_stage_event", ["stage_name"], unique=False)
    op.create_index("ix_policy_promotion_pipeline_stage_event_event_type", "policy_promotion_pipeline_stage_event", ["event_type"], unique=False)

    op.create_table(
        "policy_manual_review_queue_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_promotion_pipeline.id"), nullable=False),
        sa.Column("decision_key", sa.String(length=255), nullable=True),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("arm_key", sa.String(length=255), nullable=False),
        sa.Column("status", policy_manual_review_queue_item_status_enum, nullable=False),
        sa.Column("assigned_reviewer_id", sa.String(length=255), nullable=True),
        sa.Column("escalation_reviewer_id", sa.String(length=255), nullable=True),
        sa.Column("priority", sa.String(length=64), nullable=False),
        sa.Column("sla_due_at", sa.DateTime(), nullable=True),
        sa.Column("review_context_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_manual_review_queue_item_pipeline_id", "policy_manual_review_queue_item", ["pipeline_id"], unique=False)
    op.create_index("ix_policy_manual_review_queue_item_decision_key", "policy_manual_review_queue_item", ["decision_key"], unique=False)
    op.create_index("ix_policy_manual_review_queue_item_bundle_id", "policy_manual_review_queue_item", ["bundle_id"], unique=False)
    op.create_index("ix_policy_manual_review_queue_item_arm_key", "policy_manual_review_queue_item", ["arm_key"], unique=False)
    op.create_index("ix_policy_manual_review_queue_item_assigned_reviewer_id", "policy_manual_review_queue_item", ["assigned_reviewer_id"], unique=False)

    op.create_table(
        "policy_manual_review_action",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("queue_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_manual_review_queue_item.id"), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_manual_review_action_queue_item_id", "policy_manual_review_action", ["queue_item_id"], unique=False)
    op.create_index("ix_policy_manual_review_action_action_type", "policy_manual_review_action", ["action_type"], unique=False)
    op.create_index("ix_policy_manual_review_action_actor_id", "policy_manual_review_action", ["actor_id"], unique=False)

    op.create_table(
        "policy_rollback_investigation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_promotion_pipeline.id"), nullable=False),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("arm_key", sa.String(length=255), nullable=False),
        sa.Column("rollback_reason", sa.String(length=255), nullable=True),
        sa.Column("status", policy_rollback_investigation_status_enum, nullable=False),
        sa.Column("opened_by", sa.String(length=255), nullable=True),
        sa.Column("assigned_owner_id", sa.String(length=255), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("resolution_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_rollback_investigation_pipeline_id", "policy_rollback_investigation", ["pipeline_id"], unique=False)
    op.create_index("ix_policy_rollback_investigation_bundle_id", "policy_rollback_investigation", ["bundle_id"], unique=False)
    op.create_index("ix_policy_rollback_investigation_arm_key", "policy_rollback_investigation", ["arm_key"], unique=False)
    op.create_index("ix_policy_rollback_investigation_rollback_reason", "policy_rollback_investigation", ["rollback_reason"], unique=False)
    op.create_index("ix_policy_rollback_investigation_assigned_owner_id", "policy_rollback_investigation", ["assigned_owner_id"], unique=False)

    op.create_table(
        "policy_rollback_investigation_timeline_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_rollback_investigation.id"), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_rollback_investigation_timeline_event_investigation_id", "policy_rollback_investigation_timeline_event", ["investigation_id"], unique=False)
    op.create_index("ix_policy_rollback_investigation_timeline_event_event_type", "policy_rollback_investigation_timeline_event", ["event_type"], unique=False)
    op.create_index("ix_policy_rollback_investigation_timeline_event_actor_id", "policy_rollback_investigation_timeline_event", ["actor_id"], unique=False)

    op.create_table(
        "policy_post_promotion_monitor",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy_promotion_pipeline.id"), nullable=False),
        sa.Column("decision_key", sa.String(length=255), nullable=True),
        sa.Column("off_policy_evaluation_key", sa.String(length=255), nullable=True),
        sa.Column("safety_simulation_key", sa.String(length=255), nullable=True),
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("arm_key", sa.String(length=255), nullable=False),
        sa.Column("status", policy_post_promotion_monitor_status_enum, nullable=False),
        sa.Column("observed_uplift", sa.Float(), nullable=True),
        sa.Column("observed_regression_risk", sa.Float(), nullable=True),
        sa.Column("observed_safety_score", sa.Float(), nullable=True),
        sa.Column("latest_metrics_json", sa.JSON(), nullable=False),
        sa.Column("alert_state_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_policy_post_promotion_monitor_pipeline_id", "policy_post_promotion_monitor", ["pipeline_id"], unique=False)
    op.create_index("ix_policy_post_promotion_monitor_decision_key", "policy_post_promotion_monitor", ["decision_key"], unique=False)
    op.create_index("ix_policy_post_promotion_monitor_bundle_id", "policy_post_promotion_monitor", ["bundle_id"], unique=False)
    op.create_index("ix_policy_post_promotion_monitor_arm_key", "policy_post_promotion_monitor", ["arm_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_policy_post_promotion_monitor_arm_key", table_name="policy_post_promotion_monitor")
    op.drop_index("ix_policy_post_promotion_monitor_bundle_id", table_name="policy_post_promotion_monitor")
    op.drop_index("ix_policy_post_promotion_monitor_decision_key", table_name="policy_post_promotion_monitor")
    op.drop_index("ix_policy_post_promotion_monitor_pipeline_id", table_name="policy_post_promotion_monitor")
    op.drop_table("policy_post_promotion_monitor")

    op.drop_index("ix_policy_rollback_investigation_timeline_event_actor_id", table_name="policy_rollback_investigation_timeline_event")
    op.drop_index("ix_policy_rollback_investigation_timeline_event_event_type", table_name="policy_rollback_investigation_timeline_event")
    op.drop_index("ix_policy_rollback_investigation_timeline_event_investigation_id", table_name="policy_rollback_investigation_timeline_event")
    op.drop_table("policy_rollback_investigation_timeline_event")

    op.drop_index("ix_policy_rollback_investigation_assigned_owner_id", table_name="policy_rollback_investigation")
    op.drop_index("ix_policy_rollback_investigation_rollback_reason", table_name="policy_rollback_investigation")
    op.drop_index("ix_policy_rollback_investigation_arm_key", table_name="policy_rollback_investigation")
    op.drop_index("ix_policy_rollback_investigation_bundle_id", table_name="policy_rollback_investigation")
    op.drop_index("ix_policy_rollback_investigation_pipeline_id", table_name="policy_rollback_investigation")
    op.drop_table("policy_rollback_investigation")

    op.drop_index("ix_policy_manual_review_action_actor_id", table_name="policy_manual_review_action")
    op.drop_index("ix_policy_manual_review_action_action_type", table_name="policy_manual_review_action")
    op.drop_index("ix_policy_manual_review_action_queue_item_id", table_name="policy_manual_review_action")
    op.drop_table("policy_manual_review_action")

    op.drop_index("ix_policy_manual_review_queue_item_assigned_reviewer_id", table_name="policy_manual_review_queue_item")
    op.drop_index("ix_policy_manual_review_queue_item_arm_key", table_name="policy_manual_review_queue_item")
    op.drop_index("ix_policy_manual_review_queue_item_bundle_id", table_name="policy_manual_review_queue_item")
    op.drop_index("ix_policy_manual_review_queue_item_decision_key", table_name="policy_manual_review_queue_item")
    op.drop_index("ix_policy_manual_review_queue_item_pipeline_id", table_name="policy_manual_review_queue_item")
    op.drop_table("policy_manual_review_queue_item")

    op.drop_index("ix_policy_promotion_pipeline_stage_event_event_type", table_name="policy_promotion_pipeline_stage_event")
    op.drop_index("ix_policy_promotion_pipeline_stage_event_stage_name", table_name="policy_promotion_pipeline_stage_event")
    op.drop_index("ix_policy_promotion_pipeline_stage_event_pipeline_id", table_name="policy_promotion_pipeline_stage_event")
    op.drop_table("policy_promotion_pipeline_stage_event")

    op.drop_index("ix_policy_promotion_pipeline_decision_key", table_name="policy_promotion_pipeline")
    op.drop_index("ix_policy_promotion_pipeline_arm_key", table_name="policy_promotion_pipeline")
    op.drop_index("ix_policy_promotion_pipeline_bundle_id", table_name="policy_promotion_pipeline")
    op.drop_index("ix_policy_promotion_pipeline_experiment_key", table_name="policy_promotion_pipeline")
    op.drop_index("ix_policy_promotion_pipeline_pipeline_key", table_name="policy_promotion_pipeline")
    op.drop_table("policy_promotion_pipeline")

    bind = op.get_bind()
    policy_post_promotion_monitor_status_enum.drop(bind, checkfirst=True)
    policy_rollback_investigation_status_enum.drop(bind, checkfirst=True)
    policy_manual_review_queue_item_status_enum.drop(bind, checkfirst=True)
    policy_promotion_pipeline_status_enum.drop(bind, checkfirst=True)
backend/tests/services/test_policy_promotion_pipeline_service.py
from unittest.mock import Mock

from app.services.policy_promotion_pipeline_service import PolicyPromotionPipelineService


def test_create_pipeline_creates_initial_stage_event():
    pipeline_repo = Mock()
    stage_event_repo = Mock()

    pipeline_repo.create.side_effect = lambda x: x
    stage_event_repo.create.side_effect = lambda x: x

    service = PolicyPromotionPipelineService(
        pipeline_repo=pipeline_repo,
        stage_event_repo=stage_event_repo,
    )

    model = service.create_pipeline(
        pipeline_key="pipe-1",
        experiment_key="exp-1",
        bundle_id="bundle-a",
        arm_key="arm-a",
        decision_key="decision-1",
        off_policy_evaluation_key="ope-1",
        safety_simulation_key="sim-1",
        config_json={},
        notes=None,
        actor_id="tester",
    )

    assert model.pipeline_key == "pipe-1"
    assert stage_event_repo.create.called
backend/tests/services/test_policy_manual_review_workbench_service.py
from unittest.mock import Mock

from app.services.policy_manual_review_workbench_service import PolicyManualReviewWorkbenchService


def test_apply_manual_review_approve_updates_pipeline():
    pipeline = type("Pipeline", (), {"id": "p1", "status": "waiting_manual_review", "current_stage": "manual_review"})()
    queue_item = type("QueueItem", (), {"id": "q1", "pipeline_id": "p1", "status": "pending", "assigned_reviewer_id": None, "updated_by": None})()

    pipeline_repo = Mock()
    stage_event_repo = Mock()
    queue_repo = Mock()
    action_repo = Mock()

    queue_repo.get.return_value = queue_item
    pipeline_repo.get.return_value = pipeline
    queue_repo.save.side_effect = lambda x: x
    pipeline_repo.save.side_effect = lambda x: x
    action_repo.create.side_effect = lambda x: x
    stage_event_repo.create.side_effect = lambda x: x

    service = PolicyManualReviewWorkbenchService(
        pipeline_repo=pipeline_repo,
        stage_event_repo=stage_event_repo,
        queue_repo=queue_repo,
        action_repo=action_repo,
    )

    item = service.apply_action(
        queue_item_id="q1",
        action_type="approve",
        reason="Looks safe",
        payload_json={},
        actor_id="reviewer-1",
    )

    assert item.status.value == "approved"
    assert pipeline.status == "approved"
backend/tests/services/test_policy_rollback_investigation_service.py
from unittest.mock import Mock

from app.services.policy_rollback_investigation_service import PolicyRollbackInvestigationService


def test_open_investigation_returns_existing_if_present():
    pipeline = type("Pipeline", (), {"id": "p1"})()
    existing = type("Investigation", (), {"id": "i1"})()

    pipeline_repo = Mock()
    investigation_repo = Mock()
    timeline_repo = Mock()

    pipeline_repo.get_by_key.return_value = pipeline
    investigation_repo.get_by_pipeline_id.return_value = existing

    service = PolicyRollbackInvestigationService(
        pipeline_repo=pipeline_repo,
        investigation_repo=investigation_repo,
        timeline_repo=timeline_repo,
    )

    result = service.open_investigation(
        pipeline_key="pipe-1",
        bundle_id="bundle-a",
        arm_key="arm-a",
        rollback_reason="regression",
        evidence_json={},
        assigned_owner_id=None,
        actor_id="system",
    )

    assert result.id == "i1"
3) CÁCH NỐI ROUTER VÀO APP
Trong backend/app/main.py hoặc router registry:
from app.api.policy_promotion_operations import router as policy_promotion_operations_router

app.include_router(policy_promotion_operations_router)
4) FLOW THỰC TẾ SAU PATCH NÀY
A. Tạo promotion pipeline
POST /policy-promotion-operations/pipeline
{
  "pipeline_key": "promotion-pipe-001",
  "experiment_key": "bundle-routing-exp-001",
  "bundle_id": "bundle-a",
  "arm_key": "variant_a",
  "decision_key": "committee-001",
  "off_policy_evaluation_key": "ope-fraud-night-001",
  "safety_simulation_key": "safety-fraud-night-001",
  "config_json": {
    "canary_percent": 20
  }
}
B. Advance pipeline stages
POST /policy-promotion-operations/pipeline/advance
{
  "pipeline_key": "promotion-pipe-001",
  "next_stage": "committee_review",
  "payload_json": {
    "committee_ready": true
  },
  "summary": "Evidence package ready for committee"
}
Ví dụ stage tiếp theo:
manual_review
approved
canary_live
promoted_live
rolled_back
completed
C. Tạo manual review queue item
POST /policy-promotion-operations/manual-review/queue-item
{
  "pipeline_key": "promotion-pipe-001",
  "decision_key": "committee-001",
  "bundle_id": "bundle-a",
  "arm_key": "variant_a",
  "priority": "high",
  "review_context_json": {
    "reason": "borderline confidence"
  },
  "assigned_reviewer_id": "reviewer-ops-1",
  "escalation_reviewer_id": "supervisor-1"
}
D. Reviewer actions
POST /policy-promotion-operations/manual-review/action
{
  "queue_item_id": "REPLACE_UUID",
  "action_type": "approve",
  "reason": "Evidence sufficient after manual review",
  "payload_json": {
    "confidence_override": true
  }
}
Các action hợp lệ hiện có:
claim
approve
reject
request_changes
escalate
close
E. Mở rollback investigation
POST /policy-promotion-operations/rollback-investigation/open
{
  "pipeline_key": "promotion-pipe-001",
  "bundle_id": "bundle-a",
  "arm_key": "variant_a",
  "rollback_reason": "post_promotion_regression_detected",
  "evidence_json": {
    "observed_regression_risk": 0.54,
    "observed_safety_score": 0.41
  },
  "assigned_owner_id": "investigator-1"
}
F. Thêm investigation timeline event
POST /policy-promotion-operations/rollback-investigation/event
{
  "investigation_id": "REPLACE_UUID",
  "event_type": "started",
  "summary": "Investigation started by operations",
  "payload_json": {
    "owner": "investigator-1"
  }
}
Ví dụ event_type:
started
metric_regression_detected
root_cause_hypothesis_added
resolved
closed
G. Cập nhật post-promotion monitor
POST /policy-promotion-operations/post-promotion-monitor
{
  "pipeline_key": "promotion-pipe-001",
  "decision_key": "committee-001",
  "off_policy_evaluation_key": "ope-fraud-night-001",
  "safety_simulation_key": "safety-fraud-night-001",
  "bundle_id": "bundle-a",
  "arm_key": "variant_a",
  "observed_uplift": 0.18,
  "observed_regression_risk": 0.46,
  "observed_safety_score": 0.52,
  "latest_metrics_json": {
    "sla_breach_rate": 0.31
  },
  "alert_state_json": {
    "rollback_candidate": true
  }
}
Nếu regression risk cao, hệ sẽ mark:
rollback_candidate
Worker có thể tự mở investigation.
5) ĐIỂM MAP QUAN TRỌNG KHI DÁN VÀO REPO THẬT
A. Bundle lifecycle hooks
Trong repo thật, map:
promote_bundle(...)
rollback_bundle(...)
freeze_bundle(...)
retire_bundle(...)
vào service hiện có của bundle lifecycle.
B. Manual review RBAC
Bản này chưa siết RBAC chi tiết.
Repo thật nên map:
reviewer
supervisor
governance admin
product owner
veto authority
vào auth deps thật.
C. Investigation timeline hợp nhất
Hiện timeline mới chứa event manual add.
Repo thật nên hợp nhất thêm từ:
committee decision events
canary rollout events
alert events
rollback execution attempt
audit logs
monitor changes
D. Post-promotion monitoring feed
Bản này nhận metrics trực tiếp.
Repo thật nên aggregate từ:
actual SLA metrics
actual cost deltas
actual churn/rework
actual rebalance success
queue health snapshots
E. SLA & overdue queue
Bản này mới tạo sla_due_at.
Repo thật nên thêm worker:
detect overdue reviews
auto-escalate
alert supervisors
queue aging metrics
6) KẾT QUẢ SAU PATCH NÀY
Sau phase này, hệ đi từ:
governance-grade promotion decision
sang:
enterprise policy promotion operations
Cụ thể hệ đã có:
A. Multi-stage promotion pipeline
Policy không chỉ được chấm điểm rồi promote, mà đi qua pipeline stage thật.
B. Human approval workbench
Có manual review queue, reviewer actions, escalation, review SLA.
C. Rollback investigation timeline
Khi policy fail sau promote, có investigation record và timeline điều tra.
D. Post-promotion monitoring linked to evidence
Monitoring không tách rời. Nó nối ngược về:
decision
OPE
safety simulation
pipeline
E. Closed-loop enterprise operations
Hệ giờ có thể:
decide
review
approve
promote
monitor
rollback
investigate
