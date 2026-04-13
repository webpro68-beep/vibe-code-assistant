from __future__ import annotations

from dataclasses import dataclass

from app.services.production.timeline_service import ProductionTimelineService


@dataclass
class EventWriter:
    timeline_service: ProductionTimelineService

    def emit(self, **kwargs):
        return self.timeline_service.write_event(kwargs)
