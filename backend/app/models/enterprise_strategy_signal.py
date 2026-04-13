import uuid
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class EnterpriseStrategySignal(Base):
    __tablename__ = "enterprise_strategy_signals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    customer_tier: Mapped[str | None] = mapped_column(String(32), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
