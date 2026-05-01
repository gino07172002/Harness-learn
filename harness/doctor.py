from __future__ import annotations

import importlib.util
import json
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str


def check_python_version() -> CheckResult:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 10)
    return CheckResult("python.version", ok, f"Python {version}")


def check_import(module_name: str, check_name: str) -> CheckResult:
    found = importlib.util.find_spec(module_name) is not None
    message = f"{module_name} importable" if found else f"{module_name} is not importable"
    return CheckResult(check_name, found, message)


def check_chromium_launch() -> CheckResult:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except PlaywrightError as exc:
        return CheckResult(
            "chromium.launch",
            False,
            f"Chromium could not launch. Run `python -m playwright install chromium`. {exc}",
        )
    return CheckResult("chromium.launch", True, "Chromium launches successfully")


def check_port_available(port: int, host: str = "127.0.0.1") -> CheckResult:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return CheckResult("port.available", False, f"Port {port} is already in use on {host}")
    return CheckResult("port.available", True, f"Port {port} is available on {host}")


def check_target_path(target: Path) -> CheckResult:
    if not target.exists():
        return CheckResult("target.index_html", False, f"Target path does not exist: {target}")
    if not target.is_dir():
        return CheckResult("target.index_html", False, f"Target path is not a directory: {target}")
    index = target / "index.html"
    if not index.exists():
        return CheckResult("target.index_html", False, f"Target does not contain index.html: {target}")
    return CheckResult("target.index_html", True, f"Found {index}")


def check_writable_directory(name: str, directory: Path) -> CheckResult:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".doctor-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult(name, False, f"{directory} is not writable: {exc}")
    return CheckResult(name, True, f"{directory} is writable")


def check_harness_client(path: Path = Path("harness/static/harness_client.js")) -> CheckResult:
    if path.exists() and path.is_file():
        return CheckResult("client.exists", True, f"Found {path}")
    return CheckResult("client.exists", False, f"Missing harness client: {path}")


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

    fields = list(volatile_fields or [])
    if not fields:
        return CheckResult(
            "volatility.suppression",
            True,
            "no volatileFields declared; nothing to verify",
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
            f"volatile field still surfaced: {suppressed.get('path')}; "
            f"declared list (first): {pivot}. "
            f"hint: confirm volatileFields prefix matches the actual snapshot path",
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
            "diff engine failed to report a non-volatile divergence; "
            "suppression is over-broad",
        )

    return CheckResult(
        "volatility.suppression",
        True,
        f"verified suppression for {len(fields)} volatile field(s)",
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
        status = "ok" if item.ok else f"fail - {item.message}"
        lines.append(f"  {item.name}: {status}")
    return "\n".join(lines) + "\n"


def render_doctor_json(results: Iterable[CheckResult]) -> str:
    items = list(results)
    payload = {
        "ok": all(item.ok for item in items),
        "checks": [asdict(item) for item in items],
    }
    return json.dumps(payload, indent=2)
