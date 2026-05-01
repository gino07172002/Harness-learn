"""End-to-end check: clicking the harness control panel must not pollute
the trace. Boots the proxy against examples/targets/simple, opens the
page with Playwright, clicks the harness Stop button, and inspects the
resulting trace.events to confirm no event has a target inside
#__zero_mod_harness_panel."""
from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.async_api import async_playwright


def _wait_http(url: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1.0) as resp:
                if 200 <= resp.status < 500:
                    return
        except (URLError, ConnectionError, socket.timeout) as exc:
            last = exc
        time.sleep(0.2)
    raise TimeoutError(f"server at {url} not healthy within {timeout}s (last={last})")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _drive_panel(proxy_url: str) -> dict:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(proxy_url)
            await page.wait_for_selector("#__zero_mod_harness_panel", state="attached")
            await page.wait_for_function("window.__ZERO_MOD_HARNESS__ != null", timeout=5000)
            # The panel is user-driven; start capture programmatically so the
            # test focuses on whether subsequent panel clicks pollute the trace.
            await page.evaluate("window.__ZERO_MOD_HARNESS__.startCapture()")
            await page.click("#incrementBtn")
            # Now click Stop on the harness panel
            await page.locator("#__zero_mod_harness_panel button", has_text="Stop").click()
            return await page.evaluate("window.__ZERO_MOD_HARNESS__.trace")
        finally:
            await browser.close()


def test_harness_panel_clicks_do_not_appear_in_trace_events():
    pytest.importorskip("playwright")
    target = Path("examples/targets/simple")
    port = _free_port()
    cmd = [
        sys.executable,
        "harness_server.py",
        "--target", str(target),
        "--target-name", "simple",
        "--host", "127.0.0.1",
        "--port", str(port),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _wait_http(f"http://127.0.0.1:{port}/")
        trace = asyncio.run(_drive_panel(f"http://127.0.0.1:{port}/"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)

    assert trace and "events" in trace, "expected trace from window.__ZERO_MOD_HARNESS__"

    events = trace.get("events", [])
    # The fixture page contains exactly one legitimate button (#incrementBtn).
    # If a panel click leaks, it shows up as an extra click on a button that
    # is not #incrementBtn (the harness panel buttons have no id).
    button_clicks = [
        e for e in events
        if e.get("type") == "click" and (e.get("target") or {}).get("tag") == "button"
    ]
    assert button_clicks, "expected at least one button click in trace"
    leaked = [
        e for e in button_clicks
        if (e.get("target") or {}).get("id") != "incrementBtn"
    ]
    assert leaked == [], (
        f"harness panel click leaked into trace: {leaked}"
    )
    # Sanity: the legitimate target click did make it in.
    target_clicks = [
        e for e in button_clicks
        if (e.get("target") or {}).get("id") == "incrementBtn"
    ]
    assert target_clicks, "expected the #incrementBtn click to be recorded"
