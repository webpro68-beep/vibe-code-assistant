import uuid
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class BusinessOutcomeSnapshot(Base):
    __tablename__ = "business_outcome_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    mode: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    revenue_index: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    sla_attainment_bps: Mapped[int] = mapped_column(Integer, default=9900, nullable=False)
    throughput_index: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    margin_index: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    captured_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
