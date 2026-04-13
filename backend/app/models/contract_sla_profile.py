import uuid
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ContractSlaProfile(Base):
    __tablename__ = "contract_sla_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_tier: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    target_latency_minutes: Mapped[int | None] = mapped_column(Integer)
    target_success_rate_bps: Mapped[int | None] = mapped_column(Integer)
    penalty_weight: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
