from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.trace_schema import ValidationOutcome, validate_trace_outcome


def validate_trace(trace: Any) -> list[str]:
    """Backwards-compatible facade returning only errors."""
    return validate_trace_outcome(trace).errors


def validate_trace_with_warnings(trace: Any) -> ValidationOutcome:
    return validate_trace_outcome(trace)


def load_trace(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
