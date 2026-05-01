from __future__ import annotations

from typing import Any


def build_report_generated_event(path: str) -> dict[str, str]:
    return {"path": path}


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

    lines.extend(["", "## Snapshot Evidence", ""])
    for snapshot in snapshots[:20]:
        lines.append(f"- `{snapshot.get('reason')}` state summary: `{snapshot.get('stateSummary')}` debug snapshot: `{snapshot.get('debugSnapshot')}`")

    if not snapshots:
        lines.append("No snapshots were captured.")

    return "\n".join(lines) + "\n"
