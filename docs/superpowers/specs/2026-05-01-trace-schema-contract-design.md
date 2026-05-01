# Trace Schema Contract Design

## Goal

Turn the trace JSON shape into a single, versioned, machine-checked contract
that every harness component reads from the same source.

Today the trace shape is implicit. `harness/trace_validation.py` checks only
top-level keys and types. Everything below that — event shape, snapshot shape,
`replay.divergence` shape, `session.debugMethodResults`, `passiveProbes` — is
agreed by convention across `harness_client.js`, `harness/replay.py`,
`harness/divergence.py`, and `harness/report.py`. When one of those files
adds or renames a field, nothing fails until a real run produces a confusing
diff or a golden silently drifts.

This stage closes that gap. The trace contract becomes the load-bearing
artifact, and validator / replay / report / divergence all consume it.

## Why This Is Harness Engineering

A harness lives or dies by its artifacts. If the artifact contract is implicit:

- A golden trace can become invalid and we won't know until replay fails for a
  reason that looks like a target bug.
- Two components can disagree about a field name and produce a divergence that
  is really a harness bug.
- A new agent reading `traces/*.json` cannot tell which fields are required,
  which are optional, and which are deprecated.

Schema-as-code makes the trace shape something a new engineer or AI agent can
*read* rather than reverse-engineer.

## Scope

Three increments, in order:

1. Schema definition: a single Python module that defines the trace shape.
2. Validator rewrite: `harness/trace_validation.py` consumes the schema.
3. Negative goldens: a fixture set that proves the validator rejects
   malformed traces with the right messages.

## Non-Goals

- Do not introduce a runtime dependency on `pydantic` or `jsonschema` if
  `dataclasses` plus a small validator can do the job. Harness should stay
  installable from `requirements.txt` without surprises.
- Do not change the on-disk trace format. Existing `traces/*.json` files
  written by the current `harness_client.js` must still validate.
- Do not redesign `harness_client.js`'s recording logic. The schema describes
  what the client already produces, plus what replay and divergence add.
- Do not gate report generation on schema validation yet. Validation runs in
  `harness_validate_trace.py` and `harness_regress.py` first; integration
  into the proxy save path is a later increment.

## Increment 1: Schema Module

Create `harness/trace_schema.py`. This module is the single source of truth
for the trace shape. Other modules import names from it instead of using
string literals or duck-typed dict access.

The module exposes:

- `TRACE_VERSION = 1`
- A typed description of each section: `session`, `events`, `snapshots`,
  `console`, `errors`, `screenshots`, `replay`.
- Per-section field rules: name, type, required vs optional, allowed values
  where the set is closed (for example, snapshot `reason` strings).
- Replayable event types as a closed enum. Today the canonical set lives
  inside `harness/replay.py` and `harness/divergence.py`; this module owns it.
- Snapshot reason patterns: `capture:start`, `after:<replayable_type>`, plus
  any new reasons added later.
- The `replay.divergence` shape: `kind`, `stepIndex`, `reason`, `path`,
  `expected`, `actual`.

Implementation guideline: prefer plain `@dataclass` with type hints plus a
small `validate(obj) -> list[str]` per section. Avoid building a generic
schema framework. The module should read like documentation.

Backwards-compatible additions only. New optional fields are allowed; renames
require a schema version bump (see below).

## Increment 2: Validator Rewrite

Rewrite `harness/trace_validation.py` so it walks the schema instead of
hand-rolling each top-level check.

Behaviors to preserve:

- Returns `list[str]` of error paths and reasons.
- Error messages keep the existing path style: `trace.events[3].type:
  expected one of {...}, got 'pointre'`.
- Empty list means valid.

Behaviors to add:

- Validates events: required fields per `type`, replayable types match the
  schema enum, timestamps are numeric.
- Validates snapshots: `reason` matches an allowed pattern, payload fields
  exist where required, `debugMethodResults` keys are strings.
- Validates `replay`: if present, `divergence` (when set) matches the schema.
- Distinguishes *unknown* fields from *invalid* fields. Unknown fields are a
  warning, not an error, so older traces with extra metadata still pass. The
  validator returns `(errors, warnings)` instead of just errors. CLI prints
  warnings in a separate section so they don't fail CI.

CLI changes in `harness_validate_trace.py`:

- Exit code 0 on no errors, even with warnings.
- Exit code 1 on errors.
- `--strict` flag promotes warnings to errors for use in golden regression.

## Increment 3: Negative Goldens

Add a `examples/golden/invalid/` directory of intentionally malformed traces.
Each fixture has a sibling `.expected.txt` listing the exact validator
messages it should produce.

Suggested first set:

```text
invalid/missing-version.json           trace.version: missing
invalid/wrong-version.json             trace.version: expected 1, got 2
invalid/events-not-list.json           trace.events: expected list, got dict
invalid/event-bad-type.json            trace.events[0].type: not in <enum>
invalid/snapshot-bad-reason.json       trace.snapshots[2].reason: not allowed
invalid/replay-divergence-missing-kind trace.replay.divergence.kind: missing
```

A new test `tests/test_trace_validation_negative.py` iterates the directory,
runs the validator, and asserts each fixture's actual messages match its
expected file. This proves the validator's *rejection* behavior, not just its
acceptance.

The positive golden `examples/golden/simple-trace.json` keeps its role.

## Schema Versioning

Today every trace has `version: 1`. Define the rule:

- Adding an optional field: no version bump.
- Adding a required field, renaming a field, removing a field, or changing
  the meaning of a field: version bump.

When the version bumps, the validator carries support for both N and N-1.
Golden fixtures live alongside their schema version: `examples/golden/v1/`,
`examples/golden/v2/`. Do not delete old goldens on bump; copy and re-record.

This stage stays at version 1. The rule is documented so the next agent has
a clear path.

## Touch Points

Only these files change behavior:

```text
harness/trace_schema.py        new
harness/trace_validation.py    rewrite to consume schema
harness_validate_trace.py      add --strict flag
tests/test_trace_validation.py keep, extend with schema-driven cases
tests/test_trace_validation_negative.py new
examples/golden/invalid/*      new fixtures + expected messages
```

`harness_client.js`, `harness/proxy.py`, `harness/replay.py`,
`harness/report.py`, `harness/divergence.py` are not modified in this stage.
A follow-up can migrate them to import field names from `trace_schema.py`.

## Success Criteria

- `harness/trace_schema.py` exists and is the only place the event-type enum,
  snapshot reason patterns, and divergence shape are defined.
- `python harness_validate_trace.py examples/golden/simple-trace.json`
  succeeds.
- `python harness_validate_trace.py examples/golden/invalid/<file>` fails
  with the message recorded in the matching `.expected.txt`.
- `harness_regress.py --strict` rejects any warning-level drift.
- `pytest -k validation` covers both positive and negative paths.
- All existing tests still pass.

## Teaching Notes

The lesson here: a harness without a schema is a harness whose artifacts can
silently rot. Encourage the reader to look at `trace_schema.py` before any
other file in the project — it is the contract everything else upholds.

Negative goldens are the second lesson. A validator only proves it works
when you can show it rejecting exactly what it should reject. A test suite
that only feeds valid input is half a test suite.
