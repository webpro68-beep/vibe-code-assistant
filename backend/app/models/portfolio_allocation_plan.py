import uuid
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class PortfolioAllocationPlan(Base):
    __tablename__ = "portfolio_allocation_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    mode: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_name: Mapped[str] = mapped_column(String(255), nullable=False)
    allocation_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    reserve_capacity_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
