from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def require_key(obj: dict[str, Any], key: str, path: str, errors: list[str]) -> Any:
    if key not in obj:
        errors.append(f"{path}.{key}: missing")
        return None
    return obj[key]


def validate_trace(trace: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(trace, dict):
        return [f"trace: expected object, got {type_name(trace)}"]

    version = require_key(trace, "version", "trace", errors)
    if version is not None and version != 1:
        errors.append(f"trace.version: expected 1, got {version!r}")

    session = require_key(trace, "session", "trace", errors)
    if isinstance(session, dict):
        require_key(session, "targetName", "trace.session", errors)
        require_key(session, "proxyUrl", "trace.session", errors)
    elif session is not None:
        errors.append(f"trace.session: expected object, got {type_name(session)}")

    for key in ["events", "snapshots", "console", "errors", "screenshots"]:
        value = require_key(trace, key, "trace", errors)
        if value is not None and not isinstance(value, list):
            errors.append(f"trace.{key}: expected list, got {type_name(value)}")

    replay = require_key(trace, "replay", "trace", errors)
    if replay is not None and not isinstance(replay, dict):
        errors.append(f"trace.replay: expected object or null, got {type_name(replay)}")

    return errors


def load_trace(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
