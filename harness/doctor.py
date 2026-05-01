from __future__ import annotations

import importlib.util
import json
import socket
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


HINT_PYTHON_VERSION = "install Python 3.10+ from python.org"
HINT_REQUIRED_IMPORTS = "run `pip install -r requirements.txt`"
HINT_PLAYWRIGHT_IMPORT = "run `pip install -r requirements.txt`"
HINT_CHROMIUM_LAUNCH = "run `python -m playwright install chromium`"
HINT_PORT_AVAILABLE = "port {port} appears to be in use; pick another or stop the process"
HINT_TARGET_PATH = "path '{path}' does not exist; check --target"
HINT_TARGET_INDEX_HTML = "target has no index.html; pass --target to a folder with index.html"
HINT_ARTIFACT_DIRS = "cannot write to {dir}; check filesystem permissions"
HINT_CLIENT_FILE = "harness/static/harness_client.js missing; reinstall the harness"
HINT_VOLATILITY_SUPPRESSION = (
    "see divergence-volatility-coverage spec; profile volatileFields list "
    "does not match snapshot paths"
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str
    detail: str = ""
    duration_ms: int = 0
    hint: str | None = None


def _measure() -> float:
    return time.monotonic()


def _ms_since(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def check_python_version() -> CheckResult:
    start = _measure()
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 10)
    return CheckResult(
        "python.version",
        ok,
        f"Python {version}",
        detail=f"Python {version}",
        duration_ms=_ms_since(start),
        hint=None if ok else HINT_PYTHON_VERSION,
    )


def check_import(module_name: str, check_name: str) -> CheckResult:
    start = _measure()
    spec = importlib.util.find_spec(module_name)
    found = spec is not None
    detail = ""
    if found:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", None)
            if version:
                detail = f"{module_name} {version}"
            else:
                detail = f"{module_name} importable"
        except Exception as exc:
            found = False
            detail = f"{module_name} import failed: {exc}"
    else:
        detail = f"{module_name} not importable"
    hint = None if found else (
        HINT_PLAYWRIGHT_IMPORT if module_name == "playwright" else HINT_REQUIRED_IMPORTS
    )
    return CheckResult(
        check_name,
        found,
        detail,
        detail=detail,
        duration_ms=_ms_since(start),
        hint=hint,
    )


def check_chromium_launch() -> CheckResult:
    start = _measure()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except PlaywrightError as exc:
        return CheckResult(
            "chromium.launch",
            False,
            f"Chromium could not launch: {exc}",
            detail=str(exc),
            duration_ms=_ms_since(start),
            hint=HINT_CHROMIUM_LAUNCH,
        )
    return CheckResult(
        "chromium.launch",
        True,
        "Chromium launches successfully",
        detail="chromium launched headless",
        duration_ms=_ms_since(start),
    )


def check_port_available(port: int, host: str = "127.0.0.1") -> CheckResult:
    start = _measure()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return CheckResult(
                "port.available",
                False,
                f"Port {port} is already in use on {host}",
                detail=f"port {port} bound on {host}",
                duration_ms=_ms_since(start),
                hint=HINT_PORT_AVAILABLE.format(port=port),
            )
    return CheckResult(
        "port.available",
        True,
        f"Port {port} is available on {host}",
        detail=f"port {port} on {host}",
        duration_ms=_ms_since(start),
    )


def check_target_path(target: Path) -> CheckResult:
    start = _measure()
    if not target.exists():
        return CheckResult(
            "target.index_html",
            False,
            f"Target path does not exist: {target}",
            detail=str(target),
            duration_ms=_ms_since(start),
            hint=HINT_TARGET_PATH.format(path=target),
        )
    if not target.is_dir():
        return CheckResult(
            "target.index_html",
            False,
            f"Target path is not a directory: {target}",
            detail=str(target),
            duration_ms=_ms_since(start),
            hint=HINT_TARGET_PATH.format(path=target),
        )
    index = target / "index.html"
    if not index.exists():
        return CheckResult(
            "target.index_html",
            False,
            f"Target does not contain index.html: {target}",
            detail=str(target),
            duration_ms=_ms_since(start),
            hint=HINT_TARGET_INDEX_HTML,
        )
    return CheckResult(
        "target.index_html",
        True,
        f"Found {index}",
        detail=str(index),
        duration_ms=_ms_since(start),
    )


def check_writable_directory(name: str, directory: Path) -> CheckResult:
    start = _measure()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".doctor-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult(
            name,
            False,
            f"{directory} is not writable: {exc}",
            detail=str(directory),
            duration_ms=_ms_since(start),
            hint=HINT_ARTIFACT_DIRS.format(dir=directory),
        )
    return CheckResult(
        name,
        True,
        f"{directory} is writable",
        detail=str(directory),
        duration_ms=_ms_since(start),
    )


def check_harness_client(path: Path = Path("harness/static/harness_client.js")) -> CheckResult:
    start = _measure()
    if path.exists() and path.is_file():
        return CheckResult(
            "client.exists",
            True,
            f"Found {path}",
            detail=str(path),
            duration_ms=_ms_since(start),
        )
    return CheckResult(
        "client.exists",
        False,
        f"Missing harness client: {path}",
        detail=str(path),
        duration_ms=_ms_since(start),
        hint=HINT_CLIENT_FILE,
    )


def check_volatility_suppression(
    volatile_fields: tuple[str, ...] | list[str] | None,
) -> CheckResult:
    """Self-test: prove the volatility wiring still suppresses what it should.

    Synthesizes a snapshot pair that diverges only on the first declared
    volatile field. The diff engine must report no divergence. Then mutates
    a non-volatile field and the diff engine must surface it. If either
    expectation fails, the check fails so the user knows the wiring is
    broken before relying on golden regression.
    """
    from harness.divergence import find_first_divergence

    start = _measure()
    fields = list(volatile_fields or [])
    if not fields:
        return CheckResult(
            "volatility.suppression",
            True,
            "no volatileFields declared; nothing to verify",
            detail="0 volatile fields",
            duration_ms=_ms_since(start),
        )

    pivot = fields[0]
    capture_snapshot = {
        "reason": "capture:start",
        "debugSnapshot": {"ok": True, "value": {"_volatilePivot": "A", "stable": 1}},
        "stateSummary": None,
    }
    replay_snapshot_volatile_only = {
        "reason": "capture:start",
        "debugSnapshot": {"ok": True, "value": {"_volatilePivot": "B", "stable": 1}},
        "stateSummary": None,
    }
    replay_snapshot_stable_diff = {
        "reason": "capture:start",
        "debugSnapshot": {"ok": True, "value": {"_volatilePivot": "A", "stable": 2}},
        "stateSummary": None,
    }

    synthetic_volatile = ["debugSnapshot.value._volatilePivot"] + fields
    suppressed = find_first_divergence(
        {"snapshots": [capture_snapshot], "errors": []},
        {"snapshots": [replay_snapshot_volatile_only], "errors": []},
        volatile_fields=synthetic_volatile,
    )
    if suppressed is not None:
        return CheckResult(
            "volatility.suppression",
            False,
            f"volatile field still surfaced: {suppressed.get('path')}; first declared: {pivot}",
            detail=f"surfaced path: {suppressed.get('path')}",
            duration_ms=_ms_since(start),
            hint=HINT_VOLATILITY_SUPPRESSION,
        )

    surfaced = find_first_divergence(
        {"snapshots": [capture_snapshot], "errors": []},
        {"snapshots": [replay_snapshot_stable_diff], "errors": []},
        volatile_fields=synthetic_volatile,
    )
    if surfaced is None:
        return CheckResult(
            "volatility.suppression",
            False,
            "diff engine failed to report a non-volatile divergence; suppression is over-broad",
            detail="non-volatile field was suppressed",
            duration_ms=_ms_since(start),
            hint=HINT_VOLATILITY_SUPPRESSION,
        )

    return CheckResult(
        "volatility.suppression",
        True,
        f"verified suppression for {len(fields)} volatile field(s)",
        detail=f"{len(fields)} volatile fields verified",
        duration_ms=_ms_since(start),
    )


def run_doctor_checks(
    target: Path,
    port: int,
    host: str = "127.0.0.1",
    volatile_fields: tuple[str, ...] | list[str] | None = None,
) -> list[CheckResult]:
    return [
        check_python_version(),
        check_import("pytest", "pytest.import"),
        check_import("playwright", "playwright.import"),
        check_chromium_launch(),
        check_port_available(port, host),
        check_target_path(target),
        check_writable_directory("traces.writable", Path("traces")),
        check_writable_directory("reports.writable", Path("reports")),
        check_writable_directory("runs.writable", Path("runs")),
        check_harness_client(),
        check_volatility_suppression(volatile_fields),
    ]


def render_doctor_text(results: Iterable[CheckResult]) -> str:
    items = list(results)
    ok = all(item.ok for item in items)
    lines = ["HARNESS_DOCTOR", f"ok: {str(ok).lower()}", "checks:"]
    for item in items:
        if item.ok:
            base = f"  {item.name}: ok"
            extras = []
            if item.detail:
                extras.append(item.detail)
            if item.duration_ms:
                extras.append(f"{item.duration_ms} ms")
            if extras:
                base += "    " + "    ".join(extras)
            lines.append(base)
        else:
            lines.append(f"  {item.name}: fail - {item.message}")
            if item.hint:
                lines.append(f"    hint: {item.hint}")
            if item.duration_ms:
                lines.append(f"    duration: {item.duration_ms} ms")
    # Trailing summary so callers and CI logs can read the last line for a
    # one-shot verdict without scanning the per-check block. Keep the
    # `ok: <bool>` second line untouched so existing parsers still work.
    failed = [item.name for item in items if not item.ok]
    if failed:
        lines.append(f"SUMMARY: {len(failed)} failed ({', '.join(failed)}), {len(items) - len(failed)} ok")
    else:
        lines.append(f"SUMMARY: all {len(items)} checks passed")
    return "\n".join(lines) + "\n"


def render_doctor_json(results: Iterable[CheckResult]) -> str:
    items = list(results)
    payload = {
        "ok": all(item.ok for item in items),
        "checks": [asdict(item) for item in items],
    }
    return json.dumps(payload, indent=2)
