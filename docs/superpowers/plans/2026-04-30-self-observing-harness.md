# Self-Observing Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `d:/harness` observable as a harness project by adding doctor checks, trace validation, structured run logs, and golden trace regression.

**Architecture:** Add small focused modules under `harness/` and thin root CLI wrappers, matching the existing command style. Doctor verifies the environment before a run, trace validation verifies debug artifacts, run logs record the harness infrastructure's own behavior, and regression replays golden traces to prove the harness still works.

**Tech Stack:** Python 3 standard library, pytest, Playwright for Python, JSON/JSONL artifacts, existing vanilla JavaScript harness client.

---

## Teaching Frame

This stage teaches the second layer of harness engineering:

```text
Layer 1: The harness observes target apps.
Layer 2: The harness observes and verifies itself.
```

Each task maps to one harness engineering question:

- Doctor: Can the harness trust the current machine?
- Trace validation: Are the debug artifacts well-formed?
- Run log: Can the harness explain what it did?
- Golden regression: Can the harness prove it did not regress?

---

## File Structure

- Create `harness_doctor.py`: root CLI wrapper.
- Create `harness_validate_trace.py`: root CLI wrapper.
- Create `harness_regress.py`: root CLI wrapper.
- Modify `harness/cli.py`: add doctor, validation, and regression parsers and entry points.
- Create `harness/doctor.py`: environment checks and human/JSON output models.
- Create `harness/trace_validation.py`: trace shape validation with exact error paths.
- Create `harness/run_log.py`: JSONL run logger and run ID helpers.
- Modify `harness/proxy.py`: create run log on server startup and append proxy events.
- Modify `harness/static/harness_client.js`: include `harnessRunId` in trace session.
- Modify `harness/replay.py`: optionally append replay events to a run log.
- Modify `harness/report.py`: optionally append report generation events.
- Create `harness/regression.py`: golden trace replay/report comparison helpers.
- Create `examples/golden/simple-trace.json`: deterministic golden trace fixture.
- Create `examples/golden/simple-report.md`: normalized golden report fixture.
- Create `runs/.gitkeep`: keep run-log directory in git while ignoring generated logs.
- Modify `.gitignore`: ignore generated `runs/*.jsonl`.
- Create `tests/test_doctor.py`: doctor unit tests.
- Create `tests/test_trace_validation.py`: trace validator unit tests.
- Create `tests/test_run_log.py`: run log unit tests.
- Create `tests/test_regression.py`: report normalization and golden comparison tests.
- Modify `tests/test_cli_smoke.py`: smoke-test new root CLIs.
- Create `docs/runbooks/self-observing-harness.md`: how to run Doctor, validation, run logs, and regression.

---

### Task 1: Doctor Command

**Harness engineering lesson:** Environment comes before evidence. A harness result is only trustworthy if the harness can first prove its runtime is usable.

**Files:**
- Create: `harness/doctor.py`
- Create: `harness_doctor.py`
- Modify: `harness/cli.py`
- Modify: `tests/test_cli_smoke.py`
- Create: `tests/test_doctor.py`

- [ ] **Step 1: Write failing doctor tests**

Create `tests/test_doctor.py`:

```python
from pathlib import Path

from harness.doctor import CheckResult, check_target_path, check_writable_directory, render_doctor_text


def test_check_target_path_passes_for_directory_with_index(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "index.html").write_text("<html></html>", encoding="utf-8")

    result = check_target_path(target)

    assert result.name == "target.index_html"
    assert result.ok is True


def test_check_target_path_fails_for_missing_index(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()

    result = check_target_path(target)

    assert result.ok is False
    assert "index.html" in result.message


def test_check_writable_directory_creates_directory_and_writes_probe(tmp_path: Path):
    directory = tmp_path / "runs"

    result = check_writable_directory("runs.writable", directory)

    assert result.ok is True
    assert directory.exists()
    assert not any(directory.iterdir())


def test_render_doctor_text_summarizes_results():
    text = render_doctor_text([
        CheckResult("python.version", True, "Python 3.13"),
        CheckResult("port.available", False, "Port 6173 is already in use"),
    ])

    assert "HARNESS_DOCTOR" in text
    assert "ok: false" in text
    assert "python.version: ok" in text
    assert "port.available: fail - Port 6173 is already in use" in text
```

- [ ] **Step 2: Add failing CLI smoke tests**

Append to `tests/test_cli_smoke.py`:

```python
def test_harness_doctor_help_exits_successfully():
    result = run_script("harness_doctor.py", "--help")
    assert result.returncode == 0
    assert "Check whether the harness can run on this machine" in result.stdout
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_doctor.py tests/test_cli_smoke.py -v
```

Expected: FAIL because `harness.doctor` and `harness_doctor.py` do not exist.

- [ ] **Step 4: Implement doctor module**

Create `harness/doctor.py`:

```python
from __future__ import annotations

import importlib.util
import json
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str


def check_python_version() -> CheckResult:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 10)
    return CheckResult("python.version", ok, f"Python {version}")


def check_import(module_name: str, check_name: str) -> CheckResult:
    found = importlib.util.find_spec(module_name) is not None
    message = f"{module_name} importable" if found else f"{module_name} is not importable"
    return CheckResult(check_name, found, message)


def check_chromium_launch() -> CheckResult:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except PlaywrightError as exc:
        return CheckResult(
            "chromium.launch",
            False,
            f"Chromium could not launch. Run `python -m playwright install chromium`. {exc}",
        )
    return CheckResult("chromium.launch", True, "Chromium launches successfully")


def check_port_available(port: int, host: str = "127.0.0.1") -> CheckResult:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return CheckResult("port.available", False, f"Port {port} is already in use on {host}")
    return CheckResult("port.available", True, f"Port {port} is available on {host}")


def check_target_path(target: Path) -> CheckResult:
    if not target.exists():
        return CheckResult("target.index_html", False, f"Target path does not exist: {target}")
    if not target.is_dir():
        return CheckResult("target.index_html", False, f"Target path is not a directory: {target}")
    index = target / "index.html"
    if not index.exists():
        return CheckResult("target.index_html", False, f"Target does not contain index.html: {target}")
    return CheckResult("target.index_html", True, f"Found {index}")


def check_writable_directory(name: str, directory: Path) -> CheckResult:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".doctor-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult(name, False, f"{directory} is not writable: {exc}")
    return CheckResult(name, True, f"{directory} is writable")


def check_harness_client(path: Path = Path("harness/static/harness_client.js")) -> CheckResult:
    if path.exists() and path.is_file():
        return CheckResult("client.exists", True, f"Found {path}")
    return CheckResult("client.exists", False, f"Missing harness client: {path}")


def run_doctor_checks(target: Path, port: int, host: str = "127.0.0.1") -> list[CheckResult]:
    return [
        check_python_version(),
        check_import("pytest", "pytest.import"),
        check_import("playwright", "playwright.import"),
        check_chromium_launch(),
        check_port_available(port, host),
        check_target_path(target),
        check_writable_directory("traces.writable", Path("traces")),
        check_writable_directory("reports.writable", Path("reports")),
        check_writable_directory("runs.writable", Path("runs")),
        check_harness_client(),
    ]


def render_doctor_text(results: Iterable[CheckResult]) -> str:
    items = list(results)
    ok = all(item.ok for item in items)
    lines = ["HARNESS_DOCTOR", f"ok: {str(ok).lower()}", "checks:"]
    for item in items:
        status = "ok" if item.ok else f"fail - {item.message}"
        lines.append(f"  {item.name}: {status}")
    return "\n".join(lines) + "\n"


def render_doctor_json(results: Iterable[CheckResult]) -> str:
    items = list(results)
    payload = {
        "ok": all(item.ok for item in items),
        "checks": [asdict(item) for item in items],
    }
    return json.dumps(payload, indent=2)
```

- [ ] **Step 5: Wire doctor CLI**

Modify `harness/cli.py`:

```python
def build_doctor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether the harness can run on this machine")
    parser.add_argument("--target", type=Path, required=True, help="Target app directory to verify")
    parser.add_argument("--port", type=int, default=6173, help="Port to check")
    parser.add_argument("--host", default="127.0.0.1", help="Host to check")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def doctor_main() -> int:
    from harness.doctor import render_doctor_json, render_doctor_text, run_doctor_checks

    parser = build_doctor_parser()
    args = parser.parse_args()
    results = run_doctor_checks(args.target, args.port, args.host)
    print(render_doctor_json(results) if args.json else render_doctor_text(results), end="")
    return 0 if all(result.ok for result in results) else 1
```

Create `harness_doctor.py`:

```python
from harness.cli import doctor_main


if __name__ == "__main__":
    raise SystemExit(doctor_main())
```

- [ ] **Step 6: Run doctor tests**

Run:

```bash
python -m pytest tests/test_doctor.py tests/test_cli_smoke.py -v
```

Expected: PASS.

- [ ] **Step 7: Run doctor manually**

Run:

```bash
python harness_doctor.py --target examples/targets/simple --port 6173
python harness_doctor.py --target examples/targets/simple --port 6173 --json
```

Expected: both commands report `ok: true` when port `6173` is free.

- [ ] **Step 8: Commit**

```bash
git add harness/doctor.py harness/cli.py harness_doctor.py tests/test_doctor.py tests/test_cli_smoke.py
git commit -m "Add harness doctor command"
```

---

### Task 2: Trace Validation Command

**Harness engineering lesson:** A harness produces artifacts. Those artifacts need contracts, or later debugging becomes guesswork.

**Files:**
- Create: `harness/trace_validation.py`
- Create: `harness_validate_trace.py`
- Modify: `harness/cli.py`
- Create: `tests/test_trace_validation.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write failing validation tests**

Create `tests/test_trace_validation.py`:

```python
from harness.trace_validation import validate_trace


def valid_trace():
    return {
        "version": 1,
        "session": {"targetName": "simple", "proxyUrl": "http://127.0.0.1:6173"},
        "events": [],
        "snapshots": [],
        "console": [],
        "errors": [],
        "screenshots": [],
        "replay": None,
    }


def test_validate_trace_accepts_minimal_valid_trace():
    assert validate_trace(valid_trace()) == []


def test_validate_trace_reports_missing_session_field():
    trace = valid_trace()
    del trace["session"]["targetName"]

    errors = validate_trace(trace)

    assert "trace.session.targetName: missing" in errors


def test_validate_trace_reports_wrong_list_type():
    trace = valid_trace()
    trace["events"] = {}

    errors = validate_trace(trace)

    assert "trace.events: expected list, got dict" in errors


def test_validate_trace_reports_invalid_replay_type():
    trace = valid_trace()
    trace["replay"] = []

    errors = validate_trace(trace)

    assert "trace.replay: expected object or null, got list" in errors
```

- [ ] **Step 2: Add failing CLI smoke test**

Append to `tests/test_cli_smoke.py`:

```python
def test_harness_validate_trace_help_exits_successfully():
    result = run_script("harness_validate_trace.py", "--help")
    assert result.returncode == 0
    assert "Validate a harness trace JSON file" in result.stdout
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_trace_validation.py tests/test_cli_smoke.py -v
```

Expected: FAIL because validation module and root CLI do not exist.

- [ ] **Step 4: Implement trace validation**

Create `harness/trace_validation.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def require_key(obj: dict[str, Any], key: str, path: str, errors: list[str]) -> Any:
    if key not in obj:
        errors.append(f"{path}.{key}: missing")
        return None
    return obj[key]


def validate_trace(trace: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(trace, dict):
        return [f"trace: expected object, got {type_name(trace)}"]

    version = require_key(trace, "version", "trace", errors)
    if version is not None and version != 1:
        errors.append(f"trace.version: expected 1, got {version!r}")

    session = require_key(trace, "session", "trace", errors)
    if isinstance(session, dict):
        require_key(session, "targetName", "trace.session", errors)
        require_key(session, "proxyUrl", "trace.session", errors)
    elif session is not None:
        errors.append(f"trace.session: expected object, got {type_name(session)}")

    for key in ["events", "snapshots", "console", "errors", "screenshots"]:
        value = require_key(trace, key, "trace", errors)
        if value is not None and not isinstance(value, list):
            errors.append(f"trace.{key}: expected list, got {type_name(value)}")

    replay = require_key(trace, "replay", "trace", errors)
    if replay is not None and not isinstance(replay, dict):
        errors.append(f"trace.replay: expected object or null, got {type_name(replay)}")

    return errors


def load_trace(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 5: Wire validation CLI**

Modify `harness/cli.py`:

```python
def build_validate_trace_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a harness trace JSON file")
    parser.add_argument("trace", type=Path, help="Trace JSON file")
    return parser


def validate_trace_main() -> int:
    from harness.trace_validation import load_trace, validate_trace

    parser = build_validate_trace_parser()
    args = parser.parse_args()
    errors = validate_trace(load_trace(args.trace))
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Trace valid: {args.trace}")
    return 0
```

Create `harness_validate_trace.py`:

```python
from harness.cli import validate_trace_main


if __name__ == "__main__":
    raise SystemExit(validate_trace_main())
```

- [ ] **Step 6: Run validation tests**

Run:

```bash
python -m pytest tests/test_trace_validation.py tests/test_cli_smoke.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add harness/trace_validation.py harness/cli.py harness_validate_trace.py tests/test_trace_validation.py tests/test_cli_smoke.py
git commit -m "Add trace validation command"
```

---

### Task 3: Structured Run Log

**Harness engineering lesson:** If the harness fails, the harness itself must leave evidence. Run logs are traces for the harness infrastructure.

**Files:**
- Create: `harness/run_log.py`
- Modify: `harness/proxy.py`
- Modify: `harness/static/harness_client.js`
- Modify: `.gitignore`
- Create: `runs/.gitkeep`
- Create: `tests/test_run_log.py`

- [ ] **Step 1: Write failing run log tests**

Create `tests/test_run_log.py`:

```python
import json
from pathlib import Path

from harness.run_log import RunLogger, make_run_id


def test_make_run_id_is_filename_safe():
    run_id = make_run_id()
    assert ":" not in run_id
    assert "/" not in run_id
    assert "\\" not in run_id
    assert len(run_id) >= 15


def test_run_logger_writes_jsonl_events(tmp_path: Path):
    logger = RunLogger(tmp_path, run_id="run-1")

    logger.record("proxy.started", port=6173, targetName="simple")
    logger.record("trace.saved", path="traces/example.json")

    lines = (tmp_path / "run-1.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["event"] == "proxy.started"
    assert json.loads(lines[0])["port"] == 6173
    assert json.loads(lines[1])["event"] == "trace.saved"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_run_log.py -v
```

Expected: FAIL because `harness.run_log` does not exist.

- [ ] **Step 3: Implement run logger**

Create `harness/run_log.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


class RunLogger:
    def __init__(self, root: Path, run_id: str | None = None) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or make_run_id()
        self.path = self.root / f"{self.run_id}.jsonl"

    def record(self, event: str, **fields: Any) -> None:
        payload = {
            "time": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Add run-log ignore rules**

Modify `.gitignore`:

```text
runs/*
!runs/.gitkeep
```

Create `runs/.gitkeep` as an empty file.

- [ ] **Step 5: Instrument proxy run events**

Modify `harness/proxy.py`:

```python
from harness.run_log import RunLogger
```

Add `run_logger: RunLogger` and `run_id: str` to `HarnessProxyHandler`.

Record events:

```python
self.run_logger.record("client.served", path=CLIENT_ROUTE)
self.run_logger.record("html.injected", path=str(target_path.relative_to(self.target_root.resolve())))
self.run_logger.record("trace.received", eventCount=len(trace.get("events", [])), snapshotCount=len(trace.get("snapshots", [])))
self.run_logger.record("trace.saved", path=str(path))
```

In `do_POST`, before saving, attach run ID:

```python
trace.setdefault("session", {})["harnessRunId"] = self.run_id
```

In `run_proxy_server()`:

```python
run_logger = RunLogger(Path("runs"))
run_logger.record("proxy.started", port=port, host=host, targetName=target_name, targetRoot=str(target_root))
ConfiguredHarnessProxyHandler.run_logger = run_logger
ConfiguredHarnessProxyHandler.run_id = run_logger.run_id
```

- [ ] **Step 6: Pass run ID to client bootstrap**

Modify `build_injected_html()` signature:

```python
def build_injected_html(html_text: str, target_name: str, harness_run_id: str | None = None) -> str:
```

Include it in bootstrap:

```python
"harnessRunId": harness_run_id,
```

Modify `_send_file()` call:

```python
data = build_injected_html(text, self.target_name, self.run_id).encode("utf-8")
```

Modify `harness/static/harness_client.js` session object:

```javascript
harnessRunId: bootstrap.harnessRunId || null,
```

- [ ] **Step 7: Run tests**

Run:

```bash
python -m pytest tests/test_run_log.py tests/test_proxy.py -v
node --check harness/static/harness_client.js
```

Expected: PASS.

- [ ] **Step 8: Manual run-log smoke**

Run:

```bash
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

Open `http://127.0.0.1:6173`, press `Start`, click `Increment`, press `Save`, stop the server, then run:

```bash
Get-ChildItem runs
Get-Content runs\<run-id>.jsonl
```

Expected: JSONL contains `proxy.started`, `html.injected`, `client.served`, `trace.received`, and `trace.saved`.

- [ ] **Step 9: Commit**

```bash
git add harness/run_log.py harness/proxy.py harness/static/harness_client.js .gitignore runs/.gitkeep tests/test_run_log.py tests/test_proxy.py
git commit -m "Add structured harness run logs"
```

---

### Task 4: Replay And Report Run-Log Events

**Harness engineering lesson:** Observability must cover the full workflow, not just server startup. Replay and report generation are harness operations too.

**Files:**
- Modify: `harness/cli.py`
- Modify: `harness/replay.py`
- Modify: `harness/report.py`
- Modify: `tests/test_replay.py`
- Modify: `tests/test_report.py`

- [ ] **Step 1: Add replay run-log test**

Append to `tests/test_replay.py`:

```python
def test_replay_result_event_payload_is_stable():
    from harness.replay import build_replay_completed_event

    payload = build_replay_completed_event({"ok": True, "completedEvents": 3})

    assert payload == {"ok": True, "completedEvents": 3}
```

- [ ] **Step 2: Add report run-log test**

Append to `tests/test_report.py`:

```python
def test_report_generated_event_payload_is_stable():
    from harness.report import build_report_generated_event

    payload = build_report_generated_event("reports/simple-report.md")

    assert payload == {"path": "reports/simple-report.md"}
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_replay.py tests/test_report.py -v
```

Expected: FAIL because helper functions do not exist.

- [ ] **Step 4: Add replay event helper**

Modify `harness/replay.py`:

```python
def build_replay_completed_event(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(result.get("ok")),
        "completedEvents": int(result.get("completedEvents", 0)),
    }
```

- [ ] **Step 5: Add report event helper**

Modify `harness/report.py`:

```python
def build_report_generated_event(path: str) -> dict[str, str]:
    return {"path": path}
```

- [ ] **Step 6: Wire CLI run logging**

Modify `build_replay_parser()` in `harness/cli.py`:

```python
parser.add_argument("--run-log", type=Path, help="Optional JSONL run log path")
```

Modify `build_report_parser()`:

```python
parser.add_argument("--run-log", type=Path, help="Optional JSONL run log path")
```

In `replay_main()` after replay:

```python
if args.run_log:
    from harness.run_log import RunLogger
    from harness.replay import build_replay_completed_event

    logger = RunLogger(args.run_log.parent, run_id=args.run_log.stem)
    logger.record("replay.completed", **build_replay_completed_event(result))
```

In `report_main()` after writing or printing:

```python
if args.run_log:
    from harness.run_log import RunLogger
    from harness.report import build_report_generated_event

    logger = RunLogger(args.run_log.parent, run_id=args.run_log.stem)
    report_path = str(args.out) if args.out else "<stdout>"
    logger.record("report.generated", **build_report_generated_event(report_path))
```

- [ ] **Step 7: Run tests**

Run:

```bash
python -m pytest tests/test_replay.py tests/test_report.py tests/test_cli_smoke.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add harness/cli.py harness/replay.py harness/report.py tests/test_replay.py tests/test_report.py
git commit -m "Log replay and report harness events"
```

---

### Task 5: Golden Trace Regression

**Harness engineering lesson:** A harness needs its own regression fixture. Golden traces make the harness's expected behavior concrete.

**Files:**
- Create: `harness/regression.py`
- Create: `harness_regress.py`
- Modify: `harness/cli.py`
- Create: `examples/golden/simple-trace.json`
- Create: `examples/golden/simple-report.md`
- Create: `tests/test_regression.py`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write failing regression tests**

Create `tests/test_regression.py`:

```python
from harness.regression import normalize_report_markdown, compare_reports


def test_normalize_report_removes_session_line():
    report = "# Harness Debug Report\n\n- Session: abc\n- Events: 2\n"

    normalized = normalize_report_markdown(report)

    assert "- Session: <normalized>" in normalized
    assert "- Events: 2" in normalized


def test_compare_reports_returns_empty_list_for_matching_normalized_reports():
    current = "# Harness Debug Report\n\n- Session: abc\n- Events: 2\n"
    golden = "# Harness Debug Report\n\n- Session: xyz\n- Events: 2\n"

    assert compare_reports(current, golden) == []


def test_compare_reports_explains_mismatch():
    current = "# Harness Debug Report\n\n- Events: 3\n"
    golden = "# Harness Debug Report\n\n- Events: 2\n"

    errors = compare_reports(current, golden)

    assert errors
    assert "normalized report differs" in errors[0]
```

- [ ] **Step 2: Add CLI smoke test**

Append to `tests/test_cli_smoke.py`:

```python
def test_harness_regress_help_exits_successfully():
    result = run_script("harness_regress.py", "--help")
    assert result.returncode == 0
    assert "Run golden trace regression" in result.stdout
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_regression.py tests/test_cli_smoke.py -v
```

Expected: FAIL because regression module and CLI do not exist.

- [ ] **Step 4: Implement regression helpers**

Create `harness/regression.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from harness.replay import attach_replay_result, replay_trace
from harness.report import build_report_markdown
from harness.trace_validation import validate_trace


def normalize_report_markdown(markdown: str) -> str:
    normalized_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("- Session:"):
            normalized_lines.append("- Session: <normalized>")
        elif line.startswith("- Proxy URL:"):
            normalized_lines.append("- Proxy URL: <normalized>")
        else:
            normalized_lines.append(line)
    return "\n".join(normalized_lines).strip() + "\n"


def compare_reports(current: str, golden: str) -> list[str]:
    if normalize_report_markdown(current) == normalize_report_markdown(golden):
        return []
    return ["normalized report differs from golden report"]


def run_report_regression(golden_trace: Path, golden_report: Path) -> list[str]:
    trace = json.loads(golden_trace.read_text(encoding="utf-8"))
    errors = validate_trace(trace)
    if errors:
        return errors
    replay_result = replay_trace(trace)
    if not replay_result.get("ok"):
        return [f"golden replay failed: {replay_result.get('firstFailure') or replay_result.get('error')}"]
    current_report = build_report_markdown(attach_replay_result(trace, replay_result))
    return compare_reports(current_report, golden_report.read_text(encoding="utf-8"))
```

- [ ] **Step 5: Add golden fixtures**

Create `examples/golden/simple-trace.json`:

```json
{
  "version": 1,
  "session": {
    "id": "golden-simple",
    "targetName": "simple",
    "proxyUrl": "http://127.0.0.1:6173",
    "viewport": { "width": 1440, "height": 900 },
    "harnessRunId": "golden-run"
  },
  "events": [
    { "type": "click", "time": 1, "target": { "selectorHint": "#incrementBtn" } },
    { "type": "input", "time": 2, "target": { "selectorHint": "#nameInput" } },
    { "type": "click", "time": 3, "target": { "selectorHint": "#drawCanvas" } }
  ],
  "snapshots": [
    { "reason": "capture:start", "debugSnapshot": { "ok": true, "value": { "count": 0 } } },
    { "reason": "after:click", "debugSnapshot": { "ok": true, "value": { "count": 1 } } }
  ],
  "console": [],
  "errors": [],
  "screenshots": [],
  "replay": {
    "ok": true,
    "completedEvents": 3,
    "firstFailure": null,
    "console": [],
    "errors": []
  }
}
```

Create `examples/golden/simple-report.md` by running:

```bash
python report_generator.py examples/golden/simple-trace.json --out examples/golden/simple-report.md
```

- [ ] **Step 6: Wire regression CLI**

Modify `harness/cli.py`:

```python
def build_regress_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run golden trace regression")
    parser.add_argument("--golden", type=Path, required=True, help="Golden trace JSON path")
    parser.add_argument("--report", type=Path, help="Golden report Markdown path")
    return parser


def regress_main() -> int:
    from harness.regression import run_report_regression

    parser = build_regress_parser()
    args = parser.parse_args()
    golden_report = args.report or args.golden.with_name(args.golden.stem.replace("-trace", "-report") + ".md")
    errors = run_report_regression(args.golden, golden_report)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Golden regression passed: {args.golden}")
    return 0
```

Create `harness_regress.py`:

```python
from harness.cli import regress_main


if __name__ == "__main__":
    raise SystemExit(regress_main())
```

- [ ] **Step 7: Run tests and regression command**

Run:

```bash
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

In another terminal, run:

```bash
python -m pytest tests/test_regression.py tests/test_cli_smoke.py -v
python harness_regress.py --golden examples/golden/simple-trace.json
```

Expected: tests pass and regression prints `Golden regression passed` while the fixture server is running.

- [ ] **Step 8: Commit**

```bash
git add harness/regression.py harness/cli.py harness_regress.py examples/golden tests/test_regression.py tests/test_cli_smoke.py
git commit -m "Add golden trace regression"
```

---

### Task 6: Self-Observing Runbook And End-To-End Validation

**Harness engineering lesson:** The process is only real if another engineer can run it and get the same evidence.

**Files:**
- Create: `docs/runbooks/self-observing-harness.md`

- [ ] **Step 1: Create runbook**

Create `docs/runbooks/self-observing-harness.md`:

````markdown
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

```bash
python harness_regress.py --golden examples/golden/simple-trace.json
```
````

- [ ] **Step 2: Run full automated verification**

Run:

```bash
python -m pytest -v
node --check harness/static/harness_client.js
python harness_doctor.py --target examples/targets/simple --port 6173
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

In another terminal, run:

```bash
python harness_regress.py --golden examples/golden/simple-trace.json
```

Expected: pytest passes, JS syntax check passes, doctor reports success, and golden regression passes while the fixture server is running.

- [ ] **Step 3: Commit**

```bash
git add docs/runbooks/self-observing-harness.md
git commit -m "Document self-observing harness workflow"
```

---

## Self-Review Notes

- Spec coverage: Doctor is Task 1, trace validation is Task 2, run logs are Tasks 3 and 4, golden regression is Task 5, and teaching/runbook coverage is Task 6.
- Scope control: This plan does not add CDP heap snapshots, breakpoints, source rewriting, or autonomous AI control.
- Artifact model: generated files remain under ignored `traces/`, `reports/`, and `runs/`; stable fixtures live in `examples/golden/`.
- Teaching flow: each task explicitly names the harness engineering lesson it teaches.
