import uuid
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class StrategyDirective(Base):
    __tablename__ = "strategy_directives"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    mode: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    directive_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(64), default="global", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ttl_minutes: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
