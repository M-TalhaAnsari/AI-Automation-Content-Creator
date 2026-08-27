"""api/web/services/timing_service.py -- Measures and records pipeline latency timings."""
import time
from typing import Dict, Any, Optional


class LatencyTracker:
    def __init__(self):
        self.start_time = time.monotonic()
        self.checkpoints: Dict[str, float] = {}

    def mark(self, label: str) -> None:
        self.checkpoints[label] = time.monotonic()

    def get_summary(self) -> Dict[str, int]:
        total_turn_ms = int((time.monotonic() - self.start_time) * 1000)
        summary = {"total_turn_ms": total_turn_ms}
        prev_time = self.start_time
        for label, timestamp in self.checkpoints.items():
            duration_ms = int((timestamp - prev_time) * 1000)
            summary[f"{label}_ms"] = duration_ms
            prev_time = timestamp
        return summary
