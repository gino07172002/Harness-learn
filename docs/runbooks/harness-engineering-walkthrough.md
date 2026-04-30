# Harness Engineering Walkthrough

This walkthrough is for learning the process by running the harness yourself.
The goal is not only to see green checks. The goal is to understand what each
artifact proves.

Run these commands from the harness project root:

```powershell
cd D:\harness\.worktrees\self-observing-harness
```

## Human Or Agent?

Harness engineering should support both humans and agents.

Humans usually decide:

- what behavior matters
- what evidence is trustworthy
- whether a failure is a product bug, harness bug, or environment issue
- when a regression is important enough to block a change

Agents and automation usually run:

- repeatable checks
- capture/replay flows
- trace validation
- report generation
- golden regression
- CI jobs

The important rule is that humans and agents should use the same commands and
artifacts. If an agent can run a flow but a human cannot reproduce it, the
harness is not transparent enough. If a human can run it but it cannot be
automated, the harness is not repeatable enough.

## The Loop

This project uses this harness engineering loop:

```text
Doctor
  -> Capture
  -> Validate Trace
  -> Replay
  -> Report
  -> Inspect Run Log
  -> Golden Regression
```

Each stage answers one question.

## 1. Doctor

Question:

```text
Can I trust this machine to run the harness?
```

Run:

```powershell
python harness_doctor.py --target examples/targets/simple --port 6173
```

Expected:

```text
HARNESS_DOCTOR
ok: true
```

What this proves:

- Python is usable.
- Required packages are importable.
- Chromium can launch.
- The requested port is free.
- The target has an `index.html`.
- `traces/`, `reports/`, and `runs/` are writable.
- The injected harness client exists.

Harness engineering idea:

Never trust a failed replay until the harness has first proved its own
environment is healthy.

## 2. Capture

Question:

```text
Can the harness observe a target without modifying it?
```

Start the proxy server:

```powershell
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

Open:

```text
http://127.0.0.1:6173
```

In the page:

1. Press `Start`.
2. Click `Increment`.
3. Type a short value in the input.
4. Click the canvas.
5. Press `Save`.

Expected artifacts:

```powershell
Get-ChildItem traces
Get-ChildItem runs
```

What this proves:

- The proxy can serve the target.
- The harness can inject `harness_client.js`.
- The browser client can record events and snapshots.
- The server can save a trace.
- The server can write a run log.

Harness engineering idea:

The trace is evidence from the target. The run log is evidence from the
harness infrastructure.

## 3. Validate Trace

Question:

```text
Is the debug artifact well formed?
```

Pick the newest trace:

```powershell
$trace = Get-ChildItem traces\*.json | Sort-Object LastWriteTime | Select-Object -Last 1
python harness_validate_trace.py $trace.FullName
```

Expected:

```text
Trace valid: ...
```

What this proves:

- The trace has the fields the rest of the harness expects.
- Missing or malformed fields will be reported with exact paths.

Harness engineering idea:

Artifacts need contracts. Without a trace contract, downstream replay and
report failures become guesswork.

## 4. Replay

Question:

```text
Can the harness reproduce the captured behavior?
```

Keep the proxy server running, then run in another terminal:

```powershell
$trace = Get-ChildItem traces\*.json | Sort-Object LastWriteTime | Select-Object -Last 1
$runLog = Get-ChildItem runs\*.jsonl | Sort-Object LastWriteTime | Select-Object -Last 1
python replay_runner.py $trace.FullName --run-log $runLog.FullName
```

Expected:

```json
{
  "ok": true,
  "completedEvents": 13,
  "firstFailure": null
}
```

What this proves:

- The trace can drive browser automation.
- Replay results are written back into the trace.
- Replay completion is appended to the run log.

Harness engineering idea:

Replay is where a user story becomes a reproducible debugging artifact.

## 5. Report

Question:

```text
Can a human or AI understand what happened without watching the session?
```

Run:

```powershell
$trace = Get-ChildItem traces\*.json | Sort-Object LastWriteTime | Select-Object -Last 1
$runLog = Get-ChildItem runs\*.jsonl | Sort-Object LastWriteTime | Select-Object -Last 1
python report_generator.py $trace.FullName --out reports/demo-report.md --run-log $runLog.FullName
```

Open:

```powershell
Get-Content reports\demo-report.md
```

What this proves:

- The trace can be summarized.
- The report contains event counts, timeline, errors, replay status, and
  snapshot evidence.
- Report generation is appended to the run log.

Harness engineering idea:

Reports are not decoration. They are the bridge from raw evidence to debugging
decisions.

## 6. Inspect Run Log

Question:

```text
Can the harness explain its own actions?
```

Run:

```powershell
$runLog = Get-ChildItem runs\*.jsonl | Sort-Object LastWriteTime | Select-Object -Last 1
Get-Content $runLog.FullName
```

Look for events like:

```text
proxy.started
html.injected
client.served
trace.received
trace.saved
replay.completed
report.generated
```

What this proves:

- The harness is not a black box.
- If something fails, the run log narrows down which stage failed.

Harness engineering idea:

A harness that cannot diagnose itself eventually becomes part of the problem.

## 7. Golden Regression

Question:

```text
Did the harness regress compared with known-good behavior?
```

Start the fixture target if it is not already running:

```powershell
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

In another terminal:

```powershell
python harness_regress.py --golden examples/golden/simple-trace.json
```

Expected:

```text
Golden regression passed: examples\golden\simple-trace.json
```

What this proves:

- The golden trace is still valid.
- Replay still works.
- Report generation still produces the stable expected sections.

Harness engineering idea:

Golden traces are how the harness protects itself from silent behavior drift.

## How To Read Failures

When something fails, ask which layer failed:

```text
Doctor failed      -> environment or setup problem
Capture failed     -> proxy, injection, browser client, or trace save problem
Validation failed  -> trace schema problem
Replay failed      -> reproduction or target availability problem
Report failed      -> summarization problem
Run log missing    -> harness observability problem
Regression failed  -> harness behavior changed
```

This is the main habit: do not immediately patch symptoms. Locate the failing
layer first.

## What To Automate

Humans should run the walkthrough while learning or investigating a weird
failure. Automation should run the repeatable subset:

```powershell
python -m pytest -v
node --check harness/static/harness_client.js
python harness_doctor.py --target examples/targets/simple --port 6173
python harness_regress.py --golden examples/golden/simple-trace.json
```

The golden regression needs the fixture server running. In CI, start
`harness_server.py` in the background before running the regression command.
