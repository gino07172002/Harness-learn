# Self-Observing Harness Runbook

## What This Proves

This runbook verifies the harness itself:

- Doctor proves the environment is usable.
- Trace validation proves artifacts follow the trace contract.
- Run logs prove the harness explains its own actions.
- Golden regression proves stable behavior stays stable.

## Doctor

```bash
python harness_doctor.py --target examples/targets/simple --port 6173
python harness_doctor.py --target examples/targets/simple --port 6173 --json
```

## Capture With Run Log

```bash
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

Open `http://127.0.0.1:6173`, press `Start`, perform a small interaction, and press `Save`.

Inspect generated artifacts:

```bash
Get-ChildItem traces
Get-ChildItem runs
Get-Content runs/<run-id>.jsonl
```

## Validate Trace

```bash
python harness_validate_trace.py traces/<trace-file>.json
```

## Replay And Report

```bash
python replay_runner.py traces/<trace-file>.json --run-log runs/<run-id>.jsonl
python report_generator.py traces/<trace-file>.json --out reports/simple-report.md --run-log runs/<run-id>.jsonl
```

## Golden Regression

Start the fixture target:

```bash
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

In another terminal:

```bash
python harness_regress.py --golden examples/golden/simple-trace.json
```
