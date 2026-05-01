from __future__ import annotations

from typing import Any


def diff_value(expected: Any, actual: Any, path: str = "") -> tuple[str, Any, Any] | None:
    if type(expected) is not type(actual):
        return (path or "<root>", expected, actual)
    if isinstance(expected, dict):
        for key in expected:
            if key not in actual:
                return (f"{path}.{key}".lstrip("."), expected[key], None)
            sub = diff_value(expected[key], actual[key], f"{path}.{key}".lstrip("."))
            if sub is not None:
                return sub
        for key in actual:
            if key not in expected:
                return (f"{path}.{key}".lstrip("."), None, actual[key])
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return (f"{path}.length".lstrip("."), len(expected), len(actual))
        for index, (a, b) in enumerate(zip(expected, actual)):
            sub = diff_value(a, b, f"{path}[{index}]")
            if sub is not None:
                return sub
        return None
    if expected != actual:
        return (path or "<root>", expected, actual)
    return None


SNAPSHOT_COMPARE_FIELDS = ("debugSnapshot", "stateSummary")


def compare_snapshot_pair(
    capture_snapshot: dict[str, Any],
    replay_snapshot: dict[str, Any],
) -> tuple[str, Any, Any] | None:
    for field in SNAPSHOT_COMPARE_FIELDS:
        diff = diff_value(capture_snapshot.get(field), replay_snapshot.get(field), field)
        if diff is not None:
            return diff
    return None


def first_snapshot_divergence(
    capture_snapshots: list[dict[str, Any]],
    replay_snapshots: list[dict[str, Any]],
) -> dict[str, Any] | None:
    pairs = min(len(capture_snapshots), len(replay_snapshots))
    for index in range(pairs):
        cap = capture_snapshots[index]
        rep = replay_snapshots[index]
        diff = compare_snapshot_pair(cap, rep)
        if diff is not None:
            path, expected, actual = diff
            return {
                "kind": "snapshot",
                "stepIndex": index,
                "reason": cap.get("reason"),
                "path": path,
                "expected": expected,
                "actual": actual,
            }
    if len(capture_snapshots) != len(replay_snapshots):
        return {
            "kind": "snapshot",
            "stepIndex": pairs,
            "reason": "<count-mismatch>",
            "path": "snapshots.length",
            "expected": len(capture_snapshots),
            "actual": len(replay_snapshots),
        }
    return None


def first_error_divergence(
    capture_errors: list[dict[str, Any]],
    replay_errors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if len(capture_errors) == len(replay_errors) == 0:
        return None
    pairs = min(len(capture_errors), len(replay_errors))
    for index in range(pairs):
        cap_msg = capture_errors[index].get("message") or capture_errors[index].get("reason")
        rep_msg = replay_errors[index].get("message") or replay_errors[index].get("reason")
        if cap_msg != rep_msg:
            return {
                "kind": "error",
                "stepIndex": index,
                "path": "message",
                "expected": cap_msg,
                "actual": rep_msg,
            }
    if len(capture_errors) != len(replay_errors):
        return {
            "kind": "error",
            "stepIndex": pairs,
            "path": "errors.length",
            "expected": len(capture_errors),
            "actual": len(replay_errors),
        }
    return None


def find_first_divergence(trace: dict[str, Any], replay_result: dict[str, Any]) -> dict[str, Any] | None:
    snapshot_diff = first_snapshot_divergence(
        trace.get("snapshots", []),
        replay_result.get("snapshots", []),
    )
    if snapshot_diff is not None:
        return snapshot_diff
    return first_error_divergence(trace.get("errors", []), replay_result.get("errors", []))
