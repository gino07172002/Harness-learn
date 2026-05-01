from __future__ import annotations

from typing import Any

from harness.divergence import diff_value


def build_report_generated_event(path: str) -> dict[str, str]:
    return {"path": path}


def _path_value(obj: Any, path: str) -> Any:
    current = obj
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _intent_diagnostics(trace: dict[str, Any]) -> list[dict[str, Any]]:
    replay = trace.get("replay")
    if not isinstance(replay, dict):
        return []

    events = trace.get("events", [])
    capture_snapshots = trace.get("snapshots", [])
    replay_snapshots = replay.get("snapshots", [])
    if not isinstance(events, list) or not isinstance(replay_snapshots, list):
        return []

    by_selector: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        selector = ((event.get("target") or {}).get("selectorHint") or "").strip()
        if not selector:
            continue
        bucket = by_selector.setdefault(
            selector,
            {"pointerdown": 0, "pointerup": 0, "click": 0, "first_pointerup": None},
        )
        event_type = event.get("type")
        if event_type in {"pointerdown", "pointerup", "click"}:
            bucket[event_type] += 1
        if event_type == "pointerup" and bucket["first_pointerup"] is None:
            bucket["first_pointerup"] = index

    volatile_fields = list((trace.get("session") or {}).get("volatileFields") or [])
    volatile_fields.extend(["debugSnapshot.value.gl", "debugMethodResults.snapshot.value.gl"])

    findings: list[dict[str, Any]] = []
    limit = min(len(capture_snapshots), len(replay_snapshots))
    for selector, counts in by_selector.items():
        if counts["pointerdown"] < 3 or counts["pointerup"] < 3 or counts["click"] != 0:
            continue
        start_index = counts["first_pointerup"]
        if start_index is None:
            continue

        # Snapshot 0 is capture:start; snapshot N+1 corresponds to event N.
        for step in range(start_index + 1, limit):
            diff = diff_value(
                capture_snapshots[step].get("debugSnapshot"),
                replay_snapshots[step].get("debugSnapshot"),
                "debugSnapshot",
                volatile_fields,
            )
            if diff is None:
                continue
            path, expected, actual = diff
            baseline = _path_value(capture_snapshots[0], path)
            if baseline != expected:
                continue
            findings.append({
                "selector": selector,
                "pointerdown": counts["pointerdown"],
                "pointerup": counts["pointerup"],
                "click": counts["click"],
                "step": step,
                "path": path,
                "expected": expected,
                "actual": actual,
            })
            break
    return findings


def build_report_markdown(trace: dict[str, Any]) -> str:
    session = trace.get("session", {})
    events = trace.get("events", [])
    snapshots = trace.get("snapshots", [])
    console = trace.get("console", [])
    errors = trace.get("errors", [])
    replay = trace.get("replay")

    lines = [
        "# Harness Debug Report",
        "",
        "## Summary",
        "",
        f"- Target: {session.get('targetName', 'unknown')}",
        f"- Session: {session.get('id', 'unknown')}",
        f"- Proxy URL: {session.get('proxyUrl', 'unknown')}",
        f"- Events: {len(events)}",
        f"- Snapshots: {len(snapshots)}",
        f"- Console entries: {len(console)}",
        f"- Errors: {len(errors)}",
        "",
        "## Operation Timeline",
        "",
    ]

    for index, event in enumerate(events[:50]):
        target = event.get("target") or {}
        lines.append(f"{index + 1}. `{event.get('type')}` on `{target.get('selectorHint', '')}` at `{event.get('time', '')}`")

    if not events:
        lines.append("No user events were captured.")

    lines.extend(["", "## Errors", ""])
    if errors:
        for error in errors[:20]:
            lines.append(f"- `{error.get('type', 'error')}` {error.get('message') or error.get('reason')}")
    else:
        lines.append("No runtime errors were captured.")

    lines.extend(["", "## Console Warnings And Errors", ""])
    console_findings = [entry for entry in console if entry.get("level") in {"warn", "error"}]
    if console_findings:
        for entry in console_findings[:20]:
            lines.append(f"- `{entry.get('level')}` {entry.get('args')}")
    else:
        lines.append("No console warnings or errors were captured.")

    lines.extend(["", "## Replay", ""])
    if replay is None:
        lines.append("Replay has not been run for this trace.")
    elif replay.get("ok"):
        lines.append(f"Replay passed after `{replay.get('completedEvents', 0)}` event(s).")
    else:
        lines.append("Replay failed; first failure is listed below.")
        lines.append("")
        lines.append("```json")
        lines.append(str(replay.get("firstFailure")))
        lines.append("```")

    lines.extend(["", "## Divergence", ""])
    divergence = (replay or {}).get("divergence") if replay else None
    first_failure = (replay or {}).get("firstFailure") if replay else None
    if replay is None:
        lines.append("Replay has not been run for this trace.")
    elif divergence is not None:
        lines.append(
            f"First divergence at step `{divergence.get('stepIndex')}` "
            f"(reason `{divergence.get('reason', '<n/a>')}`, kind `{divergence.get('kind')}`)."
        )
        lines.append("")
        lines.append(f"- Path: `{divergence.get('path')}`")
        lines.append(f"- Expected: `{divergence.get('expected')}`")
        lines.append(f"- Actual: `{divergence.get('actual')}`")
    elif first_failure is not None:
        lines.append(
            f"Replay aborted before state comparison; first divergence is the failed event "
            f"at index `{first_failure.get('eventIndex')}` (`{first_failure.get('eventType')}`)."
        )
    else:
        lines.append("Replay state matches captured state across all aligned snapshots.")

    intent_findings = _intent_diagnostics(trace)
    lines.extend(["", "## Intent Diagnostics", ""])
    if intent_findings:
        for finding in intent_findings[:10]:
            lines.append(
                f"- Possible failed intent on `{finding['selector']}`: "
                f"pointerdown/up: `{finding['pointerdown']}/{finding['pointerup']}`, "
                f"clicks: `{finding['click']}`, first state split at step `{finding['step']}` "
                f"on `{finding['path']}`; capture stayed `{finding['expected']}`; "
                f"replay reached `{finding['actual']}`."
            )
    else:
        lines.append("No repeated pointer intent failures were detected.")

    lines.extend(["", "## Snapshot Evidence", ""])
    for snapshot in snapshots[:20]:
        lines.append(f"- `{snapshot.get('reason')}` state summary: `{snapshot.get('stateSummary')}` debug snapshot: `{snapshot.get('debugSnapshot')}`")

    if not snapshots:
        lines.append("No snapshots were captured.")

    return "\n".join(lines) + "\n"
