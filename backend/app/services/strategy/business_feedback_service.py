from __future__ import annotations

from datetime import datetime, timezone


class BusinessFeedbackService:
    def snapshot(self, mode: str, directives: list[dict]) -> dict:
        throughput_index = 1120 if mode == "launch_mode" else 1000
        margin_index = 1080 if mode == "margin_mode" else 1000
        sla_bps = 9975 if mode == "sla_protection_mode" else 9920
        quality_bonus = 20 if mode == "quality_first_mode" else 0
        return {
            "mode": mode,
            "revenue_index": 1000 + max(0, len(directives) * 5),
            "sla_attainment_bps": sla_bps,
            "throughput_index": throughput_index,
            "margin_index": margin_index + quality_bonus,
            "captured_at": datetime.now(timezone.utc),
        }
