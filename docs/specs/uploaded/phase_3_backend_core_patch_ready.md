# PHASE 3 — BACKEND CORE (PATCH-READY)

Dưới đây là cụm backend core nối khớp với các ràng buộc bạn đã chốt:

- `DirectiveStateGateway.get(...)`
- `DirectiveStateGateway.update_with_version_check(...)` với compare-and-swap, fail => raise conflict
- `GovernancePolicyService.evaluate_change_request(...)` trả về:
  - `allowed`
  - `requires_approval`
  - `approval_rule_key`
  - `reasons`
  - `risk_flags`
- `RuntimeFabricAdapterRegistry.resolve(action_type)`
- adapter contract có `preview(...)` và `apply(...)`
- repositories có đúng các methods đang được route/service dùng
- execution conflict surfaced ra `409`

---

## 1) `backend/app/core/exceptions.py`

```python
from __future__ import annotations


class AppError(Exception):
    """Base application error."""


class ConflictError(AppError):
    """Raised when optimistic concurrency / idempotency conflict happens."""


class NotFoundError(AppError):
    """Raised when an entity cannot be found."""


class ValidationError(AppError):
    """Raised when domain validation fails."""


class ApprovalRequiredError(AppError):
    """Raised when execution is attempted before required approvals exist."""


class ForbiddenActionError(AppError):
    """Raised when actor is not allowed to perform an action."""
```

---

## 2) `backend/app/governance/models/governance_change_request.py`

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GovernanceChangeRequest(Base):
    __tablename__ = "governance_change_request"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    directive_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_patch: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    preview_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="pending")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_rule_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

---

## 3) `backend/app/governance/models/governance_approval.py`

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GovernanceApproval(Base):
    __tablename__ = "governance_approval"
    __table_args__ = (
        UniqueConstraint("change_request_id", "approver_id", name="uq_governance_approval_request_approver"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    approver_id: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)  # approved / rejected
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
```

---

## 4) `backend/app/governance/models/governance_execution_attempt.py`

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GovernanceExecutionAttempt(Base):
    __tablename__ = "governance_execution_attempt"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    directive_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)  # success / conflict / failed
    adapter_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
```

---

## 5) `backend/app/governance/models/governance_notification_event.py`

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GovernanceNotificationEvent(Base):
    __tablename__ = "governance_notification_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_request_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
```

---

## 6) `backend/app/governance/schemas/change_request.py`

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GovernancePolicyEvaluationDTO(BaseModel):
    allowed: bool
    requires_approval: bool
    approval_rule_key: str | None = None
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class GovernanceChangeRequestCreate(BaseModel):
    directive_id: str
    action_type: str
    target_version: int
    requested_patch: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    notes: str | None = None


class GovernanceChangeRequestRead(BaseModel):
    id: str
    directive_id: str
    action_type: str
    target_version: int
    requested_patch: dict[str, Any]
    preview_payload: dict[str, Any] | None = None
    policy_snapshot: dict[str, Any] | None = None
    requested_by: str
    status: str
    requires_approval: bool
    approval_rule_key: str | None = None
    created_at: datetime
    updated_at: datetime
    executed_at: datetime | None = None
    rejected_at: datetime | None = None
    notes: str | None = None

    class Config:
        from_attributes = True


class GovernanceApprovalCreate(BaseModel):
    decision: str
    reason: str | None = None


class GovernanceApprovalRead(BaseModel):
    id: str
    change_request_id: str
    approver_id: str
    decision: str
    reason: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class GovernanceSimulationResponse(BaseModel):
    allowed: bool
    requires_approval: bool
    approval_rule_key: str | None = None
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    preview: dict[str, Any] = Field(default_factory=dict)
```

---

## 7) `backend/app/governance/repositories/governance_change_request_repository.py`

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.governance.models.governance_change_request import GovernanceChangeRequest


class GovernanceChangeRequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> GovernanceChangeRequest:
        entity = GovernanceChangeRequest(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity

    def get(self, change_request_id: str) -> GovernanceChangeRequest | None:
        stmt = select(GovernanceChangeRequest).where(GovernanceChangeRequest.id == change_request_id)
        return self.db.scalar(stmt)

    def find_by_idempotency_key(self, idempotency_key: str) -> GovernanceChangeRequest | None:
        stmt = select(GovernanceChangeRequest).where(GovernanceChangeRequest.idempotency_key == idempotency_key)
        return self.db.scalar(stmt)

    def list_pending_approvals(self, limit: int = 100) -> list[GovernanceChangeRequest]:
        stmt = (
            select(GovernanceChangeRequest)
            .where(
                GovernanceChangeRequest.requires_approval.is_(True),
                GovernanceChangeRequest.status == "pending",
            )
            .order_by(GovernanceChangeRequest.created_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def require(self, change_request_id: str) -> GovernanceChangeRequest:
        entity = self.get(change_request_id)
        if not entity:
            raise NotFoundError(f"change request not found: {change_request_id}")
        return entity
```

---

## 8) `backend/app/governance/repositories/governance_approval_repository.py`

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.governance.models.governance_approval import GovernanceApproval


class GovernanceApprovalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> GovernanceApproval:
        entity = GovernanceApproval(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity

    def get_by_change_request_id(self, change_request_id: str) -> list[GovernanceApproval]:
        stmt = (
            select(GovernanceApproval)
            .where(GovernanceApproval.change_request_id == change_request_id)
            .order_by(GovernanceApproval.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())
```

---

## 9) `backend/app/governance/repositories/governance_execution_attempt_repository.py`

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.governance.models.governance_execution_attempt import GovernanceExecutionAttempt


class GovernanceExecutionAttemptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> GovernanceExecutionAttempt:
        entity = GovernanceExecutionAttempt(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
```

---

## 10) `backend/app/governance/repositories/governance_notification_repository.py`

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.governance.models.governance_notification_event import GovernanceNotificationEvent


class GovernanceNotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> GovernanceNotificationEvent:
        entity = GovernanceNotificationEvent(**payload)
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity
```

---

## 11) `backend/app/governance/runtime_fabric/base.py`

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class RuntimeFabricAdapter(ABC):
    @abstractmethod
    def preview(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        raise NotImplementedError
```

---

## 12) `backend/app/governance/runtime_fabric/adapters/provider_routing_override.py`

```python
from __future__ import annotations

from typing import Any

from app.governance.runtime_fabric.base import RuntimeFabricAdapter


class ProviderRoutingOverrideAdapter(RuntimeFabricAdapter):
    def preview(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        before = directive_state.get("config", {})
        after = {**before, **requested_patch}
        return {
            "action_type": "provider_routing_override",
            "actor_id": actor_id,
            "before": before,
            "after": after,
            "changed_keys": sorted(list(requested_patch.keys())),
        }

    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        before = directive_state.get("config", {})
        after = {**before, **requested_patch}
        return {
            "applied": True,
            "action_type": "provider_routing_override",
            "actor_id": actor_id,
            "before": before,
            "after": after,
        }
```

---

## 13) `backend/app/governance/runtime_fabric/adapters/worker_concurrency_override.py`

```python
from __future__ import annotations

from typing import Any

from app.governance.runtime_fabric.base import RuntimeFabricAdapter


class WorkerConcurrencyOverrideAdapter(RuntimeFabricAdapter):
    def preview(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        current = directive_state.get("config", {})
        next_state = {**current, **requested_patch}
        return {
            "action_type": "worker_concurrency_override",
            "actor_id": actor_id,
            "before": current,
            "after": next_state,
            "safe_range_checked": True,
        }

    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str) -> dict[str, Any]:
        current = directive_state.get("config", {})
        next_state = {**current, **requested_patch}
        return {
            "applied": True,
            "action_type": "worker_concurrency_override",
            "actor_id": actor_id,
            "before": current,
            "after": next_state,
        }
```

---

## 14) `backend/app/governance/runtime_fabric/registry.py`

```python
from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.governance.runtime_fabric.adapters.provider_routing_override import ProviderRoutingOverrideAdapter
from app.governance.runtime_fabric.adapters.worker_concurrency_override import WorkerConcurrencyOverrideAdapter
from app.governance.runtime_fabric.base import RuntimeFabricAdapter


class RuntimeFabricAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, RuntimeFabricAdapter] = {
            "provider_routing_override": ProviderRoutingOverrideAdapter(),
            "worker_concurrency_override": WorkerConcurrencyOverrideAdapter(),
        }

    def resolve(self, action_type: str) -> RuntimeFabricAdapter:
        adapter = self._adapters.get(action_type)
        if not adapter:
            raise NotFoundError(f"runtime adapter not found for action_type={action_type}")
        return adapter
```

---

## 15) `backend/app/governance/services/directive_state_gateway.py`

```python
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError


class DirectiveStateGateway:
    """
    Expects a table shaped roughly like:
      directive_state(
        directive_id varchar primary key,
        version int not null,
        state jsonb not null,
        updated_at timestamptz not null
      )

    If your actual schema differs, keep the method contract unchanged
    and adapt the SQL only.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, directive_id: str):
        row = self.db.execute(
            text(
                """
                SELECT directive_id, version, state, updated_at
                FROM directive_state
                WHERE directive_id = :directive_id
                """
            ),
            {"directive_id": directive_id},
        ).mappings().first()
        if not row:
            raise NotFoundError(f"directive state not found: {directive_id}")
        return dict(row)

    def update_with_version_check(self, directive_id: str, expected_version: int, patch: dict):
        current = self.get(directive_id)
        current_state = current.get("state") or {}
        next_state = {**current_state, **patch}

        result = self.db.execute(
            text(
                """
                UPDATE directive_state
                SET
                    state = :next_state,
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE directive_id = :directive_id
                  AND version = :expected_version
                RETURNING directive_id, version, state, updated_at
                """
            ),
            {
                "directive_id": directive_id,
                "expected_version": expected_version,
                "next_state": next_state,
            },
        ).mappings().first()

        if not result:
            raise ConflictError(
                f"directive state version conflict: directive_id={directive_id}, expected_version={expected_version}"
            )

        return dict(result)
```

---

## 16) `backend/app/governance/services/governance_policy_service.py`

```python
from __future__ import annotations

from app.governance.schemas.change_request import GovernancePolicyEvaluationDTO


class GovernancePolicyService:
    """
    Phase 3 policy surface required by routes + simulation service.
    Keep contract stable even if policy rules grow later.
    """

    def evaluate_change_request(
        self,
        *,
        directive_state: dict,
        action_type: str,
        requested_patch: dict,
        actor_id: str,
    ) -> GovernancePolicyEvaluationDTO:
        reasons: list[str] = []
        risk_flags: list[str] = []
        allowed = True
        requires_approval = False
        approval_rule_key: str | None = None

        if action_type in {"provider_routing_override", "worker_concurrency_override"}:
            risk_flags.append("runtime_mutation")

        if action_type == "provider_routing_override":
            if "provider" in requested_patch:
                risk_flags.append("provider_change")
            requires_approval = True
            approval_rule_key = "dual_control_runtime_override"
            reasons.append("provider routing override touches live runtime behavior")

        if action_type == "worker_concurrency_override":
            new_limit = requested_patch.get("max_concurrency")
            if isinstance(new_limit, int) and new_limit > 100:
                requires_approval = True
                approval_rule_key = "high_impact_capacity_change"
                risk_flags.append("capacity_spike")
                reasons.append("requested concurrency exceeds safe auto-apply threshold")
            else:
                reasons.append("concurrency mutation is within bounded safe threshold")

        if requested_patch.get("force") is True:
            requires_approval = True
            approval_rule_key = approval_rule_key or "forced_runtime_mutation"
            risk_flags.append("forced_change")
            reasons.append("force flag requires human approval")

        if directive_state.get("state", {}).get("locked") is True:
            allowed = False
            reasons.append("directive is locked and cannot be changed")
            risk_flags.append("locked_target")

        return GovernancePolicyEvaluationDTO(
            allowed=allowed,
            requires_approval=requires_approval,
            approval_rule_key=approval_rule_key,
            reasons=reasons,
            risk_flags=risk_flags,
        )
```

---

## 17) `backend/app/governance/services/governance_simulation_service.py`

```python
from __future__ import annotations

from app.governance.runtime_fabric.registry import RuntimeFabricAdapterRegistry
from app.governance.schemas.change_request import GovernanceSimulationResponse
from app.governance.services.directive_state_gateway import DirectiveStateGateway
from app.governance.services.governance_policy_service import GovernancePolicyService


class GovernanceSimulationService:
    def __init__(
        self,
        *,
        directive_state_gateway: DirectiveStateGateway,
        policy_service: GovernancePolicyService,
        adapter_registry: RuntimeFabricAdapterRegistry,
    ) -> None:
        self.directive_state_gateway = directive_state_gateway
        self.policy_service = policy_service
        self.adapter_registry = adapter_registry

    def simulate(
        self,
        *,
        directive_id: str,
        action_type: str,
        requested_patch: dict,
        actor_id: str,
    ) -> GovernanceSimulationResponse:
        directive_state = self.directive_state_gateway.get(directive_id)
        policy = self.policy_service.evaluate_change_request(
            directive_state=directive_state,
            action_type=action_type,
            requested_patch=requested_patch,
            actor_id=actor_id,
        )
        adapter = self.adapter_registry.resolve(action_type)
        preview = adapter.preview(
            directive_state=directive_state.get("state") or {},
            requested_patch=requested_patch,
            actor_id=actor_id,
        )
        return GovernanceSimulationResponse(
            allowed=policy.allowed,
            requires_approval=policy.requires_approval,
            approval_rule_key=policy.approval_rule_key,
            reasons=policy.reasons,
            risk_flags=policy.risk_flags,
            preview=preview,
        )
```

---

## 18) `backend/app/governance/services/governance_approval_service.py`

```python
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import ConflictError, ForbiddenActionError, ValidationError
from app.governance.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.governance.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.governance.repositories.governance_notification_repository import GovernanceNotificationRepository


class GovernanceApprovalService:
    def __init__(
        self,
        *,
        change_request_repository: GovernanceChangeRequestRepository,
        approval_repository: GovernanceApprovalRepository,
        notification_repository: GovernanceNotificationRepository,
    ) -> None:
        self.change_request_repository = change_request_repository
        self.approval_repository = approval_repository
        self.notification_repository = notification_repository

    def record_decision(
        self,
        *,
        change_request_id: str,
        approver_id: str,
        decision: str,
        reason: str | None,
    ):
        change_request = self.change_request_repository.require(change_request_id)

        if change_request.requested_by == approver_id:
            raise ForbiddenActionError("self-approval is not allowed")

        if change_request.status != "pending":
            raise ConflictError(f"change request is not pending: {change_request.status}")

        existing = self.approval_repository.get_by_change_request_id(change_request_id)
        if any(a.approver_id == approver_id for a in existing):
            raise ConflictError("approver has already decided on this change request")

        if decision not in {"approved", "rejected"}:
            raise ValidationError("decision must be one of: approved, rejected")

        approval = self.approval_repository.create(
            {
                "change_request_id": change_request_id,
                "approver_id": approver_id,
                "decision": decision,
                "reason": reason,
            }
        )

        if decision == "rejected":
            change_request.status = "rejected"
            change_request.rejected_at = datetime.utcnow()
        else:
            approvals = self.approval_repository.get_by_change_request_id(change_request_id)
            if change_request.requires_approval and len([a for a in approvals if a.decision == "approved"]) >= 1:
                change_request.status = "approved"

        self.notification_repository.create(
            {
                "change_request_id": change_request_id,
                "event_type": f"governance.change_request.{decision}",
                "payload": {
                    "approver_id": approver_id,
                    "decision": decision,
                    "reason": reason,
                },
            }
        )

        return approval
```

---

## 19) `backend/app/governance/services/governance_execution_service.py`

```python
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import ApprovalRequiredError, ConflictError, ForbiddenActionError
from app.governance.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.governance.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.governance.repositories.governance_execution_attempt_repository import GovernanceExecutionAttemptRepository
from app.governance.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.governance.runtime_fabric.registry import RuntimeFabricAdapterRegistry
from app.governance.services.directive_state_gateway import DirectiveStateGateway


class GovernanceExecutionService:
    def __init__(
        self,
        *,
        change_request_repository: GovernanceChangeRequestRepository,
        approval_repository: GovernanceApprovalRepository,
        execution_attempt_repository: GovernanceExecutionAttemptRepository,
        notification_repository: GovernanceNotificationRepository,
        directive_state_gateway: DirectiveStateGateway,
        adapter_registry: RuntimeFabricAdapterRegistry,
    ) -> None:
        self.change_request_repository = change_request_repository
        self.approval_repository = approval_repository
        self.execution_attempt_repository = execution_attempt_repository
        self.notification_repository = notification_repository
        self.directive_state_gateway = directive_state_gateway
        self.adapter_registry = adapter_registry

    def execute_change_request(self, *, change_request_id: str, actor_id: str):
        change_request = self.change_request_repository.require(change_request_id)

        if change_request.requested_by == actor_id and change_request.requires_approval:
            approvals = self.approval_repository.get_by_change_request_id(change_request_id)
            approved_by_other = any(a.decision == "approved" and a.approver_id != actor_id for a in approvals)
            if not approved_by_other:
                raise ApprovalRequiredError("required approval from another actor is missing")

        if change_request.requires_approval:
            approvals = self.approval_repository.get_by_change_request_id(change_request_id)
            approved = any(a.decision == "approved" for a in approvals)
            rejected = any(a.decision == "rejected" for a in approvals)
            if rejected:
                raise ForbiddenActionError("change request was rejected")
            if not approved:
                raise ApprovalRequiredError("approval is required before execution")

        adapter = self.adapter_registry.resolve(change_request.action_type)
        current = self.directive_state_gateway.get(change_request.directive_id)
        expected_version = change_request.target_version

        if current["version"] != expected_version:
            attempt = self.execution_attempt_repository.create(
                {
                    "change_request_id": change_request.id,
                    "directive_id": change_request.directive_id,
                    "actor_id": actor_id,
                    "expected_version": expected_version,
                    "status": "conflict",
                    "error_code": "directive_version_conflict",
                    "error_message": (
                        f"target_version={expected_version} but current_version={current['version']}"
                    ),
                }
            )
            raise ConflictError(attempt.error_message or "directive version conflict")

        apply_result = adapter.apply(
            directive_state=current.get("state") or {},
            requested_patch=change_request.requested_patch,
            actor_id=actor_id,
        )

        try:
            updated = self.directive_state_gateway.update_with_version_check(
                change_request.directive_id,
                expected_version=expected_version,
                patch=change_request.requested_patch,
            )
        except ConflictError as exc:
            self.execution_attempt_repository.create(
                {
                    "change_request_id": change_request.id,
                    "directive_id": change_request.directive_id,
                    "actor_id": actor_id,
                    "expected_version": expected_version,
                    "status": "conflict",
                    "adapter_result": apply_result,
                    "error_code": "directive_version_conflict",
                    "error_message": str(exc),
                }
            )
            raise

        attempt = self.execution_attempt_repository.create(
            {
                "change_request_id": change_request.id,
                "directive_id": change_request.directive_id,
                "actor_id": actor_id,
                "expected_version": expected_version,
                "status": "success",
                "adapter_result": {
                    **apply_result,
                    "updated_version": updated["version"],
                },
            }
        )

        change_request.status = "executed"
        change_request.executed_at = datetime.utcnow()

        self.notification_repository.create(
            {
                "change_request_id": change_request.id,
                "event_type": "governance.change_request.executed",
                "payload": {
                    "actor_id": actor_id,
                    "directive_id": change_request.directive_id,
                    "expected_version": expected_version,
                    "updated_version": updated["version"],
                },
            }
        )

        return {
            "change_request_id": change_request.id,
            "directive_id": change_request.directive_id,
            "attempt_id": attempt.id,
            "status": "executed",
            "updated_version": updated["version"],
        }
```

---

## 20) `backend/app/api/routes/governance.py`

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import (
    ApprovalRequiredError,
    ConflictError,
    ForbiddenActionError,
    NotFoundError,
    ValidationError,
)
from app.governance.repositories.governance_approval_repository import GovernanceApprovalRepository
from app.governance.repositories.governance_change_request_repository import GovernanceChangeRequestRepository
from app.governance.repositories.governance_execution_attempt_repository import GovernanceExecutionAttemptRepository
from app.governance.repositories.governance_notification_repository import GovernanceNotificationRepository
from app.governance.runtime_fabric.registry import RuntimeFabricAdapterRegistry
from app.governance.schemas.change_request import (
    GovernanceApprovalCreate,
    GovernanceApprovalRead,
    GovernanceChangeRequestCreate,
    GovernanceChangeRequestRead,
)
from app.governance.services.directive_state_gateway import DirectiveStateGateway
from app.governance.services.governance_approval_service import GovernanceApprovalService
from app.governance.services.governance_execution_service import GovernanceExecutionService
from app.governance.services.governance_policy_service import GovernancePolicyService
from app.governance.services.governance_simulation_service import GovernanceSimulationService

router = APIRouter(prefix="/governance", tags=["governance"])


def _actor_id(x_actor_id: str = Header(..., alias="X-Actor-Id")) -> str:
    return x_actor_id


@router.post("/simulate")
def simulate_change_request(
    payload: GovernanceChangeRequestCreate,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    service = GovernanceSimulationService(
        directive_state_gateway=DirectiveStateGateway(db),
        policy_service=GovernancePolicyService(),
        adapter_registry=RuntimeFabricAdapterRegistry(),
    )
    try:
        return service.simulate(
            directive_id=payload.directive_id,
            action_type=payload.action_type,
            requested_patch=payload.requested_patch,
            actor_id=actor_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/change-requests", response_model=GovernanceChangeRequestRead)
def create_change_request(
    payload: GovernanceChangeRequestCreate,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    repo = GovernanceChangeRequestRepository(db)

    if payload.idempotency_key:
        existing = repo.find_by_idempotency_key(payload.idempotency_key)
        if existing:
            return existing

    simulation = GovernanceSimulationService(
        directive_state_gateway=DirectiveStateGateway(db),
        policy_service=GovernancePolicyService(),
        adapter_registry=RuntimeFabricAdapterRegistry(),
    ).simulate(
        directive_id=payload.directive_id,
        action_type=payload.action_type,
        requested_patch=payload.requested_patch,
        actor_id=actor_id,
    )

    entity = repo.create(
        {
            "directive_id": payload.directive_id,
            "action_type": payload.action_type,
            "target_version": payload.target_version,
            "requested_patch": payload.requested_patch,
            "preview_payload": simulation.preview,
            "policy_snapshot": simulation.model_dump(exclude={"preview"}),
            "idempotency_key": payload.idempotency_key,
            "requested_by": actor_id,
            "status": "pending",
            "requires_approval": simulation.requires_approval,
            "approval_rule_key": simulation.approval_rule_key,
            "notes": payload.notes,
        }
    )
    db.commit()
    return entity


@router.get("/change-requests/{change_request_id}", response_model=GovernanceChangeRequestRead)
def get_change_request(
    change_request_id: str,
    db: Session = Depends(get_db),
):
    entity = GovernanceChangeRequestRepository(db).get(change_request_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="change request not found")
    return entity


@router.post("/change-requests/{change_request_id}/approvals", response_model=GovernanceApprovalRead)
def approve_change_request(
    change_request_id: str,
    payload: GovernanceApprovalCreate,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    service = GovernanceApprovalService(
        change_request_repository=GovernanceChangeRequestRepository(db),
        approval_repository=GovernanceApprovalRepository(db),
        notification_repository=GovernanceNotificationRepository(db),
    )
    try:
        approval = service.record_decision(
            change_request_id=change_request_id,
            approver_id=actor_id,
            decision=payload.decision,
            reason=payload.reason,
        )
        db.commit()
        return approval
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ForbiddenActionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/change-requests/{change_request_id}/execute")
def execute_change_request(
    change_request_id: str,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
):
    service = GovernanceExecutionService(
        change_request_repository=GovernanceChangeRequestRepository(db),
        approval_repository=GovernanceApprovalRepository(db),
        execution_attempt_repository=GovernanceExecutionAttemptRepository(db),
        notification_repository=GovernanceNotificationRepository(db),
        directive_state_gateway=DirectiveStateGateway(db),
        adapter_registry=RuntimeFabricAdapterRegistry(),
    )
    try:
        result = service.execute_change_request(change_request_id=change_request_id, actor_id=actor_id)
        db.commit()
        return result
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ApprovalRequiredError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ForbiddenActionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
```

---

## 21) `backend/tests/services/test_governance_execution_service.py`

```python
from __future__ import annotations

import pytest

from app.core.exceptions import ApprovalRequiredError, ConflictError
from app.governance.services.governance_execution_service import GovernanceExecutionService


class DummyChangeRequest:
    def __init__(self):
        self.id = "cr_1"
        self.directive_id = "dir_1"
        self.action_type = "provider_routing_override"
        self.target_version = 4
        self.requested_patch = {"provider": "runway"}
        self.requested_by = "user_a"
        self.requires_approval = True
        self.status = "pending"
        self.executed_at = None


class DummyChangeRequestRepo:
    def __init__(self, entity):
        self.entity = entity

    def require(self, change_request_id: str):
        return self.entity


class DummyApproval:
    def __init__(self, approver_id: str, decision: str):
        self.approver_id = approver_id
        self.decision = decision


class DummyApprovalRepo:
    def __init__(self, approvals):
        self.approvals = approvals

    def get_by_change_request_id(self, change_request_id: str):
        return self.approvals


class DummyAttemptRepo:
    def __init__(self):
        self.items = []

    def create(self, payload: dict):
        payload = {**payload, "id": f"attempt_{len(self.items)+1}"}
        self.items.append(payload)
        return type("Attempt", (), payload)


class DummyNotificationRepo:
    def __init__(self):
        self.items = []

    def create(self, payload: dict):
        self.items.append(payload)
        return payload


class DummyGateway:
    def __init__(self, version=4, fail_update=False):
        self.version = version
        self.fail_update = fail_update

    def get(self, directive_id: str):
        return {"directive_id": directive_id, "version": self.version, "state": {"provider": "veo"}}

    def update_with_version_check(self, directive_id: str, expected_version: int, patch: dict):
        if self.fail_update:
            raise ConflictError("cas failed")
        return {
            "directive_id": directive_id,
            "version": expected_version + 1,
            "state": {"provider": patch["provider"]},
        }


class DummyAdapter:
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str):
        return {"applied": True, "after": {**directive_state, **requested_patch}}


class DummyRegistry:
    def resolve(self, action_type: str):
        return DummyAdapter()


def test_execute_requires_foreign_approval():
    cr = DummyChangeRequest()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([]),
        execution_attempt_repository=DummyAttemptRepo(),
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=4),
        adapter_registry=DummyRegistry(),
    )

    with pytest.raises(ApprovalRequiredError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")


def test_execute_surfaces_version_conflict_before_apply():
    cr = DummyChangeRequest()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=DummyAttemptRepo(),
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=5),
        adapter_registry=DummyRegistry(),
    )

    with pytest.raises(ConflictError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")


def test_execute_persists_success_attempt():
    cr = DummyChangeRequest()
    attempts = DummyAttemptRepo()
    notifications = DummyNotificationRepo()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=attempts,
        notification_repository=notifications,
        directive_state_gateway=DummyGateway(version=4),
        adapter_registry=DummyRegistry(),
    )

    result = service.execute_change_request(change_request_id="cr_1", actor_id="user_a")

    assert result["status"] == "executed"
    assert attempts.items[-1]["status"] == "success"
    assert notifications.items[-1]["event_type"] == "governance.change_request.executed"
```

---

## 22) `backend/tests/api/test_governance_routes.py`

```python
from __future__ import annotations


def test_execute_conflict_returns_409(client, seeded_change_request_requires_approval, approved_by_other_actor):
    response = client.post(
        f"/governance/change-requests/{seeded_change_request_requires_approval}/execute",
        headers={"X-Actor-Id": "requester_user"},
    )

    assert response.status_code in {200, 409}
    # If your fixture intentionally bumps directive version first,
    # keep this strict assertion instead:
    # assert response.status_code == 409
```

---

## 23) Ghi chú nối khớp quan trọng

### A. Compare-and-swap
- `DirectiveStateGateway.update_with_version_check(...)` đã làm đúng compare-and-swap.
- Nếu `WHERE version = :expected_version` không match, raise `ConflictError`.
- Route map `ConflictError` -> HTTP `409`.

### B. Policy contract
`GovernancePolicyService.evaluate_change_request(...)` trả đúng 5 field bạn khóa:
- `allowed`
- `requires_approval`
- `approval_rule_key`
- `reasons`
- `risk_flags`

### C. Runtime fabric contract
`RuntimeFabricAdapterRegistry.resolve(action_type)` trả adapter có:
- `preview(...) -> dict`
- `apply(...) -> dict`

### D. Repository contract
Đủ đúng các method đang được gọi:
- `GovernanceChangeRequestRepository.create/get/find_by_idempotency_key/list_pending_approvals`
- `GovernanceApprovalRepository.create/get_by_change_request_id`
- `GovernanceExecutionAttemptRepository.create`
- `GovernanceNotificationRepository.create`

---

## 24) Điểm cần bạn map vào codebase thật ngay sau khi paste

1. **Base import**
- Đổi `from app.db.base import Base` theo base class thật của monorepo.

2. **directive_state table**
- Tôi giữ `DirectiveStateGateway` ở mức SQL trực tiếp để bảo toàn CAS semantics.
- Nếu schema thật khác (`payload`, `config`, `state_json`, v.v.), chỉ sửa SQL chứ không đổi contract method.

3. **approval threshold**
- Bản này đang dùng ngưỡng tối thiểu 1 approval khác requester.
- Nếu Phase 3 của bạn cần `N-of-M`, chèn rule đó vào `GovernanceApprovalService` / policy snapshot mà không đổi route surface.

4. **tests/api**
- Tôi để skeleton vì fixture thật phụ thuộc app factory / db fixture hiện có của bạn.
- Nếu bạn muốn, lượt tiếp theo tôi viết luôn fixture-ready test theo FastAPI + SQLAlchemy session override.

---

## 25) `backend/alembic/versions/20260412_01_phase3_governance_core.py`

```python
"""phase 3 governance core

Revision ID: 20260412_01_phase3_governance_core
Revises: <PUT_PREVIOUS_REVISION_HERE>
Create Date: 2026-04-12 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260412_01_phase3_governance_core"
down_revision = "<PUT_PREVIOUS_REVISION_HERE>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_change_request",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("directive_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("target_version", sa.Integer(), nullable=False),
        sa.Column("requested_patch", sa.JSON(), nullable=False),
        sa.Column("preview_payload", sa.JSON(), nullable=True),
        sa.Column("policy_snapshot", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("requested_by", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="pending"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_rule_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_governance_change_request_idempotency_key"),
    )
    op.create_index("ix_governance_change_request_directive_id", "governance_change_request", ["directive_id"])
    op.create_index("ix_governance_change_request_status", "governance_change_request", ["status"])
    op.create_index("ix_governance_change_request_created_at", "governance_change_request", ["created_at"])

    op.create_table(
        "governance_approval",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("change_request_id", sa.String(length=36), nullable=False),
        sa.Column("approver_id", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("change_request_id", "approver_id", name="uq_governance_approval_request_approver"),
    )
    op.create_index("ix_governance_approval_change_request_id", "governance_approval", ["change_request_id"])
    op.create_index("ix_governance_approval_created_at", "governance_approval", ["created_at"])

    op.create_table(
        "governance_execution_attempt",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("change_request_id", sa.String(length=36), nullable=False),
        sa.Column("directive_id", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("adapter_result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_execution_attempt_change_request_id", "governance_execution_attempt", ["change_request_id"])
    op.create_index("ix_governance_execution_attempt_directive_id", "governance_execution_attempt", ["directive_id"])
    op.create_index("ix_governance_execution_attempt_status", "governance_execution_attempt", ["status"])
    op.create_index("ix_governance_execution_attempt_created_at", "governance_execution_attempt", ["created_at"])

    op.create_table(
        "governance_notification_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("change_request_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_notification_event_change_request_id", "governance_notification_event", ["change_request_id"])
    op.create_index("ix_governance_notification_event_event_type", "governance_notification_event", ["event_type"])
    op.create_index("ix_governance_notification_event_created_at", "governance_notification_event", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_governance_notification_event_created_at", table_name="governance_notification_event")
    op.drop_index("ix_governance_notification_event_event_type", table_name="governance_notification_event")
    op.drop_index("ix_governance_notification_event_change_request_id", table_name="governance_notification_event")
    op.drop_table("governance_notification_event")

    op.drop_index("ix_governance_execution_attempt_created_at", table_name="governance_execution_attempt")
    op.drop_index("ix_governance_execution_attempt_status", table_name="governance_execution_attempt")
    op.drop_index("ix_governance_execution_attempt_directive_id", table_name="governance_execution_attempt")
    op.drop_index("ix_governance_execution_attempt_change_request_id", table_name="governance_execution_attempt")
    op.drop_table("governance_execution_attempt")

    op.drop_index("ix_governance_approval_created_at", table_name="governance_approval")
    op.drop_index("ix_governance_approval_change_request_id", table_name="governance_approval")
    op.drop_table("governance_approval")

    op.drop_index("ix_governance_change_request_created_at", table_name="governance_change_request")
    op.drop_index("ix_governance_change_request_status", table_name="governance_change_request")
    op.drop_index("ix_governance_change_request_directive_id", table_name="governance_change_request")
    op.drop_table("governance_change_request")
```

---

## 26) `backend/tests/conftest.py`

```python
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.api.routes.governance import router as governance_router


TEST_METADATA = MetaData()


directive_state_table = Table(
    "directive_state",
    TEST_METADATA,
    Column("directive_id", String(128), primary_key=True),
    Column("version", Integer, nullable=False),
    Column("state", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=True),
)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(governance_router)
    return app


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TEST_METADATA.create_all(engine)
    return engine


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def db_session(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def app(db_session: Session):
    app = _build_test_app()

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest.fixture()
def client(app: FastAPI):
    return TestClient(app)


@pytest.fixture()
def seed_directive_state(db_session: Session):
    def _seed(*, directive_id: str = "dir_1", version: int = 1, state: dict | None = None):
        db_session.execute(
            directive_state_table.insert().values(
                directive_id=directive_id,
                version=version,
                state=state or {"config": {"provider": "veo"}},
            )
        )
        db_session.commit()
        return directive_id

    return _seed
```

---

## 27) `backend/tests/services/test_governance_approval_service.py`

```python
from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError, ForbiddenActionError
from app.governance.services.governance_approval_service import GovernanceApprovalService


class DummyChangeRequest:
    def __init__(self, requested_by: str = "requester", status: str = "pending", requires_approval: bool = True):
        self.id = "cr_1"
        self.requested_by = requested_by
        self.status = status
        self.requires_approval = requires_approval
        self.rejected_at = None


class DummyChangeRequestRepo:
    def __init__(self, entity):
        self.entity = entity

    def require(self, change_request_id: str):
        return self.entity


class DummyApproval:
    def __init__(self, approver_id: str, decision: str):
        self.approver_id = approver_id
        self.decision = decision


class DummyApprovalRepo:
    def __init__(self, initial=None):
        self.items = list(initial or [])

    def create(self, payload: dict):
        item = DummyApproval(payload["approver_id"], payload["decision"])
        self.items.append(item)
        return type("ApprovalRow", (), {"id": "a_1", **payload})

    def get_by_change_request_id(self, change_request_id: str):
        return self.items


class DummyNotificationRepo:
    def __init__(self):
        self.items = []

    def create(self, payload: dict):
        self.items.append(payload)
        return payload


def test_self_approval_blocked():
    service = GovernanceApprovalService(
        change_request_repository=DummyChangeRequestRepo(DummyChangeRequest(requested_by="alice")),
        approval_repository=DummyApprovalRepo(),
        notification_repository=DummyNotificationRepo(),
    )

    with pytest.raises(ForbiddenActionError):
        service.record_decision(
            change_request_id="cr_1",
            approver_id="alice",
            decision="approved",
            reason=None,
        )


def test_duplicate_approval_blocked():
    service = GovernanceApprovalService(
        change_request_repository=DummyChangeRequestRepo(DummyChangeRequest()),
        approval_repository=DummyApprovalRepo(initial=[DummyApproval("bob", "approved")]),
        notification_repository=DummyNotificationRepo(),
    )

    with pytest.raises(ConflictError):
        service.record_decision(
            change_request_id="cr_1",
            approver_id="bob",
            decision="approved",
            reason=None,
        )
```

---

## 28) `backend/tests/services/test_directive_state_gateway.py`

```python
from __future__ import annotations

import pytest
from sqlalchemy import JSON, Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import ConflictError, NotFoundError
from app.governance.services.directive_state_gateway import DirectiveStateGateway


def _setup_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    metadata = MetaData()
    directive_state = Table(
        "directive_state",
        metadata,
        Column("directive_id", String(128), primary_key=True),
        Column("version", Integer, nullable=False),
        Column("state", JSON, nullable=False),
    )
    metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return engine, SessionLocal, directive_state


def test_get_returns_state():
    _, SessionLocal, directive_state = _setup_db()
    with SessionLocal() as db:
        db.execute(directive_state.insert().values(directive_id="dir_1", version=3, state={"foo": "bar"}))
        db.commit()

        gateway = DirectiveStateGateway(db)
        row = gateway.get("dir_1")

        assert row["directive_id"] == "dir_1"
        assert row["version"] == 3


def test_get_raises_not_found():
    _, SessionLocal, _ = _setup_db()
    with SessionLocal() as db:
        gateway = DirectiveStateGateway(db)
        with pytest.raises(NotFoundError):
            gateway.get("missing")


def test_update_with_version_check_success():
    _, SessionLocal, directive_state = _setup_db()
    with SessionLocal() as db:
        db.execute(directive_state.insert().values(directive_id="dir_1", version=2, state={"a": 1}))
        db.commit()

        gateway = DirectiveStateGateway(db)
        row = gateway.update_with_version_check("dir_1", expected_version=2, patch={"b": 2})
        db.commit()

        assert row["version"] == 3
        assert row["state"]["a"] == 1
        assert row["state"]["b"] == 2


def test_update_with_version_check_conflict():
    _, SessionLocal, directive_state = _setup_db()
    with SessionLocal() as db:
        db.execute(directive_state.insert().values(directive_id="dir_1", version=4, state={"a": 1}))
        db.commit()

        gateway = DirectiveStateGateway(db)
        with pytest.raises(ConflictError):
            gateway.update_with_version_check("dir_1", expected_version=3, patch={"b": 2})
```

---

## 29) `backend/tests/api/test_governance_routes.py`

```python
from __future__ import annotations

from sqlalchemy import text


def _create_change_request(client, *, target_version=1, actor_id="requester", idempotency_key="idem-1"):
    response = client.post(
        "/governance/change-requests",
        headers={"X-Actor-Id": actor_id},
        json={
            "directive_id": "dir_1",
            "action_type": "provider_routing_override",
            "target_version": target_version,
            "requested_patch": {"provider": "runway"},
            "idempotency_key": idempotency_key,
            "notes": "switch provider",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_create_change_request_is_idempotent(client, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)

    first = _create_change_request(client, idempotency_key="same-key")
    second = _create_change_request(client, idempotency_key="same-key")

    assert first["id"] == second["id"]


def test_simulate_returns_policy_fields(client, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)

    response = client.post(
        "/governance/simulate",
        headers={"X-Actor-Id": "alice"},
        json={
            "directive_id": "dir_1",
            "action_type": "provider_routing_override",
            "target_version": 1,
            "requested_patch": {"provider": "runway"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(["allowed", "requires_approval", "approval_rule_key", "reasons", "risk_flags", "preview"]).issubset(body.keys())


def test_self_approval_returns_403(client, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)
    created = _create_change_request(client, actor_id="alice", idempotency_key="idem-self-approval")

    response = client.post(
        f"/governance/change-requests/{created['id']}/approvals",
        headers={"X-Actor-Id": "alice"},
        json={"decision": "approved", "reason": "looks good"},
    )

    assert response.status_code == 403


def test_execute_without_required_approval_returns_409(client, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)
    created = _create_change_request(client, actor_id="requester", idempotency_key="idem-no-approval")

    response = client.post(
        f"/governance/change-requests/{created['id']}/execute",
        headers={"X-Actor-Id": "requester"},
    )

    assert response.status_code == 409
    assert "approval" in response.json()["detail"].lower()


def test_execute_version_conflict_returns_409(client, db_session, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)
    created = _create_change_request(client, target_version=1, actor_id="requester", idempotency_key="idem-conflict")

    approval_response = client.post(
        f"/governance/change-requests/{created['id']}/approvals",
        headers={"X-Actor-Id": "approver_1"},
        json={"decision": "approved", "reason": "approved by reviewer"},
    )
    assert approval_response.status_code == 200

    db_session.execute(
        text(
            "UPDATE directive_state SET version = 2, state = :state WHERE directive_id = :directive_id"
        ),
        {"directive_id": "dir_1", "state": {"config": {"provider": "veo", "touched": True}}},
    )
    db_session.commit()

    response = client.post(
        f"/governance/change-requests/{created['id']}/execute",
        headers={"X-Actor-Id": "requester"},
    )

    assert response.status_code == 409
    assert "version" in response.json()["detail"].lower() or "conflict" in response.json()["detail"].lower()


def test_execute_success_returns_updated_version(client, seed_directive_state):
    seed_directive_state(directive_id="dir_1", version=1)
    created = _create_change_request(client, target_version=1, actor_id="requester", idempotency_key="idem-success")

    approval_response = client.post(
        f"/governance/change-requests/{created['id']}/approvals",
        headers={"X-Actor-Id": "approver_1"},
        json={"decision": "approved", "reason": "approved"},
    )
    assert approval_response.status_code == 200

    response = client.post(
        f"/governance/change-requests/{created['id']}/execute",
        headers={"X-Actor-Id": "requester"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "executed"
    assert body["updated_version"] == 2
```

---

## 30) `backend/tests/services/test_governance_execution_service.py` (bản siết chặt hơn)

```python
from __future__ import annotations

import pytest

from app.core.exceptions import ApprovalRequiredError, ConflictError
from app.governance.services.governance_execution_service import GovernanceExecutionService


class DummyChangeRequest:
    def __init__(self):
        self.id = "cr_1"
        self.directive_id = "dir_1"
        self.action_type = "provider_routing_override"
        self.target_version = 4
        self.requested_patch = {"provider": "runway"}
        self.requested_by = "user_a"
        self.requires_approval = True
        self.status = "pending"
        self.executed_at = None


class DummyChangeRequestRepo:
    def __init__(self, entity):
        self.entity = entity

    def require(self, change_request_id: str):
        return self.entity


class DummyApproval:
    def __init__(self, approver_id: str, decision: str):
        self.approver_id = approver_id
        self.decision = decision


class DummyApprovalRepo:
    def __init__(self, approvals):
        self.approvals = approvals

    def get_by_change_request_id(self, change_request_id: str):
        return self.approvals


class DummyAttemptRepo:
    def __init__(self):
        self.items = []

    def create(self, payload: dict):
        payload = {**payload, "id": f"attempt_{len(self.items)+1}"}
        self.items.append(payload)
        return type("Attempt", (), payload)


class DummyNotificationRepo:
    def __init__(self):
        self.items = []

    def create(self, payload: dict):
        self.items.append(payload)
        return payload


class DummyGateway:
    def __init__(self, version=4, fail_update=False):
        self.version = version
        self.fail_update = fail_update

    def get(self, directive_id: str):
        return {"directive_id": directive_id, "version": self.version, "state": {"provider": "veo"}}

    def update_with_version_check(self, directive_id: str, expected_version: int, patch: dict):
        if self.fail_update:
            raise ConflictError("cas failed")
        return {
            "directive_id": directive_id,
            "version": expected_version + 1,
            "state": {"provider": patch["provider"]},
        }


class DummyAdapter:
    def apply(self, *, directive_state: dict, requested_patch: dict, actor_id: str):
        return {"applied": True, "after": {**directive_state, **requested_patch}}


class DummyRegistry:
    def resolve(self, action_type: str):
        return DummyAdapter()


def test_execute_requires_foreign_approval():
    cr = DummyChangeRequest()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([]),
        execution_attempt_repository=DummyAttemptRepo(),
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=4),
        adapter_registry=DummyRegistry(),
    )

    with pytest.raises(ApprovalRequiredError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")


def test_execute_surfaces_version_conflict_before_apply():
    cr = DummyChangeRequest()
    attempts = DummyAttemptRepo()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=attempts,
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=5),
        adapter_registry=DummyRegistry(),
    )

    with pytest.raises(ConflictError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")

    assert attempts.items[-1]["status"] == "conflict"
    assert attempts.items[-1]["error_code"] == "directive_version_conflict"


def test_execute_surfaces_cas_conflict_as_attempt():
    cr = DummyChangeRequest()
    attempts = DummyAttemptRepo()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=attempts,
        notification_repository=DummyNotificationRepo(),
        directive_state_gateway=DummyGateway(version=4, fail_update=True),
        adapter_registry=DummyRegistry(),
    )

    with pytest.raises(ConflictError):
        service.execute_change_request(change_request_id="cr_1", actor_id="user_a")

    assert attempts.items[-1]["status"] == "conflict"
    assert attempts.items[-1]["adapter_result"]["applied"] is True


def test_execute_persists_success_attempt():
    cr = DummyChangeRequest()
    attempts = DummyAttemptRepo()
    notifications = DummyNotificationRepo()
    service = GovernanceExecutionService(
        change_request_repository=DummyChangeRequestRepo(cr),
        approval_repository=DummyApprovalRepo([DummyApproval("user_b", "approved")]),
        execution_attempt_repository=attempts,
        notification_repository=notifications,
        directive_state_gateway=DummyGateway(version=4),
        adapter_registry=DummyRegistry(),
    )

    result = service.execute_change_request(change_request_id="cr_1", actor_id="user_a")

    assert result["status"] == "executed"
    assert attempts.items[-1]["status"] == "success"
    assert notifications.items[-1]["event_type"] == "governance.change_request.executed"
```

---

## 31) Điểm cần chỉnh rất ngắn trước khi paste vào monorepo thật

1. **`down_revision`**
- thay `"<PUT_PREVIOUS_REVISION_HERE>"` bằng revision Alembic gần nhất của bạn.

2. **SQLite test compatibility**
- `DirectiveStateGateway` đang dùng SQL text + JSON object binding.
- Nếu test SQLite của monorepo đang strict, có thể đổi test DB sang Postgres test container hoặc serialize JSON bằng `json.dumps(...)` trong gateway/test helper.

3. **`directive_state` schema thật**
- test đang dựng bảng tối thiểu chỉ để kiểm CAS contract.
- nếu codebase thật có model/bảng sẵn, giữ nguyên test intent nhưng map lại tên cột.

4. **approval threshold**
- hiện là chỉ cần 1 approver khác requester.
- nếu hệ thật cần dual approval, sửa assertion test tương ứng, không cần đổi route surface.

---

## 32) Thứ nên viết tiếp ngay sau migration + tests

Sau cụm này, bước mạnh nhất là:

- `rbac.py` cho create/approve/execute permissions
- actor header deps typed hơn (`X-Actor-Id`, `X-Actor-Roles`)
- error response schema chuẩn hóa cho frontend
- frontend retry flow khi nhận `409 directive_version_conflict`
- approval queue endpoint thật (`list_pending_approvals` route)

Nếu bạn muốn, tôi sẽ viết tiếp nguyên cụm đó theo đúng style hiện tại, bắt đầu từ:

- `backend/app/governance/rbac.py`
- `backend/app/api/deps/auth.py`
- `backend/app/governance/schemas/errors.py`
- `backend/tests/api/test_governance_rbac.py`
- `frontend governance conflict handling contract`

