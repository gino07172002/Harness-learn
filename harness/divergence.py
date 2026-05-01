from __future__ import annotations

from typing import Any


def is_volatile(path: str, volatile_fields: tuple[str, ...] | list[str] | None) -> bool:
    if not volatile_fields:
        return False
    for prefix in volatile_fields:
        if path == prefix or path.startswith(prefix + ".") or path.startswith(prefix + "["):
            return True
    return False


def diff_value(
    expected: Any,
    actual: Any,
    path: str = "",
    volatile_fields: tuple[str, ...] | list[str] | None = None,
) -> tuple[str, Any, Any] | None:
    if is_volatile(path, volatile_fields):
        return None
    if type(expected) is not type(actual):
        return (path or "<root>", expected, actual)
    if isinstance(expected, dict):
        for key in expected:
            sub_path = f"{path}.{key}".lstrip(".")
            if is_volatile(sub_path, volatile_fields):
                continue
            if key not in actual:
                return (sub_path, expected[key], None)
            sub = diff_value(expected[key], actual[key], sub_path, volatile_fields)
            if sub is not None:
                return sub
        for key in actual:
            sub_path = f"{path}.{key}".lstrip(".")
            if is_volatile(sub_path, volatile_fields):
                continue
            if key not in expected:
                return (sub_path, None, actual[key])
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return (f"{path}.length".lstrip("."), len(expected), len(actual))
        for index, (a, b) in enumerate(zip(expected, actual)):
            sub = diff_value(a, b, f"{path}[{index}]", volatile_fields)
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
    volatile_fields: tuple[str, ...] | list[str] | None = None,
) -> tuple[str, Any, Any] | None:
    for field in SNAPSHOT_COMPARE_FIELDS:
        diff = diff_value(
            capture_snapshot.get(field),
            replay_snapshot.get(field),
            field,
            volatile_fields,
        )
        if diff is not None:
            return diff
    return None


def first_snapshot_divergence(
    capture_snapshots: list[dict[str, Any]],
    replay_snapshots: list[dict[str, Any]],
    volatile_fields: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any] | None:
    pairs = min(len(capture_snapshots), len(replay_snapshots))
    for index in range(pairs):
        cap = capture_snapshots[index]
        rep = replay_snapshots[index]
        diff = compare_snapshot_pair(cap, rep, volatile_fields)
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
    volatile_fields: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any] | None:
    if len(capture_errors) == len(replay_errors) == 0:
        return None
    pairs = min(len(capture_errors), len(replay_errors))
    for index in range(pairs):
        cap_msg = capture_errors[index].get("message") or capture_errors[index].get("reason")
        rep_msg = replay_errors[index].get("message") or replay_errors[index].get("reason")
        path = f"errors[{index}].message"
        if cap_msg != rep_msg and not is_volatile(path, volatile_fields):
            return {
                "kind": "error",
                "stepIndex": index,
                "path": path,
                "expected": cap_msg,
                "actual": rep_msg,
            }
    if len(capture_errors) != len(replay_errors) and not is_volatile(
        "errors.length", volatile_fields
    ):
        return {
            "kind": "error",
            "stepIndex": pairs,
            "path": "errors.length",
            "expected": len(capture_errors),
            "actual": len(replay_errors),
        }
    return None


def first_event_divergence(
    capture_events: list[dict[str, Any]],
    replay_events: list[dict[str, Any]],
    volatile_fields: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any] | None:
    """Reserved API for future event-level divergence diffing.

    The caller in harness.replay does not yet invoke this; defining the
    signature here ensures the volatility contract applies the moment
    event-level diffing turns on. See
    docs/superpowers/specs/2026-05-01-divergence-volatility-coverage-design.md.
    """
    if len(capture_events) != len(replay_events) and not is_volatile(
        "events.length", volatile_fields
    ):
        return {
            "kind": "event",
            "stepIndex": min(len(capture_events), len(replay_events)),
            "path": "events.length",
            "expected": len(capture_events),
            "actual": len(replay_events),
        }
    pairs = min(len(capture_events), len(replay_events))
    for index in range(pairs):
        diff = diff_value(
            capture_events[index],
            replay_events[index],
            f"events[{index}]",
            volatile_fields,
        )
        if diff is not None:
            path, expected, actual = diff
            return {
                "kind": "event",
                "stepIndex": index,
                "path": path,
                "expected": expected,
                "actual": actual,
            }
    return None


def find_first_divergence(
    trace: dict[str, Any],
    replay_result: dict[str, Any],
    volatile_fields: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any] | None:
    snapshot_diff = first_snapshot_divergence(
        trace.get("snapshots", []),
        replay_result.get("snapshots", []),
        volatile_fields,
    )
    if snapshot_diff is not None:
        return snapshot_diff
    return first_error_divergence(
        trace.get("errors", []),
        replay_result.get("errors", []),
        volatile_fields,
    )
