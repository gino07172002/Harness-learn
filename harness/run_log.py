from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


class RunLogger:
    def __init__(self, root: Path, run_id: str | None = None) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or make_run_id()
        self.path = self.root / f"{self.run_id}.jsonl"

    def record(self, event: str, **fields: Any) -> None:
        payload = {
            "time": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    @contextmanager
    def timed(
        self,
        completed_event: str,
        started_event: str | None = None,
        **fields: Any,
    ) -> Iterator[dict[str, Any]]:
        """Record a started event, run the block, record a completed event with durationMs.

        The yielded dict can be mutated to attach extra fields to the
        completed event (e.g. ok=False, error=...).
        """
        start_label = started_event or completed_event.replace(".completed", ".started")
        if start_label == completed_event:
            start_label = f"{completed_event}.started"
        self.record(start_label, **fields)
        completion_fields: dict[str, Any] = {}
        start = time.monotonic()
        try:
            yield completion_fields
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            self.record(
                completed_event,
                durationMs=duration_ms,
                **fields,
                **completion_fields,
            )
