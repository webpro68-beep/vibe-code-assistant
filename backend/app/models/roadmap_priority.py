import uuid
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class RoadmapPriority(Base):
    __tablename__ = "roadmap_priorities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    roadmap_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
