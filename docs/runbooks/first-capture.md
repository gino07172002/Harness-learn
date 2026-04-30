# First Capture Runbook

## Fixture Target

```bash
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

Open `http://127.0.0.1:6173`, press `Start`, interact with the page, and press `Save`.

Replay and report the captured trace:

```bash
python replay_runner.py traces/<trace-file>.json
python report_generator.py traces/<trace-file>.json --out reports/simple-report.md
```

## Reference Target

```bash
git -C d:/claude status --short
python harness_server.py --target d:/claude --target-name claude-editor --port 6173
```

Open `http://127.0.0.1:6173`, press `Start`, perform one small editor operation, and press `Save`.

Check `git -C d:/claude status --short` before and after capture to verify the target remains unmodified.
