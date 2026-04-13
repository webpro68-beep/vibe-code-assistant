from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from app.models import CampaignWindow
from app.state import AppState


class CampaignSyncService:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def sync(self, windows: Iterable[CampaignWindow]) -> List[CampaignWindow]:
        synced = []
        for window in windows:
            self.state.campaign_windows[window.id] = window
            synced.append(window)
        return synced

    def active_windows(self, now: datetime | None = None) -> List[CampaignWindow]:
        now = now or datetime.utcnow()
        return [
            window
            for window in self.state.campaign_windows.values()
            if window.is_active and window.starts_at <= now <= window.ends_at
        ]
