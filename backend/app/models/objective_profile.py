import uuid
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ObjectiveProfile(Base):
    __tablename__ = "objective_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    mode: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    objective_stack_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    directive_summary_json: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ttl_minutes: Mapped[int | None] = mapped_column(Integer)
