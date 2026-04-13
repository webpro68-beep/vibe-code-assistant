from __future__ import annotations

import uuid
from datetime import datetime, timezone


class StrategyIngestionService:
    def ingest_signal(self, payload: dict) -> dict:
        item = {
            "id": str(uuid.uuid4()),
            **payload,
            "starts_at": payload.get("starts_at"),
            "ends_at": payload.get("ends_at"),
            "ingested_at": datetime.now(timezone.utc),
        }
        return item
