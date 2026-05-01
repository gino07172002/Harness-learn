# Divergence Volatility Coverage Design

## Goal

Make `volatileFields` a first-class concept that every divergence path
respects, that the doctor can verify, and that golden regression can prove
is wired correctly before a new target is onboarded.

`harness/divergence.py` already consults `volatile_fields` when diffing
snapshot bodies (`debugSnapshot`, `stateSummary`). That covers the most
common case but leaves three gaps:

1. `first_error_divergence` ignores `volatile_fields` entirely. An error
   message containing a timestamp or generated id will produce a noisy
   divergence even when the user listed it as volatile.
2. There is no replay-time enforcement. Replay snapshots and replay events
   may include fields the profile considers volatile; if a future divergence
   mode (event-level diff, console diff) is added, the volatile list will
   not automatically apply.
3. There is no harness-level test that *proves* a volatile path is
   actually suppressed end-to-end. The unit tests cover the diff function in
   isolation but not the path from `harness.profile.json` to the final
   `replay.divergence` block in a saved trace.

This stage closes those three gaps before any noisy real-world target is
onboarded.

## Why This Is Harness Engineering

Every real target has volatility: timestamps, request ids, animation
phases, retry counters. A harness that cannot suppress volatility will:

- generate divergences that look like target bugs but are harness false
  positives,
- train the user to ignore divergence output,
- corrupt golden regression with non-deterministic diffs.

A harness's job is to give the user a high-signal diff. Volatility handling
is the difference between a tool that gets used and a tool that gets muted.

## Scope

Three increments, in order:

1. Apply `volatile_fields` to error and (future) event divergence paths.
2. Add a profile-driven volatility self-test inside `harness_doctor.py`.
3. Add a golden fixture pair that exercises a known-volatile field and
   proves it is suppressed.

## Non-Goals

- Do not change the on-disk shape of `harness.profile.json`. The
  `volatileFields` array stays as it is.
- Do not introduce regex or jsonpath syntax for volatile fields. The
  current prefix-match rule (`path == prefix or starts with prefix.`
  or `prefix[`) is sufficient for the targets we have. A future spec may
  generalize it.
- Do not auto-detect volatility. The profile owner declares it.
- Do not move volatility handling into the client. Volatility is a
  comparison-time concern, not a capture-time concern; capture should
  always record the raw value.

## Increment 1: Volatility on All Divergence Paths

Update `harness/divergence.py`:

- `first_error_divergence(capture_errors, replay_errors,
  volatile_fields=None)` accepts the same `volatile_fields` argument as
  the snapshot path. The diff over `message` / `reason` is filtered with
  `is_volatile("errors[i].message", ...)`-style paths so the user can mute
  noisy error text by listing `errors[].message` in the profile.
- `find_first_divergence(...)` forwards `volatile_fields` to the error
  branch (it currently does not).
- A new `first_event_divergence(capture_events, replay_events,
  volatile_fields)` is *defined* in the module with a clear docstring even
  if the caller in `harness/replay.py` does not invoke it yet. This
  reserves the API and prevents future drift.

Tests in `tests/test_divergence.py`:

- An error-divergence case where the message differs only in a volatile
  substring path and is correctly suppressed.
- An error-divergence case where a non-volatile field still surfaces.
- A regression test that asserts `find_first_divergence` passes
  `volatile_fields` through to both branches.

## Increment 2: Doctor Self-Test for Volatility

Add a new doctor check that proves the volatility wiring works end-to-end
on the active profile:

```text
volatility.suppression: ok
```

Implementation:

- Doctor synthesizes a tiny capture/replay snapshot pair where one
  declared volatile field differs and one non-volatile field is identical.
- It runs `find_first_divergence` with the profile's `volatileFields` and
  expects `None`.
- It then mutates a non-volatile field and expects a divergence.
- Pass means both expectations held; fail means the wiring is broken.

Doctor failure must be actionable:

```text
volatility.suppression: failed
  reason: profile lists 'session.startedAt' but divergence still reports it
  hint: confirm volatileFields prefix matches the actual snapshot path
```

This is the first doctor check that exercises a *behavior* of the harness,
not just the environment. It should be added in a way that does not slow
doctor down noticeably (target: under 50 ms additional).

## Increment 3: Volatility Golden Pair

Add a golden fixture that includes a known-volatile field and prove
regression handles it.

New files:

```text
examples/golden/volatile-trace.json
examples/golden/volatile-report.md
examples/targets/volatile-fixture/
  index.html
  app.js
  harness.profile.json    volatileFields: ["state.tickCount"]
```

The fixture target increments `state.tickCount` on a timer so every replay
produces a different value. Without the volatile list, the golden
regression would fail; with it, the regression must pass.

`harness_regress.py` gains no new flags. The regression command is the
existing one with a different `--golden` path:

```bash
python harness_regress.py --golden examples/golden/volatile-trace.json
```

A second test asserts that *removing* `state.tickCount` from the profile
makes the regression fail. This proves the suppression is actually doing
the work, not just that the test happens to pass.

## Touch Points

```text
harness/divergence.py             extend error path, add event-path stub
harness/doctor.py                 add volatility.suppression check
harness/regression.py             no change required
examples/targets/volatile-fixture new
examples/golden/volatile-*        new
tests/test_divergence.py          extend
tests/test_doctor.py              add volatility check tests
tests/test_regression.py          add volatile-trace golden case
```

## Success Criteria

- All existing tests still pass.
- `python harness_doctor.py --profile examples/targets/simple/harness.profile.json`
  reports `volatility.suppression: ok`.
- `python harness_regress.py --golden examples/golden/volatile-trace.json`
  passes consistently across at least three consecutive runs.
- A test confirms that emptying the fixture's `volatileFields` makes the
  same regression fail with a divergence on `state.tickCount`.
- `find_first_divergence` is the only public entry point that callers use,
  and it forwards `volatile_fields` to every branch.

## Teaching Notes

There are two ideas worth surfacing here:

1. *Volatility is a contract between the profile and the diff engine.* The
   profile says "this is allowed to drift"; the diff engine honors it.
   The harness's job is to make that contract impossible to break by
   accident.

2. *Prove suppression negatively.* A passing golden regression with
   `volatileFields` set is not enough — you must also show that *without*
   the list the regression would have failed. Otherwise you cannot tell
   whether suppression worked or the field was simply stable that day.
