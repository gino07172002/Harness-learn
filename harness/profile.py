from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_DEBUG_METHODS: tuple[str, ...] = ("snapshot", "actionLog", "errors", "timing")


@dataclass(frozen=True)
class Profile:
    name: str
    root: Path
    startup_path: str = "/"
    host: str = "127.0.0.1"
    port: int = 6173
    state_globals: tuple[str, ...] = ("state",)
    volatile_fields: tuple[str, ...] = ()
    debug_methods: tuple[str, ...] = DEFAULT_DEBUG_METHODS
    console_ignore_patterns: tuple[str, ...] = ()
    source_path: Path | None = None


def parse_profile(data: dict[str, Any], source_path: Path) -> Profile:
    if "name" not in data:
        raise ValueError(f"Profile {source_path} missing required field: name")
    raw_root = data.get("root", ".")
    root = (source_path.parent / raw_root).resolve()
    return Profile(
        name=str(data["name"]),
        root=root,
        startup_path=str(data.get("startupPath", "/")),
        host=str(data.get("host", "127.0.0.1")),
        port=int(data.get("port", 6173)),
        state_globals=tuple(data.get("stateGlobals", ["state"])),
        volatile_fields=tuple(data.get("volatileFields", [])),
        debug_methods=tuple(data.get("debugMethods", DEFAULT_DEBUG_METHODS)),
        console_ignore_patterns=tuple(data.get("consoleIgnorePatterns", [])),
        source_path=source_path,
    )


def load_profile(path: Path) -> Profile:
    resolved = path.resolve()
    data = json.loads(resolved.read_text(encoding="utf-8"))
    return parse_profile(data, resolved)
