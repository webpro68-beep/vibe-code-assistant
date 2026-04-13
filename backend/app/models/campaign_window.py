import uuid
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class CampaignWindow(Base):
    __tablename__ = "campaign_windows"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    starts_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
