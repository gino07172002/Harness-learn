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


def run_doctor_checks(target: Path, port: int, host: str = "127.0.0.1") -> list[CheckResult]:
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
