"""Single source of truth for the harness trace shape.

Other modules import names from here instead of using string literals or
duck-typed dict access. The shape is described as plain dataclasses plus
small validate functions per section so the file reads as documentation.

Versioning rule (see docs/superpowers/specs/2026-05-01-trace-schema-contract-design.md):
- Adding an optional field: no version bump.
- Renaming, removing, or changing the meaning of a field: version bump,
  and the validator must support both N and N-1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


TRACE_VERSION = 1


REPLAYABLE_EVENT_TYPES: frozenset[str] = frozenset(
    {
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
)


NON_REPLAYABLE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "console",
        "error",
        "navigation",
        "load",
        "visibility",
    }
)


ALL_EVENT_TYPES: frozenset[str] = REPLAYABLE_EVENT_TYPES | NON_REPLAYABLE_EVENT_TYPES


SNAPSHOT_REASONS_FIXED: frozenset[str] = frozenset(
    {"capture:start", "capture:stop", "capture:save"}
)


def is_allowed_snapshot_reason(reason: Any) -> bool:
    if not isinstance(reason, str):
        return False
    if reason in SNAPSHOT_REASONS_FIXED:
        return True
    if reason.startswith("after:"):
        suffix = reason[len("after:"):]
        return suffix in REPLAYABLE_EVENT_TYPES
    return False


DIVERGENCE_KINDS: frozenset[str] = frozenset({"snapshot", "error", "event"})


TOP_LEVEL_LIST_FIELDS: tuple[str, ...] = (
    "events",
    "snapshots",
    "console",
    "errors",
    "screenshots",
)


REQUIRED_SESSION_FIELDS: tuple[str, ...] = ("targetName", "proxyUrl")


KNOWN_SESSION_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "targetName",
        "targetRoot",
        "proxyUrl",
        "url",
        "viewport",
        "harnessRunId",
        "controller",
        "mode",
        "debugMethods",
        "stateGlobals",
        "consoleIgnorePatterns",
        "volatileFields",
        "passiveProbes",
        "debugHelp",
        "startedAt",
        "userAgent",
    }
)


KNOWN_TOP_LEVEL_FIELDS: frozenset[str] = frozenset(
    {
        "version",
        "session",
        "replay",
        "environmentFixture",
        "fileFixtures",
        *TOP_LEVEL_LIST_FIELDS,
    }
)


@dataclass
class ValidationOutcome:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def extend(self, other: "ValidationOutcome") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def _check_required(obj: dict, key: str, path: str, outcome: ValidationOutcome) -> Any:
    if key not in obj:
        outcome.errors.append(f"{path}.{key}: missing")
        return None
    return obj[key]


def _check_unknown_keys(
    obj: dict, known: Iterable[str], path: str, outcome: ValidationOutcome
) -> None:
    known_set = set(known)
    for key in obj:
        if key not in known_set:
            outcome.warnings.append(f"{path}.{key}: unknown field")


def validate_session(session: Any, outcome: ValidationOutcome) -> None:
    path = "trace.session"
    if not isinstance(session, dict):
        outcome.errors.append(f"{path}: expected dict, got {type_name(session)}")
        return
    for key in REQUIRED_SESSION_FIELDS:
        _check_required(session, key, path, outcome)
    if "viewport" in session:
        viewport = session["viewport"]
        if not isinstance(viewport, dict):
            outcome.errors.append(f"{path}.viewport: expected dict, got {type_name(viewport)}")
        else:
            for vkey in ("width", "height"):
                if vkey in viewport and not isinstance(viewport[vkey], (int, float)):
                    outcome.errors.append(
                        f"{path}.viewport.{vkey}: expected number, got {type_name(viewport[vkey])}"
                    )
    for list_key in ("debugMethods", "stateGlobals", "consoleIgnorePatterns", "volatileFields"):
        if list_key in session and session[list_key] is not None:
            value = session[list_key]
            if not isinstance(value, list):
                outcome.errors.append(
                    f"{path}.{list_key}: expected list, got {type_name(value)}"
                )
            else:
                for index, item in enumerate(value):
                    if not isinstance(item, str):
                        outcome.errors.append(
                            f"{path}.{list_key}[{index}]: expected string, got {type_name(item)}"
                        )
    _check_unknown_keys(session, KNOWN_SESSION_FIELDS, path, outcome)


def validate_event(event: Any, path: str, outcome: ValidationOutcome) -> None:
    if not isinstance(event, dict):
        outcome.errors.append(f"{path}: expected dict, got {type_name(event)}")
        return
    event_type = event.get("type")
    if "type" not in event:
        outcome.errors.append(f"{path}.type: missing")
    elif not isinstance(event_type, str):
        outcome.errors.append(f"{path}.type: expected string, got {type_name(event_type)}")
    elif event_type not in ALL_EVENT_TYPES:
        outcome.warnings.append(
            f"{path}.type: '{event_type}' not in known event types"
        )
    if "time" in event and not isinstance(event["time"], (int, float)):
        outcome.errors.append(
            f"{path}.time: expected number, got {type_name(event['time'])}"
        )


def validate_snapshot(snapshot: Any, path: str, outcome: ValidationOutcome) -> None:
    if not isinstance(snapshot, dict):
        outcome.errors.append(f"{path}: expected dict, got {type_name(snapshot)}")
        return
    if "reason" not in snapshot:
        outcome.errors.append(f"{path}.reason: missing")
    elif not is_allowed_snapshot_reason(snapshot["reason"]):
        outcome.warnings.append(
            f"{path}.reason: '{snapshot['reason']}' not in allowed snapshot reasons"
        )
    if "debugMethodResults" in snapshot:
        results = snapshot["debugMethodResults"]
        if not isinstance(results, dict):
            outcome.errors.append(
                f"{path}.debugMethodResults: expected dict, got {type_name(results)}"
            )
        else:
            for key in results:
                if not isinstance(key, str):
                    outcome.errors.append(
                        f"{path}.debugMethodResults: keys must be strings"
                    )
                    break


def validate_divergence(divergence: Any, path: str, outcome: ValidationOutcome) -> None:
    if divergence is None:
        return
    if not isinstance(divergence, dict):
        outcome.errors.append(f"{path}: expected dict or null, got {type_name(divergence)}")
        return
    kind = divergence.get("kind")
    if "kind" not in divergence:
        outcome.errors.append(f"{path}.kind: missing")
    elif kind not in DIVERGENCE_KINDS:
        outcome.errors.append(
            f"{path}.kind: expected one of {sorted(DIVERGENCE_KINDS)}, got {kind!r}"
        )
    for required in ("path", "expected", "actual"):
        if required not in divergence:
            outcome.errors.append(f"{path}.{required}: missing")


def validate_replay(replay: Any, outcome: ValidationOutcome) -> None:
    path = "trace.replay"
    if replay is None:
        return
    if not isinstance(replay, dict):
        outcome.errors.append(f"{path}: expected dict or null, got {type_name(replay)}")
        return
    if "ok" in replay and not isinstance(replay["ok"], bool):
        outcome.errors.append(f"{path}.ok: expected bool, got {type_name(replay['ok'])}")
    if "completedEvents" in replay and not isinstance(replay["completedEvents"], int):
        outcome.errors.append(
            f"{path}.completedEvents: expected int, got {type_name(replay['completedEvents'])}"
        )
    if "divergence" in replay:
        validate_divergence(replay["divergence"], f"{path}.divergence", outcome)


def validate_trace_outcome(trace: Any) -> ValidationOutcome:
    outcome = ValidationOutcome()
    if not isinstance(trace, dict):
        outcome.errors.append(f"trace: expected dict, got {type_name(trace)}")
        return outcome

    if "version" not in trace:
        outcome.errors.append("trace.version: missing")
    elif trace["version"] != TRACE_VERSION:
        outcome.errors.append(
            f"trace.version: expected {TRACE_VERSION}, got {trace['version']!r}"
        )

    if "session" in trace:
        validate_session(trace["session"], outcome)
    else:
        outcome.errors.append("trace.session: missing")

    for list_key in TOP_LEVEL_LIST_FIELDS:
        if list_key not in trace:
            outcome.errors.append(f"trace.{list_key}: missing")
            continue
        value = trace[list_key]
        if not isinstance(value, list):
            outcome.errors.append(
                f"trace.{list_key}: expected list, got {type_name(value)}"
            )
            continue
        if list_key == "events":
            for index, item in enumerate(value):
                validate_event(item, f"trace.events[{index}]", outcome)
        elif list_key == "snapshots":
            for index, item in enumerate(value):
                validate_snapshot(item, f"trace.snapshots[{index}]", outcome)

    if "replay" not in trace:
        outcome.errors.append("trace.replay: missing")
    else:
        validate_replay(trace["replay"], outcome)

    _check_unknown_keys(trace, KNOWN_TOP_LEVEL_FIELDS, "trace", outcome)

    return outcome
