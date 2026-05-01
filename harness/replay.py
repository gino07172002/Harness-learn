from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

from playwright.async_api import async_playwright

from harness.divergence import find_first_divergence


SNAPSHOT_JS = """
(({ debugMethods, stateGlobals }) => {
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
  const out = {
    debugSnapshot: null,
    debugActionLog: null,
    debugErrors: null,
    debugTiming: null,
    debugMethodResults: {},
    stateSummary: null,
    stateSummaries: {}
  };
  (debugMethods || []).forEach((m) => {
    if (window.debug && typeof window.debug[m] === 'function') {
      const r = safeCall(() => window.debug[m]());
      out.debugMethodResults[m] = r;
      if (m === 'snapshot') out.debugSnapshot = r;
      else if (m === 'actionLog') out.debugActionLog = r;
      else if (m === 'errors') out.debugErrors = r;
      else if (m === 'timing') out.debugTiming = r;
    }
  });
  (stateGlobals || []).forEach((g) => {
    if (g in window) {
      const s = safeCall(() => summarizeValue(window[g]));
      out.stateSummaries[g] = s;
      if (g === 'state') out.stateSummary = s;
    }
  });
  return out;
})
"""


DEFAULT_REPLAY_DEBUG_METHODS = ["snapshot", "actionLog", "errors", "timing"]
DEFAULT_REPLAY_STATE_GLOBALS = ["state"]

RESTORE_ENVIRONMENT_JS = """
((storage) => {
  const localItems = storage.localStorage || {};
  const sessionItems = storage.sessionStorage || {};
  for (const [key, value] of Object.entries(localItems || {})) {
    window.localStorage.setItem(key, value);
  }
  for (const [key, value] of Object.entries(sessionItems || {})) {
    window.sessionStorage.setItem(key, value);
  }
})(__HARNESS_ENVIRONMENT_FIXTURE__)
"""


async def take_replay_snapshot(
    page: Any,
    reason: str,
    debug_methods: list[str] | None = None,
    state_globals: list[str] | None = None,
) -> dict[str, Any]:
    payload = await page.evaluate(
        SNAPSHOT_JS,
        {
            "debugMethods": debug_methods if debug_methods is not None else DEFAULT_REPLAY_DEBUG_METHODS,
            "stateGlobals": state_globals if state_globals is not None else DEFAULT_REPLAY_STATE_GLOBALS,
        },
    )
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


def extract_fixture_storage(trace: dict[str, Any]) -> dict[str, dict[str, str]]:
    fixture = trace.get("environmentFixture") if isinstance(trace, dict) else None
    storage = fixture.get("storage", {}) if isinstance(fixture, dict) else {}

    def items_for(name: str) -> dict[str, str]:
        layer = storage.get(name, {}) if isinstance(storage, dict) else {}
        items = layer.get("items", {}) if isinstance(layer, dict) else {}
        if not isinstance(items, dict):
            return {}
        return {str(key): str(value) for key, value in items.items()}

    return {
        "localStorage": items_for("localStorage"),
        "sessionStorage": items_for("sessionStorage"),
    }


def extract_file_payloads(trace: dict[str, Any], event: dict[str, Any]) -> list[dict[str, Any]]:
    fixture_map = trace.get("fileFixtures", {}) if isinstance(trace, dict) else {}
    ids = ((event.get("form") or {}).get("files") or [])
    payloads: list[dict[str, Any]] = []
    if not isinstance(fixture_map, dict):
        return payloads
    for file_id in ids:
        fixture = fixture_map.get(str(file_id))
        if not isinstance(fixture, dict):
            continue
        raw = fixture.get("base64")
        if not isinstance(raw, str):
            continue
        payloads.append({
            "name": str(fixture.get("name") or str(file_id)),
            "mimeType": str(fixture.get("type") or "application/octet-stream"),
            "buffer": base64.b64decode(raw),
        })
    return payloads


async def restore_environment_fixture(context: Any, trace: dict[str, Any]) -> None:
    storage = extract_fixture_storage(trace)
    if not storage["localStorage"] and not storage["sessionStorage"]:
        return
    script = RESTORE_ENVIRONMENT_JS.replace(
        "__HARNESS_ENVIRONMENT_FIXTURE__",
        json.dumps(storage),
    )
    await context.add_init_script(script)


async def replay_trace_async(trace: dict[str, Any], headed: bool = False) -> dict[str, Any]:
    session = trace.get("session", {})
    proxy_url = session.get("proxyUrl")
    viewport = session.get("viewport") or {"width": 1440, "height": 900}
    if not proxy_url:
        return {"ok": False, "error": "trace.session.proxyUrl is required"}

    replay_console: list[dict[str, Any]] = []
    replay_errors: list[dict[str, Any]] = []
    replay_snapshots: list[dict[str, Any]] = []

    debug_methods = list(session.get("debugMethods") or DEFAULT_REPLAY_DEBUG_METHODS)
    state_globals = list(session.get("stateGlobals") or DEFAULT_REPLAY_STATE_GLOBALS)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=not headed)
        context = await browser.new_context(viewport=viewport)
        await restore_environment_fixture(context, trace)
        page = await context.new_page()
        page.on("console", lambda msg: replay_console.append({"type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda exc: replay_errors.append({"message": str(exc)}))
        await page.goto(session.get("url") or proxy_url)

        replay_snapshots.append(await take_replay_snapshot(page, "capture:start", debug_methods, state_globals))

        completed = 0
        first_failure = None
        for index, event in enumerate(replayable_events(trace)):
            try:
                await apply_event(page, event, trace)
                completed += 1
                replay_snapshots.append(await take_replay_snapshot(page, "after:" + str(event.get("type")), debug_methods, state_globals))
            except Exception as exc:
                first_failure = {
                    "eventIndex": index,
                    "eventType": event.get("type"),
                    "error": str(exc),
                }
                break

        await browser.close()

    aligned_capture = align_capture_snapshots(trace.get("snapshots", []))
    volatile_fields = list(session.get("volatileFields") or [])

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
        volatile_fields=volatile_fields,
    )
    return result


def align_capture_snapshots(capture_snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed_after = {"after:" + t for t in REPLAYABLE_TYPES}
    allowed = {"capture:start"} | allowed_after
    return [s for s in capture_snapshots if s.get("reason") in allowed]


async def apply_event(page: Any, event: dict[str, Any], trace: dict[str, Any] | None = None) -> None:
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
            locator = page.locator(selector)
            payloads = extract_file_payloads(trace or {}, event)
            if payloads:
                # set_input_files already fires the browser's native input/change events,
                # so dispatching the captured event here would replay the selection twice.
                await locator.set_input_files(payloads)
            else:
                await locator.dispatch_event(event_type)


def replay_trace(trace: dict[str, Any], headed: bool = False) -> dict[str, Any]:
    return asyncio.run(replay_trace_async(trace, headed=headed))
