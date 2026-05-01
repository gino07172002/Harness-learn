from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_DEBUG_METHODS: tuple[str, ...] = ("snapshot", "actionLog", "errors", "timing")
DEFAULT_MAX_ENV_VALUE_BYTES = 1_000_000
DEFAULT_MAX_FILE_BYTES = 10_000_000
DEFAULT_MAX_FILES = 4


@dataclass(frozen=True)
class FileCapture:
    mode: str = "none"
    selectors: tuple[str, ...] = ()
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_files: int = DEFAULT_MAX_FILES


@dataclass(frozen=True)
class StorageCapturePolicy:
    mode: str = "none"
    keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnvironmentCapture:
    local_storage: StorageCapturePolicy = StorageCapturePolicy()
    session_storage: StorageCapturePolicy = StorageCapturePolicy()
    max_value_bytes: int = DEFAULT_MAX_ENV_VALUE_BYTES


@dataclass(frozen=True)
class PassiveProbes:
    dom_snapshot: bool = False
    dom_selectors: tuple[str, ...] = ()
    storage: bool = False
    window_globals_scan: bool = False
    network: bool = False


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
    passive_probes: PassiveProbes = PassiveProbes()
    environment_capture: EnvironmentCapture = EnvironmentCapture()
    file_capture: FileCapture = FileCapture()
    source_path: Path | None = None


def parse_storage_capture_policy(data: Any) -> StorageCapturePolicy:
    raw = data if isinstance(data, dict) else {}
    mode = str(raw.get("mode", "none"))
    if mode not in {"none", "allowlist", "all"}:
        raise ValueError(f"Unsupported environmentCapture storage mode: {mode}")
    return StorageCapturePolicy(
        mode=mode,
        keys=tuple(str(key) for key in raw.get("keys", [])),
    )


def parse_environment_capture(data: Any) -> EnvironmentCapture:
    raw = data if isinstance(data, dict) else {}
    return EnvironmentCapture(
        local_storage=parse_storage_capture_policy(raw.get("localStorage")),
        session_storage=parse_storage_capture_policy(raw.get("sessionStorage")),
        max_value_bytes=int(raw.get("maxValueBytes", DEFAULT_MAX_ENV_VALUE_BYTES)),
    )


def parse_file_capture(data: Any) -> FileCapture:
    raw = data if isinstance(data, dict) else {}
    mode = str(raw.get("mode", "none"))
    if mode not in {"none", "allowlist", "all"}:
        raise ValueError(f"Unsupported fileCapture mode: {mode}")
    return FileCapture(
        mode=mode,
        selectors=tuple(str(selector) for selector in raw.get("selectors", [])),
        max_file_bytes=int(raw.get("maxFileBytes", DEFAULT_MAX_FILE_BYTES)),
        max_files=int(raw.get("maxFiles", DEFAULT_MAX_FILES)),
    )


def parse_profile(data: dict[str, Any], source_path: Path) -> Profile:
    if "name" not in data:
        raise ValueError(f"Profile {source_path} missing required field: name")
    raw_root = data.get("root", ".")
    root = (source_path.parent / raw_root).resolve()
    raw_probes = data.get("passiveProbes") or {}
    environment_capture = parse_environment_capture(data.get("environmentCapture"))
    file_capture = parse_file_capture(data.get("fileCapture"))
    passive_probes = PassiveProbes(
        dom_snapshot=bool(raw_probes.get("domSnapshot", False)),
        dom_selectors=tuple(raw_probes.get("domSelectors", [])),
        storage=bool(raw_probes.get("storage", False)),
        window_globals_scan=bool(raw_probes.get("windowGlobalsScan", False)),
        network=bool(raw_probes.get("network", False)),
    )
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
        passive_probes=passive_probes,
        environment_capture=environment_capture,
        file_capture=file_capture,
        source_path=source_path,
    )


def load_profile(path: Path) -> Profile:
    resolved = path.resolve()
    data = json.loads(resolved.read_text(encoding="utf-8"))
    return parse_profile(data, resolved)
