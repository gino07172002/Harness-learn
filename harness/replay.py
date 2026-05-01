from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import async_playwright

from harness.divergence import find_first_divergence


SNAPSHOT_JS = """
(() => {
  function summarizeValue(value) {
    if (value === null) return null;
    const t = typeof value;
    if (t === 'string') return { type: 'string', length: value.length, sample: value.slice(0, 80) };
    if (t === 'number' || t === 'boolean') return value;
    if (Array.isArray(value)) return { type: 'array', length: value.length, sample: value.slice(0, 5) };
    if (t === 'object') return { type: 'object', constructor: value.constructor ? value.constructor.name : 'Object', keys: Object.keys(value).slice(0, 30) };
    return { type: t };
  }
  function safeCall(fn) {
    try { return { ok: true, value: fn() }; }
    catch (e) { return { ok: false, error: String(e && e.message ? e.message : e) }; }
  }
  const out = { debugSnapshot: null, debugActionLog: null, debugErrors: null, debugTiming: null, stateSummary: null };
  if (window.debug && typeof window.debug.snapshot === 'function') out.debugSnapshot = safeCall(() => window.debug.snapshot());
  if (window.debug && typeof window.debug.actionLog === 'function') out.debugActionLog = safeCall(() => window.debug.actionLog());
  if (window.debug && typeof window.debug.errors === 'function') out.debugErrors = safeCall(() => window.debug.errors());
  if (window.debug && typeof window.debug.timing === 'function') out.debugTiming = safeCall(() => window.debug.timing());
  if ('state' in window) out.stateSummary = safeCall(() => summarizeValue(window.state));
  return out;
})()
"""


async def take_replay_snapshot(page: Any, reason: str) -> dict[str, Any]:
    payload = await page.evaluate(SNAPSHOT_JS)
    return {"reason": reason, **payload}


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


def attach_replay_result(trace: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    updated = dict(trace)
    updated["replay"] = result
    return updated


def build_replay_completed_event(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(result.get("ok")),
        "completedEvents": int(result.get("completedEvents", 0)),
    }


async def replay_trace_async(trace: dict[str, Any], headed: bool = False) -> dict[str, Any]:
    session = trace.get("session", {})
    proxy_url = session.get("proxyUrl")
    viewport = session.get("viewport") or {"width": 1440, "height": 900}
    if not proxy_url:
        return {"ok": False, "error": "trace.session.proxyUrl is required"}

    replay_console: list[dict[str, Any]] = []
    replay_errors: list[dict[str, Any]] = []
    replay_snapshots: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=not headed)
        page = await browser.new_page(viewport=viewport)
        page.on("console", lambda msg: replay_console.append({"type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda exc: replay_errors.append({"message": str(exc)}))
        await page.goto(proxy_url)

        replay_snapshots.append(await take_replay_snapshot(page, "capture:start"))

        completed = 0
        first_failure = None
        for index, event in enumerate(replayable_events(trace)):
            try:
                await apply_event(page, event)
                completed += 1
                replay_snapshots.append(await take_replay_snapshot(page, "after:" + str(event.get("type"))))
            except Exception as exc:
                first_failure = {
                    "eventIndex": index,
                    "eventType": event.get("type"),
                    "error": str(exc),
                }
                break

        await browser.close()

    aligned_capture = align_capture_snapshots(trace.get("snapshots", []))

    result: dict[str, Any] = {
        "ok": first_failure is None,
        "completedEvents": completed,
        "firstFailure": first_failure,
        "console": replay_console,
        "errors": replay_errors,
        "snapshots": replay_snapshots,
    }
    result["divergence"] = find_first_divergence(
        {"snapshots": aligned_capture, "errors": trace.get("errors", [])},
        result,
    )
    return result


def align_capture_snapshots(capture_snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed_after = {"after:" + t for t in REPLAYABLE_TYPES}
    allowed = {"capture:start"} | allowed_after
    return [s for s in capture_snapshots if s.get("reason") in allowed]


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
