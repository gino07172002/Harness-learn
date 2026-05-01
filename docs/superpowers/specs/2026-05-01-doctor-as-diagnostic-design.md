# Doctor as Diagnostic Design

## Goal

Promote `harness_doctor.py` from a pass/fail health check into a real
diagnostic tool: every check explains *why* it passed or failed with a
concrete hint, every run records its own timing, and every harness
component emits durations into the run log so a future user can answer
"where is the harness slow?" or "why did this fail on this machine?" from
artifacts alone.

Today doctor returns `ok: true|false` per check (`harness/doctor.py`). When
it fails, the user sees a label but no cause; when it passes, there is no
record of how long the check took or what version of the dependency was
detected. The run log (`runs/*.jsonl`) similarly logs *that* events
happened but not *how long* they took.

This stage makes both observable.

## Why This Is Harness Engineering

A harness's diagnostic surface is what separates "I cannot use this" from
"I can fix this in two minutes." When the doctor only says `ok: false`,
the user is forced to:

- read source to know what the check actually does,
- run subprocess commands to reproduce the failure,
- guess which version mismatch broke things.

That work belongs inside the harness. A diagnostic-quality doctor turns a
30-minute investigation into a 30-second read.

Timing belongs in the run log for the same reason. Today nobody can answer
"is `replay.completed` slow because of Playwright cold start, or because
of the divergence pass?" without instrumenting it themselves.

## Scope

Three increments, in order:

1. Doctor checks return structured detail (version, path, hint), not just
   ok.
2. Run log events carry `durationMs` for the operations that span time.
3. Doctor failures emit actionable hints, including for environment-level
   conflicts (port in use, wrong Python, missing browser).

## Non-Goals

- Do not redesign the doctor CLI. `python harness_doctor.py --target ...
  --port ...` keeps working unchanged.
- Do not add metrics export, Prometheus, or telemetry. Run logs remain
  local JSONL.
- Do not chase cross-platform process inspection. On Windows, `port.in_use`
  may not always identify the holding PID; in that case the hint should
  say so rather than fabricate a value.
- Do not redesign run-log event names. Existing events
  (`proxy.started`, `html.injected`, `trace.saved`, `replay.completed`,
  `report.generated`) keep their names; only their payloads grow.

## Increment 1: Structured Doctor Output

Each check today returns an `ok` boolean. Replace that with a structured
result:

```json
{
  "name": "playwright.import",
  "ok": true,
  "detail": "playwright 1.51.0",
  "durationMs": 84,
  "hint": null
}
```

```json
{
  "name": "chromium.launch",
  "ok": false,
  "detail": "playwright._impl._errors.Error: Executable doesn't exist",
  "durationMs": 312,
  "hint": "run `python -m playwright install chromium`"
}
```

Human output stays compact and readable but adds detail per line:

```text
HARNESS_DOCTOR
ok: false
checks:
  python.version       ok    3.13.1                          12 ms
  playwright.import    ok    playwright 1.51.0               84 ms
  chromium.launch      FAIL  Executable doesn't exist       312 ms
                            hint: run `python -m playwright install chromium`
  port.available       FAIL  6173 in use by PID 1234         18 ms
                            hint: stop the process or pick another port
```

JSON output (`--json`) returns the structured per-check object directly so
agents can consume it without re-parsing text.

The `--json` flag must already exist or be added if missing; this is a
small extension on the existing CLI in `harness/cli.py`.

## Increment 2: Timing in Run Log

Every run-log event that bounds a measurable interval gains a
`durationMs` integer. The instrumentation lives in `harness/run_log.py`
as a small context manager:

```python
with run_logger.timed("replay.completed", trace=trace_path):
    result = run_replay(...)
```

The context manager records `replay.started` immediately, then on exit
records `replay.completed` with `durationMs` measured by a monotonic
clock. The existing `record(...)` API stays for one-shot events.

Required wirings:

- `proxy.started` -> emit `proxy.shutdown` with `durationMs` for the whole
  serve session when the server stops cleanly. This may require catching
  `KeyboardInterrupt` in `harness/proxy.py:run_proxy_server`.
- `replay.started` / `replay.completed` -> use `timed`.
- `report.generation.started` / `report.generated` -> use `timed`.
- `trace.received` / `trace.saved` -> these are sequential and can stay
  as one-shot events, but `trace.saved` should include the request body
  size in `bytes` so a future regression can detect bloat.

Run-log readers must tolerate the new fields. Older log readers (the
walkthrough doc, any external scripts) only ignore extra fields, but the
spec should explicitly note that no field is renamed.

## Increment 3: Actionable Hints

Each doctor failure produces a hint string the user can act on without
reading source. Suggested hints:

```text
python.version              install Python 3.11+ from python.org
required.imports            run `pip install -r requirements.txt`
playwright.import           run `pip install -r requirements.txt`
chromium.launch             run `python -m playwright install chromium`
port.available              port {port} in use by PID {pid}; stop it or pick another
target.path                 path '{path}' does not exist; check --target
target.index_html           target has no index.html; pass --target to a folder
                            with an index.html, or use --startup-path
artifact.dirs.writable      cannot write to {dir}; check filesystem permissions
client.file                 harness/static/harness_client.js missing; reinstall
volatility.suppression      see divergence-volatility-coverage spec; profile
                            volatileFields list does not match snapshot paths
```

Hint strings are values, not formatting code. Define them as constants in
`harness/doctor.py` so tests can assert exact hint strings without
duplicating fragile string templates.

For port conflicts on Windows, attempt to discover the holding PID via
`psutil` *only if* `psutil` is already installed. If not, fall back to
the generic hint `port {port} appears to be in use; pick another or stop
the process`. Do not add a new dependency for this alone.

## Touch Points

```text
harness/doctor.py        rewrite check return type, add hints, add timing
harness/run_log.py       add `timed(...)` context manager, keep `record`
harness/proxy.py         wrap server lifecycle with timing
harness/replay.py        wrap replay with timing
harness/report.py        wrap report generation with timing
harness_doctor.py        no change
tests/test_doctor.py     extend for structured output and hints
tests/test_run_log.py    extend for `timed` context manager and durationMs
```

## Success Criteria

- `python harness_doctor.py --target examples/targets/simple --json` emits
  one structured object per check including `detail`, `durationMs`, and
  `hint`.
- Each failure case in `tests/test_doctor.py` asserts the exact hint
  string the user will see.
- Run logs from a clean capture-replay-report cycle contain a
  `durationMs` field on `replay.completed`, `report.generated`, and
  `proxy.shutdown` (when the proxy is stopped cleanly).
- The walkthrough runbook is updated to point at the new fields so a
  human reader can find them.
- All existing tests still pass.
- `harness_doctor.py` runs in under 2 seconds on a warm machine.

## Teaching Notes

The lesson: *a passing check is also a measurement*. When the doctor
records `playwright.import: ok 84 ms`, it is doing two jobs at once —
proving the import works and giving the next user a baseline. If the
import suddenly takes 4 seconds next month, the run log is the first
place to look.

The second lesson: *every error message is a UX surface*. A hint like
"run `python -m playwright install chromium`" is worth more than a
stack trace, even if the stack trace is technically more informative.
Save both: structured detail for the agent, hint for the human.
