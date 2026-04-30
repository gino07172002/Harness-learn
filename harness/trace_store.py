from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def make_trace_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


class TraceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_trace(self, trace: dict[str, Any], trace_id: str | None = None) -> Path:
        safe_id = trace_id or make_trace_id()
        path = self.root / f"{safe_id}.json"
        path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def read_trace(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))
