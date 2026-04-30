# Self-Observing Harness Design

## Goal

Extend `d:/harness` so the harness project itself goes through a complete
harness engineering workflow.

The current V1 harness can observe local browser targets, save traces, replay
them, and generate reports. The next stage makes the harness observable too:
each harness run should be diagnosable, repeatable, and regression-tested.

This keeps the learning focus on `d:/harness` as the main project. External apps
such as `examples/targets/simple` and `d:/claude` remain reference targets used
to validate the harness.

## Why This Is Harness Engineering

A mature harness does not only test or observe another system. It also gives
engineers confidence that the harness itself is working correctly.

This stage teaches three harness engineering habits:

1. Check the environment before trusting results.
2. Record the harness's own behavior during a run.
3. Preserve known-good traces as regression fixtures.

In short:

```text
V1:   harness observes target apps
V1.1: harness observes its own execution
V1.2: harness verifies itself against golden traces
```

## Scope

The work proceeds in three increments:

1. Doctor: verify the harness runtime environment.
2. Run Log: record structured internal harness events.
3. Golden Trace Regression: replay known traces and compare report stability.

The order is intentional. Doctor makes the environment reliable, Run Log makes
execution diagnosable, and Golden Trace turns known behavior into regression
coverage.

## Non-Goals

- Do not add Chrome DevTools Protocol heap snapshots yet.
- Do not add breakpoint or local-variable inspection yet.
- Do not add autonomous AI control.
- Do not rewrite target source code.
- Do not make `d:/claude` a required dependency for normal automated tests.

## Increment 1: Doctor

Doctor is a command that answers:

```text
Can this harness run correctly on this machine right now?
```

Expected command:

```bash
python harness_doctor.py --target examples/targets/simple --port 6173
```

Doctor checks:

- Python version.
- Required Python packages import correctly.
- Playwright imports correctly.
- Chromium is installed and launchable.
- Requested port is available.
- Target path exists and has an `index.html`.
- `traces/` and `reports/` are writable.
- The harness client file exists.

Doctor output should be both human-readable and machine-readable:

```text
HARNESS_DOCTOR
ok: true
checks:
  python.version: ok
  playwright.import: ok
  chromium.launch: ok
  port.available: ok
  target.index_html: ok
  traces.writable: ok
```

It should also support JSON output:

```bash
python harness_doctor.py --target examples/targets/simple --json
```

Doctor failure should be actionable. A bad target path should say the target
does not exist. A busy port should name the port. A missing browser should tell
the user to run `python -m playwright install chromium`.

## Increment 2: Run Log

Run Log records what the harness did during a session.

This is separate from target trace data. A trace says what happened inside the
browser target. A run log says what the harness infrastructure did.

Examples of run-log events:

```json
{"event": "proxy.started", "port": 6173, "targetName": "simple"}
{"event": "html.injected", "path": "index.html"}
{"event": "client.served", "path": "/__harness__/client.js"}
{"event": "trace.received", "eventCount": 14, "snapshotCount": 16}
{"event": "trace.saved", "path": "traces/20260430T141051534907Z.json"}
{"event": "replay.started", "trace": "traces/example.json"}
{"event": "replay.completed", "ok": true, "completedEvents": 13}
{"event": "report.generated", "path": "reports/simple-report.md"}
```

Run logs should live under:

```text
runs/
  <run-id>.jsonl
```

Each line is one JSON event. JSONL is easy to append, inspect, and stream.

The harness should include the run ID in generated traces:

```json
{
  "session": {
    "harnessRunId": "20260430T150000123456Z"
  }
}
```

The first version only needs run logs for:

- proxy startup
- HTML injection
- client script serving
- trace receipt
- trace save
- replay start and completion
- report generation

## Increment 3: Golden Trace Regression

Golden traces are stable fixtures that prove the harness still works.

The first golden target is `examples/targets/simple`. The golden trace should
capture a small, deterministic interaction:

1. Start capture.
2. Click `#incrementBtn`.
3. Type into `#nameInput`.
4. Click `#drawCanvas`.
5. Save trace.

Golden fixtures should live under:

```text
examples/golden/
  simple-trace.json
  simple-report.md
```

Expected command:

```bash
python harness_regress.py --golden examples/golden/simple-trace.json
```

Regression should:

- validate the trace shape
- replay the trace
- attach replay result
- generate a report
- compare stable report sections against the checked-in golden report

Some fields are expected to vary, such as timestamps and generated trace IDs.
The regression comparison should normalize volatile fields before comparing.

## Trace Validation

Trace validation supports both Run Log and Golden Trace Regression.

Expected command:

```bash
python harness_validate_trace.py traces/<trace-file>.json
```

Minimum validation rules:

- `version` exists and is `1`.
- `session` exists.
- `session.targetName` exists.
- `session.proxyUrl` exists.
- `events` is a list.
- `snapshots` is a list.
- `console` is a list.
- `errors` is a list.
- `replay` is either `null` or an object.

Validation should report exact paths:

```text
trace.session.targetName: missing
trace.events: expected list, got object
```

## Learning Path

This project should be taught as a sequence of harness engineering questions:

1. Boundary: What is the harness, and what is the system under test?
2. Environment: Can the harness trust the machine it is running on?
3. Instrumentation: What evidence does the harness collect?
4. Artifacts: What files prove what happened?
5. Replay: Can the harness reproduce behavior?
6. Diagnostics: If the harness fails, can we tell why?
7. Regression: Can we prove the harness did not get worse after a change?

The answer in this project:

```text
Boundary: d:/harness is the product; targets are fixtures/materials.
Environment: harness_doctor.py.
Instrumentation: injected client + internal run log.
Artifacts: traces, reports, runs.
Replay: replay_runner.py.
Diagnostics: doctor output + run logs + reports.
Regression: golden trace command.
```

## Success Criteria

This stage is complete when:

- `python harness_doctor.py --target examples/targets/simple` reports success.
- Doctor failures are actionable and tested.
- A proxy run creates a JSONL run log.
- Saved traces include `session.harnessRunId`.
- Replay and report generation append run-log events.
- `python harness_validate_trace.py <trace>` validates good traces and rejects
  malformed traces with useful messages.
- A golden trace regression command can replay a fixture trace and compare a
  normalized report.
- The full test suite passes.

## Teaching Notes

When explaining this work, emphasize that harness engineering is not just
writing tests. It is building a reliable observation system around software.

The important artifacts are:

- the executable harness commands
- the trace files
- the run logs
- the reports
- the golden fixtures
- the tests proving each layer

If a future engineer cannot explain a failure from those artifacts, the harness
is not observable enough yet.
