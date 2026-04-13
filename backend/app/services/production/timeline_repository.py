from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryTimelineRepository:
    runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def upsert_run(self, run: dict[str, Any]) -> dict[str, Any]:
        existing = self.runs.get(run["id"], {})
        merged = {**existing, **run}
        self.runs[run["id"]] = merged
        return merged

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.runs.get(run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        return list(self.runs.values())

    def add_event(self, event: dict[str, Any]) -> dict[str, Any]:
        self.events.append(event)
        return event

    def list_events_for_run(self, run_id: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["production_run_id"] == run_id]
