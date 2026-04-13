class ProviderWebhookEvent(Base):
    __tablename__ = "provider_webhook_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    event_idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    scene_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    provider_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_operation_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)

    headers_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)