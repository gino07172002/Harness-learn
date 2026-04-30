from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import async_playwright


REPLAYABLE_TYPES = {
    "pointerdown",
    "pointermove",
    "pointerup",
    "click",
    "keydown",
    "keyup",
    "wheel",
    "input",
    "change",
}


def replayable_events(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [event for event in trace.get("events", []) if event.get("type") in REPLAYABLE_TYPES]


async def replay_trace_async(trace: dict[str, Any], headed: bool = False) -> dict[str, Any]:
    session = trace.get("session", {})
    proxy_url = session.get("proxyUrl")
    viewport = session.get("viewport") or {"width": 1440, "height": 900}
    if not proxy_url:
        return {"ok": False, "error": "trace.session.proxyUrl is required"}

    replay_console: list[dict[str, Any]] = []
    replay_errors: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=not headed)
        page = await browser.new_page(viewport=viewport)
        page.on("console", lambda msg: replay_console.append({"type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda exc: replay_errors.append({"message": str(exc)}))
        await page.goto(proxy_url)

        completed = 0
        first_failure = None
        for index, event in enumerate(replayable_events(trace)):
            try:
                await apply_event(page, event)
                completed += 1
            except Exception as exc:
                first_failure = {
                    "eventIndex": index,
                    "eventType": event.get("type"),
                    "error": str(exc),
                }
                break

        await browser.close()

    return {
        "ok": first_failure is None,
        "completedEvents": completed,
        "firstFailure": first_failure,
        "console": replay_console,
        "errors": replay_errors,
    }


async def apply_event(page: Any, event: dict[str, Any]) -> None:
    event_type = event.get("type")
    pointer = event.get("pointer") or {}
    key = event.get("key") or {}
    wheel = event.get("wheel") or {}

    if event_type in {"pointerdown", "pointermove", "pointerup", "click"}:
        x = pointer.get("x", 0)
        y = pointer.get("y", 0)
        if event_type == "pointermove":
            await page.mouse.move(x, y)
        elif event_type == "pointerdown":
            await page.mouse.move(x, y)
            await page.mouse.down(button="left")
        elif event_type == "pointerup":
            await page.mouse.move(x, y)
            await page.mouse.up(button="left")
        else:
            await page.mouse.click(x, y)
        return

    if event_type in {"keydown", "keyup"}:
        code = key.get("code") or key.get("key")
        if code and code != "character":
            if event_type == "keydown":
                await page.keyboard.down(code)
            else:
                await page.keyboard.up(code)
        return

    if event_type == "wheel":
        await page.mouse.wheel(wheel.get("deltaX", 0), wheel.get("deltaY", 0))
        return

    if event_type in {"input", "change"}:
        selector = (event.get("target") or {}).get("selectorHint")
        if selector:
            await page.locator(selector).dispatch_event(event_type)


def replay_trace(trace: dict[str, Any], headed: bool = False) -> dict[str, Any]:
    return asyncio.run(replay_trace_async(trace, headed=headed))
