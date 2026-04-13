from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationDeliveryLog(Base):
    __tablename__ = "notification_delivery_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
