# Zero-Mod Debug Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `d:/harness` as a reusable zero-modification browser debug harness that can proxy a local HTML/JavaScript target, inject a recorder, save traces, replay them with Playwright, and generate an AI-readable report.

**Architecture:** Keep the public commands as root scripts for the learning workflow, but put real behavior in a focused `harness/` Python package. The browser recorder is a standalone injected JavaScript client served by the proxy. `d:/claude` is only the first realistic target; tests use a tiny fixture target inside this repo.

**Tech Stack:** Python 3, standard-library `http.server`, pytest, Playwright for Python, vanilla JavaScript injected into target pages.

---

## File Structure

- Create `requirements.txt`: Python dependencies for tests and replay.
- Create `harness_server.py`: root CLI wrapper for `python harness_server.py`.
- Create `replay_runner.py`: root CLI wrapper for `python replay_runner.py`.
- Create `report_generator.py`: root CLI wrapper for `python report_generator.py`.
- Create `harness/__init__.py`: package marker and version string.
- Create `harness/cli.py`: argument parsing and command entry points.
- Create `harness/proxy.py`: read-only static proxy, HTML injection, and trace POST endpoint.
- Create `harness/trace_store.py`: trace IDs, trace paths, JSON write/read helpers.
- Create `harness/replay.py`: Playwright replay engine.
- Create `harness/report.py`: Markdown report generator.
- Create `harness/static/harness_client.js`: injected browser recorder.
- Create `examples/targets/simple/index.html`: tiny target app used by local tests.
- Create `examples/targets/simple/app.js`: target app state, buttons, input, and canvas.
- Create `tests/test_proxy.py`: proxy and injection tests.
- Create `tests/test_trace_store.py`: trace persistence tests.
- Create `tests/test_report.py`: report generator tests.
- Create `tests/test_replay.py`: replay unit tests for action translation.

---

### Task 1: Project Skeleton And Smoke Commands

**Files:**
- Create: `requirements.txt`
- Create: `harness/__init__.py`
- Create: `harness/cli.py`
- Create: `harness_server.py`
- Create: `replay_runner.py`
- Create: `report_generator.py`
- Create: `examples/targets/simple/index.html`
- Create: `examples/targets/simple/app.js`
- Create: `tests/test_cli_smoke.py`

- [ ] **Step 1: Create dependency file**

Create `requirements.txt`:

```text
pytest==8.3.5
playwright==1.51.0
```

- [ ] **Step 2: Create a minimal fixture target**

Create `examples/targets/simple/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Harness Simple Target</title>
  <script src="app.js"></script>
</head>
<body>
  <h1>Harness Simple Target</h1>
  <button id="incrementBtn">Increment</button>
  <input id="nameInput" value="" placeholder="Name">
  <canvas id="drawCanvas" width="240" height="120"></canvas>
  <pre id="status"></pre>
</body>
</html>
```

Create `examples/targets/simple/app.js`:

```javascript
(function () {
  window.state = {
    count: 0,
    name: "",
    points: []
  };

  window.debug = {
    snapshot() {
      return {
        count: window.state.count,
        nameLength: window.state.name.length,
        pointCount: window.state.points.length
      };
    },
    actionLog() {
      return window.state.points.map((point, index) => ({
        index,
        x: point.x,
        y: point.y
      }));
    },
    errors() {
      return [];
    },
    timing() {
      return { frameMs: 0 };
    }
  };

  function renderStatus() {
    document.getElementById("status").textContent = JSON.stringify(window.debug.snapshot(), null, 2);
  }

  window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("incrementBtn").addEventListener("click", () => {
      window.state.count += 1;
      renderStatus();
    });

    document.getElementById("nameInput").addEventListener("input", (event) => {
      window.state.name = event.target.value;
      renderStatus();
    });

    document.getElementById("drawCanvas").addEventListener("pointerdown", (event) => {
      window.state.points.push({ x: event.offsetX, y: event.offsetY });
      renderStatus();
    });

    renderStatus();
  });
})();
```

- [ ] **Step 3: Write a failing CLI smoke test**

Create `tests/test_cli_smoke.py`:

```python
import subprocess
import sys


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, script_name, *args],
        cwd=".",
        text=True,
        capture_output=True,
        check=False,
    )


def test_harness_server_help_exits_successfully():
    result = run_script("harness_server.py", "--help")
    assert result.returncode == 0
    assert "Zero-mod browser debug harness server" in result.stdout


def test_replay_runner_help_exits_successfully():
    result = run_script("replay_runner.py", "--help")
    assert result.returncode == 0
    assert "Replay a captured harness trace" in result.stdout


def test_report_generator_help_exits_successfully():
    result = run_script("report_generator.py", "--help")
    assert result.returncode == 0
    assert "Generate a Markdown report from a harness trace" in result.stdout
```

- [ ] **Step 4: Run the smoke test and verify it fails**

Run:

```bash
pytest tests/test_cli_smoke.py -v
```

Expected: FAIL because the root scripts and package do not exist yet.

- [ ] **Step 5: Create package and CLI wrappers**

Create `harness/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `harness/cli.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path


def build_server_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zero-mod browser debug harness server")
    parser.add_argument("--target", type=Path, required=True, help="Target app directory to serve read-only")
    parser.add_argument("--target-name", default="target", help="Human-readable target name")
    parser.add_argument("--port", type=int, default=6173, help="Proxy server port")
    parser.add_argument("--host", default="127.0.0.1", help="Proxy server host")
    return parser


def build_replay_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay a captured harness trace")
    parser.add_argument("trace", type=Path, help="Trace JSON file")
    parser.add_argument("--headed", action="store_true", help="Run Chromium in headed mode")
    return parser


def build_report_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Markdown report from a harness trace")
    parser.add_argument("trace", type=Path, help="Trace JSON file")
    parser.add_argument("--out", type=Path, help="Output Markdown path")
    return parser


def server_main() -> int:
    parser = build_server_parser()
    args = parser.parse_args()
    print(f"Server entry parsed target={args.target} target_name={args.target_name} host={args.host} port={args.port}")
    return 0


def replay_main() -> int:
    parser = build_replay_parser()
    args = parser.parse_args()
    print(f"Replay entry parsed trace={args.trace} headed={args.headed}")
    return 0


def report_main() -> int:
    parser = build_report_parser()
    args = parser.parse_args()
    print(f"Report entry parsed trace={args.trace} out={args.out}")
    return 0
```

Create `harness_server.py`:

```python
from harness.cli import server_main


if __name__ == "__main__":
    raise SystemExit(server_main())
```

Create `replay_runner.py`:

```python
from harness.cli import replay_main


if __name__ == "__main__":
    raise SystemExit(replay_main())
```

Create `report_generator.py`:

```python
from harness.cli import report_main


if __name__ == "__main__":
    raise SystemExit(report_main())
```

- [ ] **Step 6: Run the smoke test and verify it passes**

Run:

```bash
pytest tests/test_cli_smoke.py -v
```

Expected: PASS for all 3 tests.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt harness harness_server.py replay_runner.py report_generator.py examples tests/test_cli_smoke.py
git commit -m "Add harness project skeleton"
```

---

### Task 2: Read-Only Proxy And HTML Injection

**Files:**
- Create: `harness/static/harness_client.js`
- Create: `harness/proxy.py`
- Modify: `harness/cli.py`
- Create: `tests/test_proxy.py`

- [ ] **Step 1: Write failing proxy tests**

Create `tests/test_proxy.py`:

```python
from pathlib import Path

from harness.proxy import build_injected_html, resolve_target_path


def test_resolve_target_path_allows_files_under_target(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()
    index = target / "index.html"
    index.write_text("<html></html>", encoding="utf-8")

    resolved = resolve_target_path(target, "/index.html")

    assert resolved == index.resolve()


def test_resolve_target_path_blocks_directory_escape(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()

    try:
        resolve_target_path(target, "/../secret.txt")
    except PermissionError as exc:
        assert "outside target root" in str(exc)
    else:
        raise AssertionError("Expected PermissionError")


def test_build_injected_html_inserts_client_before_body_close():
    html = "<!doctype html><html><body><h1>Target</h1></body></html>"

    injected = build_injected_html(html, target_name="demo")

    assert "<script" in injected
    assert "/__harness__/client.js" in injected
    assert "window.__HARNESS_BOOTSTRAP__" in injected
    assert injected.index("/__harness__/client.js") < injected.index("</body>")
```

- [ ] **Step 2: Run proxy tests and verify they fail**

Run:

```bash
pytest tests/test_proxy.py -v
```

Expected: FAIL because `harness.proxy` does not exist.

- [ ] **Step 3: Add minimal injected client placeholder**

Create `harness/static/harness_client.js`:

```javascript
(function () {
  if (window.__ZERO_MOD_HARNESS__) {
    return;
  }

  window.__ZERO_MOD_HARNESS__ = {
    version: 1,
    events: [],
    snapshots: [],
    console: [],
    errors: []
  };

  const panel = document.createElement("div");
  panel.id = "__zero_mod_harness_panel";
  panel.textContent = "HARNESS idle";
  panel.style.position = "fixed";
  panel.style.top = "8px";
  panel.style.right = "8px";
  panel.style.zIndex = "2147483647";
  panel.style.padding = "6px 8px";
  panel.style.background = "#111";
  panel.style.color = "#fff";
  panel.style.font = "12px system-ui, sans-serif";
  panel.style.border = "1px solid #555";
  panel.style.borderRadius = "4px";

  window.addEventListener("DOMContentLoaded", () => {
    document.body.appendChild(panel);
  });
})();
```

- [ ] **Step 4: Implement proxy helpers**

Create `harness/proxy.py`:

```python
from __future__ import annotations

import html
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


CLIENT_ROUTE = "/__harness__/client.js"


def resolve_target_path(target_root: Path, request_path: str) -> Path:
    root = target_root.resolve()
    parsed_path = unquote(urlparse(request_path).path)
    relative = parsed_path.lstrip("/") or "index.html"
    candidate = (root / relative).resolve()
    if root != candidate and root not in candidate.parents:
        raise PermissionError(f"Request path resolves outside target root: {request_path}")
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def build_injected_html(html_text: str, target_name: str) -> str:
    bootstrap = {
        "version": 1,
        "targetName": target_name,
    }
    script = (
        "<script>"
        f"window.__HARNESS_BOOTSTRAP__ = {json.dumps(bootstrap)};"
        "</script>"
        f'<script src="{CLIENT_ROUTE}"></script>'
    )
    lower = html_text.lower()
    body_index = lower.rfind("</body>")
    if body_index == -1:
        return html_text + script
    return html_text[:body_index] + script + html_text[body_index:]


class HarnessProxyHandler(BaseHTTPRequestHandler):
    target_root: Path
    target_name: str
    client_path: Path

    def do_GET(self) -> None:
        if urlparse(self.path).path == CLIENT_ROUTE:
            self._send_file(self.client_path, "application/javascript", inject=False)
            return

        try:
            target_path = resolve_target_path(self.target_root, self.path)
        except PermissionError as exc:
            self.send_error(403, str(exc))
            return

        if not target_path.exists() or not target_path.is_file():
            self.send_error(404, f"Not found: {html.escape(self.path)}")
            return

        content_type = mimetypes.guess_type(target_path.name)[0] or "application/octet-stream"
        self._send_file(target_path, content_type, inject=content_type.startswith("text/html"))

    def _send_file(self, path: Path, content_type: str, inject: bool) -> None:
        data = path.read_bytes()
        if inject:
            text = data.decode("utf-8")
            data = build_injected_html(text, self.target_name).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_proxy_server(target_root: Path, target_name: str, host: str, port: int) -> None:
    client_path = Path(__file__).parent / "static" / "harness_client.js"

    class ConfiguredHarnessProxyHandler(HarnessProxyHandler):
        pass

    ConfiguredHarnessProxyHandler.target_root = target_root
    ConfiguredHarnessProxyHandler.target_name = target_name
    ConfiguredHarnessProxyHandler.client_path = client_path
    server = ThreadingHTTPServer((host, port), ConfiguredHarnessProxyHandler)
    print(f"Serving {target_root} as {target_name} at http://{host}:{port}")
    server.serve_forever()
```

- [ ] **Step 5: Wire server CLI to proxy**

Modify `harness/cli.py` so `server_main()` becomes:

```python
def server_main() -> int:
    from harness.proxy import run_proxy_server

    parser = build_server_parser()
    args = parser.parse_args()
    run_proxy_server(args.target, args.target_name, args.host, args.port)
    return 0
```

- [ ] **Step 6: Run proxy tests**

Run:

```bash
pytest tests/test_proxy.py -v
```

Expected: PASS.

- [ ] **Step 7: Manual smoke check against fixture target**

Run:

```bash
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

Open `http://127.0.0.1:6173` in a browser.

Expected: The simple target page appears and a small `HARNESS idle` panel appears in the upper-right corner.

- [ ] **Step 8: Commit**

```bash
git add harness/static/harness_client.js harness/proxy.py harness/cli.py tests/test_proxy.py
git commit -m "Add proxy server and script injection"
```

---

### Task 3: Trace Store And Capture Save Endpoint

**Files:**
- Create: `harness/trace_store.py`
- Modify: `harness/proxy.py`
- Create: `tests/test_trace_store.py`

- [ ] **Step 1: Write failing trace store tests**

Create `tests/test_trace_store.py`:

```python
import json
from pathlib import Path

from harness.trace_store import TraceStore, make_trace_id


def test_make_trace_id_is_filename_safe():
    trace_id = make_trace_id()
    assert ":" not in trace_id
    assert "/" not in trace_id
    assert "\\" not in trace_id
    assert len(trace_id) >= 15


def test_trace_store_writes_json(tmp_path: Path):
    store = TraceStore(tmp_path)
    trace = {"version": 1, "events": [{"type": "click"}]}

    path = store.write_trace(trace, trace_id="example-trace")

    assert path == tmp_path / "example-trace.json"
    assert json.loads(path.read_text(encoding="utf-8")) == trace
```

- [ ] **Step 2: Run trace store tests and verify they fail**

Run:

```bash
pytest tests/test_trace_store.py -v
```

Expected: FAIL because `harness.trace_store` does not exist.

- [ ] **Step 3: Implement trace store**

Create `harness/trace_store.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def make_trace_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


class TraceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_trace(self, trace: dict[str, Any], trace_id: str | None = None) -> Path:
        safe_id = trace_id or make_trace_id()
        path = self.root / f"{safe_id}.json"
        path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def read_trace(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Add POST `/__harness__/trace` to proxy**

Modify `harness/proxy.py`:

```python
from harness.trace_store import TraceStore
```

Add to `HarnessProxyHandler`:

```python
trace_store: TraceStore

def do_POST(self) -> None:
    if urlparse(self.path).path != "/__harness__/trace":
        self.send_error(404, f"Not found: {html.escape(self.path)}")
        return

    length = int(self.headers.get("Content-Length", "0"))
    raw_body = self.rfile.read(length)
    try:
        trace = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        self.send_error(400, f"Invalid JSON: {exc}")
        return

    path = self.trace_store.write_trace(trace)
    response = json.dumps({"ok": True, "path": str(path)}).encode("utf-8")
    self.send_response(200)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(response)))
    self.end_headers()
    self.wfile.write(response)
```

Modify `run_proxy_server()` before assigning handler fields:

```python
trace_store = TraceStore(Path("traces"))
ConfiguredHarnessProxyHandler.trace_store = trace_store
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/test_trace_store.py tests/test_proxy.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add harness/trace_store.py harness/proxy.py tests/test_trace_store.py
git commit -m "Add trace storage endpoint"
```

---

### Task 4: Browser Event Capture Client

**Files:**
- Modify: `harness/static/harness_client.js`

- [ ] **Step 1: Replace client placeholder with capture UI and event buffers**

Modify `harness/static/harness_client.js`:

```javascript
(function () {
  if (window.__ZERO_MOD_HARNESS__) {
    return;
  }

  const bootstrap = window.__HARNESS_BOOTSTRAP__ || { version: 1, targetName: "target" };
  const trace = {
    version: 1,
    session: {
      id: new Date().toISOString().replace(/[:.]/g, "-"),
      targetName: bootstrap.targetName,
      targetRoot: null,
      proxyUrl: window.location.origin,
      url: window.location.href,
      viewport: { width: window.innerWidth, height: window.innerHeight },
      controller: "user",
      mode: "capture",
      userAgent: navigator.userAgent
    },
    events: [],
    snapshots: [],
    console: [],
    errors: [],
    screenshots: [],
    replay: null
  };

  let captureActive = false;
  let lastPointerMoveAt = 0;

  function now() {
    return Math.round(performance.now() * 100) / 100;
  }

  function selectorHint(target) {
    if (!target || target === window || target === document) {
      return "";
    }
    if (target.id) {
      return "#" + CSS.escape(target.id);
    }
    if (target.getAttribute && target.getAttribute("data-testid")) {
      return '[data-testid="' + target.getAttribute("data-testid") + '"]';
    }
    return target.tagName ? target.tagName.toLowerCase() : "";
  }

  function targetMeta(target) {
    return {
      tag: target && target.tagName ? target.tagName.toLowerCase() : "",
      id: target && target.id ? target.id : "",
      classes: target && target.classList ? Array.from(target.classList).slice(0, 6) : [],
      selectorHint: selectorHint(target)
    };
  }

  function recordEvent(event, extra) {
    if (!captureActive) {
      return;
    }
    trace.events.push(Object.assign({
      type: event.type,
      time: now(),
      target: targetMeta(event.target)
    }, extra || {}));
    captureSnapshot("after:" + event.type);
    updatePanel();
  }

  function summarizeValue(value) {
    if (value === null) {
      return null;
    }
    const valueType = typeof value;
    if (valueType === "string") {
      return { type: "string", length: value.length, sample: value.slice(0, 80) };
    }
    if (valueType === "number" || valueType === "boolean") {
      return value;
    }
    if (Array.isArray(value)) {
      return { type: "array", length: value.length, sample: value.slice(0, 5) };
    }
    if (valueType === "object") {
      return {
        type: "object",
        constructor: value.constructor ? value.constructor.name : "Object",
        keys: Object.keys(value).slice(0, 30)
      };
    }
    return { type: valueType };
  }

  function safeCall(fn) {
    try {
      return { ok: true, value: fn() };
    } catch (error) {
      return { ok: false, error: String(error && error.message ? error.message : error) };
    }
  }

  function captureSnapshot(reason) {
    if (!captureActive) {
      return;
    }
    const snapshot = {
      time: now(),
      reason,
      url: window.location.href,
      debugSnapshot: null,
      debugActionLog: null,
      debugErrors: null,
      debugTiming: null,
      stateSummary: null
    };

    if (window.debug && typeof window.debug.snapshot === "function") {
      snapshot.debugSnapshot = safeCall(() => window.debug.snapshot());
    }
    if (window.debug && typeof window.debug.actionLog === "function") {
      snapshot.debugActionLog = safeCall(() => window.debug.actionLog());
    }
    if (window.debug && typeof window.debug.errors === "function") {
      snapshot.debugErrors = safeCall(() => window.debug.errors());
    }
    if (window.debug && typeof window.debug.timing === "function") {
      snapshot.debugTiming = safeCall(() => window.debug.timing());
    }
    if ("state" in window) {
      snapshot.stateSummary = safeCall(() => summarizeValue(window.state));
    }

    trace.snapshots.push(snapshot);
  }

  function startCapture() {
    captureActive = true;
    captureSnapshot("capture:start");
    updatePanel();
  }

  function stopCapture() {
    captureSnapshot("capture:stop");
    captureActive = false;
    updatePanel();
  }

  async function saveTrace() {
    captureSnapshot("capture:save");
    const response = await fetch("/__harness__/trace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(trace)
    });
    const result = await response.json();
    panelStatus.textContent = result.ok ? "saved " + result.path : "save failed";
  }

  const originalConsole = {};
  ["log", "info", "warn", "error", "debug"].forEach((level) => {
    originalConsole[level] = console[level].bind(console);
    console[level] = function () {
      trace.console.push({
        time: now(),
        level,
        args: Array.from(arguments).map((value) => summarizeValue(value))
      });
      originalConsole[level].apply(console, arguments);
    };
  });

  window.addEventListener("error", (event) => {
    trace.errors.push({
      time: now(),
      type: "error",
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    trace.errors.push({
      time: now(),
      type: "unhandledrejection",
      reason: String(event.reason)
    });
  });

  document.addEventListener("pointerdown", (event) => {
    recordEvent(event, { pointer: { x: event.clientX, y: event.clientY, button: event.button, buttons: event.buttons } });
  }, true);

  document.addEventListener("pointermove", (event) => {
    const eventTime = now();
    if (eventTime - lastPointerMoveAt < 50) {
      return;
    }
    lastPointerMoveAt = eventTime;
    recordEvent(event, { pointer: { x: event.clientX, y: event.clientY, button: event.button, buttons: event.buttons } });
  }, true);

  document.addEventListener("pointerup", (event) => {
    recordEvent(event, { pointer: { x: event.clientX, y: event.clientY, button: event.button, buttons: event.buttons } });
  }, true);

  document.addEventListener("click", (event) => {
    recordEvent(event, { pointer: { x: event.clientX, y: event.clientY, button: event.button, buttons: event.buttons } });
  }, true);

  document.addEventListener("keydown", (event) => {
    recordEvent(event, { key: { key: event.key.length === 1 ? "character" : event.key, code: event.code, ctrlKey: event.ctrlKey, shiftKey: event.shiftKey, altKey: event.altKey } });
  }, true);

  document.addEventListener("keyup", (event) => {
    recordEvent(event, { key: { key: event.key.length === 1 ? "character" : event.key, code: event.code, ctrlKey: event.ctrlKey, shiftKey: event.shiftKey, altKey: event.altKey } });
  }, true);

  document.addEventListener("input", (event) => {
    const target = event.target;
    recordEvent(event, { form: { valueLength: target && "value" in target ? String(target.value).length : 0 } });
  }, true);

  document.addEventListener("change", (event) => {
    const target = event.target;
    recordEvent(event, { form: { checked: target && "checked" in target ? Boolean(target.checked) : null, selectedIndex: target && "selectedIndex" in target ? target.selectedIndex : null } });
  }, true);

  document.addEventListener("wheel", (event) => {
    recordEvent(event, { wheel: { deltaX: event.deltaX, deltaY: event.deltaY, deltaMode: event.deltaMode } });
  }, true);

  const panel = document.createElement("div");
  panel.id = "__zero_mod_harness_panel";
  panel.style.position = "fixed";
  panel.style.top = "8px";
  panel.style.right = "8px";
  panel.style.zIndex = "2147483647";
  panel.style.padding = "8px";
  panel.style.background = "#111";
  panel.style.color = "#fff";
  panel.style.font = "12px system-ui, sans-serif";
  panel.style.border = "1px solid #555";
  panel.style.borderRadius = "4px";
  panel.style.display = "flex";
  panel.style.gap = "6px";
  panel.style.alignItems = "center";

  const panelStatus = document.createElement("span");
  const startButton = document.createElement("button");
  const stopButton = document.createElement("button");
  const saveButton = document.createElement("button");
  startButton.textContent = "Start";
  stopButton.textContent = "Stop";
  saveButton.textContent = "Save";
  startButton.addEventListener("click", startCapture);
  stopButton.addEventListener("click", stopCapture);
  saveButton.addEventListener("click", saveTrace);
  panel.append(panelStatus, startButton, stopButton, saveButton);

  function updatePanel() {
    panelStatus.textContent = "HARNESS " + (captureActive ? "recording" : "idle") + " e:" + trace.events.length + " s:" + trace.snapshots.length;
  }

  window.__ZERO_MOD_HARNESS__ = {
    version: 1,
    trace,
    startCapture,
    stopCapture,
    saveTrace,
    captureSnapshot
  };

  window.addEventListener("DOMContentLoaded", () => {
    document.body.appendChild(panel);
    updatePanel();
  });
})();
```

- [ ] **Step 2: Run manual capture against simple target**

Run:

```bash
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

Open `http://127.0.0.1:6173`, press `Start`, click `Increment`, type into the input, click the canvas, press `Save`.

Expected: a JSON file appears under `traces/` with non-empty `events`, `snapshots`, and `session.targetName` equal to `simple`.

- [ ] **Step 3: Commit**

```bash
git add harness/static/harness_client.js traces/.gitkeep
git commit -m "Add browser event capture client"
```

If `traces/.gitkeep` does not exist, create an empty file there and do not commit generated trace JSON.

---

### Task 5: Replay Action Translation

**Files:**
- Create: `harness/replay.py`
- Modify: `harness/cli.py`
- Create: `tests/test_replay.py`

- [ ] **Step 1: Write failing replay translation tests**

Create `tests/test_replay.py`:

```python
from harness.replay import replayable_events


def test_replayable_events_keeps_user_input_events():
    trace = {
        "events": [
            {"type": "pointerdown", "time": 1},
            {"type": "pointermove", "time": 2},
            {"type": "pointerup", "time": 3},
            {"type": "click", "time": 4},
            {"type": "keydown", "time": 5},
            {"type": "keyup", "time": 6},
            {"type": "wheel", "time": 7},
            {"type": "input", "time": 8}
        ]
    }

    assert [event["type"] for event in replayable_events(trace)] == [
        "pointerdown",
        "pointermove",
        "pointerup",
        "click",
        "keydown",
        "keyup",
        "wheel",
        "input",
    ]


def test_replayable_events_drops_unknown_events():
    trace = {"events": [{"type": "custom"}, {"type": "click"}]}

    assert [event["type"] for event in replayable_events(trace)] == ["click"]
```

- [ ] **Step 2: Run replay tests and verify they fail**

Run:

```bash
pytest tests/test_replay.py -v
```

Expected: FAIL because `harness.replay` does not exist.

- [ ] **Step 3: Implement replay engine**

Create `harness/replay.py`:

```python
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright


REPLAYABLE_TYPES = {
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


def replayable_events(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [event for event in trace.get("events", []) if event.get("type") in REPLAYABLE_TYPES]


async def replay_trace_async(trace: dict[str, Any], headed: bool = False) -> dict[str, Any]:
    session = trace.get("session", {})
    proxy_url = session.get("proxyUrl")
    viewport = session.get("viewport") or {"width": 1440, "height": 900}
    if not proxy_url:
        return {"ok": False, "error": "trace.session.proxyUrl is required"}

    replay_console: list[dict[str, Any]] = []
    replay_errors: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=not headed)
        page = await browser.new_page(viewport=viewport)
        page.on("console", lambda msg: replay_console.append({"type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda exc: replay_errors.append({"message": str(exc)}))
        await page.goto(proxy_url)

        completed = 0
        first_failure = None
        for index, event in enumerate(replayable_events(trace)):
            try:
                await apply_event(page, event)
                completed += 1
            except Exception as exc:
                first_failure = {
                    "eventIndex": index,
                    "eventType": event.get("type"),
                    "error": str(exc),
                }
                break

        await browser.close()

    return {
        "ok": first_failure is None,
        "completedEvents": completed,
        "firstFailure": first_failure,
        "console": replay_console,
        "errors": replay_errors,
    }


async def apply_event(page: Any, event: dict[str, Any]) -> None:
    event_type = event.get("type")
    pointer = event.get("pointer") or {}
    key = event.get("key") or {}
    wheel = event.get("wheel") or {}

    if event_type in {"pointerdown", "pointermove", "pointerup", "click"}:
        x = pointer.get("x", 0)
        y = pointer.get("y", 0)
        if event_type == "pointermove":
            await page.mouse.move(x, y)
        elif event_type == "pointerdown":
            await page.mouse.move(x, y)
            await page.mouse.down(button="left")
        elif event_type == "pointerup":
            await page.mouse.move(x, y)
            await page.mouse.up(button="left")
        else:
            await page.mouse.click(x, y)
        return

    if event_type in {"keydown", "keyup"}:
        code = key.get("code") or key.get("key")
        if code and code != "character":
            if event_type == "keydown":
                await page.keyboard.down(code)
            else:
                await page.keyboard.up(code)
        return

    if event_type == "wheel":
        await page.mouse.wheel(wheel.get("deltaX", 0), wheel.get("deltaY", 0))
        return

    if event_type in {"input", "change"}:
        selector = (event.get("target") or {}).get("selectorHint")
        if selector:
            await page.locator(selector).dispatch_event(event_type)


def replay_trace(trace: dict[str, Any], headed: bool = False) -> dict[str, Any]:
    return asyncio.run(replay_trace_async(trace, headed=headed))
```

- [ ] **Step 4: Wire replay CLI**

Modify `harness/cli.py` so `replay_main()` becomes:

```python
def replay_main() -> int:
    import json
    from harness.replay import replay_trace

    parser = build_replay_parser()
    args = parser.parse_args()
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    result = replay_trace(trace, headed=args.headed)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1
```

- [ ] **Step 5: Run replay tests**

Run:

```bash
pytest tests/test_replay.py -v
```

Expected: PASS.

- [ ] **Step 6: Manual replay check**

Run the proxy server, capture a simple trace, then in another terminal run:

```bash
python replay_runner.py traces/<trace-file>.json --headed
```

Expected: Chromium replays the basic pointer and keyboard events and the CLI prints a JSON result with `completedEvents` greater than 0.

- [ ] **Step 7: Commit**

```bash
git add harness/replay.py harness/cli.py tests/test_replay.py
git commit -m "Add Playwright trace replay"
```

---

### Task 6: Markdown Report Generator

**Files:**
- Create: `harness/report.py`
- Modify: `harness/cli.py`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write failing report tests**

Create `tests/test_report.py`:

```python
from harness.report import build_report_markdown


def test_build_report_markdown_includes_high_signal_sections():
    trace = {
        "version": 1,
        "session": {"id": "abc", "targetName": "simple", "proxyUrl": "http://127.0.0.1:6173"},
        "events": [{"type": "click", "target": {"selectorHint": "#incrementBtn"}}],
        "snapshots": [{"reason": "after:click", "debugSnapshot": {"ok": True, "value": {"count": 1}}}],
        "console": [{"level": "warn", "args": [{"type": "string", "sample": "careful"}]}],
        "errors": [{"type": "error", "message": "boom"}],
        "replay": {"ok": False, "firstFailure": {"eventIndex": 0, "error": "miss"}}
    }

    markdown = build_report_markdown(trace)

    assert "# Harness Debug Report" in markdown
    assert "simple" in markdown
    assert "Events: 1" in markdown
    assert "boom" in markdown
    assert "first divergence" in markdown.lower()
```

- [ ] **Step 2: Run report tests and verify they fail**

Run:

```bash
pytest tests/test_report.py -v
```

Expected: FAIL because `harness.report` does not exist.

- [ ] **Step 3: Implement report builder**

Create `harness/report.py`:

```python
from __future__ import annotations

from typing import Any


def build_report_markdown(trace: dict[str, Any]) -> str:
    session = trace.get("session", {})
    events = trace.get("events", [])
    snapshots = trace.get("snapshots", [])
    console = trace.get("console", [])
    errors = trace.get("errors", [])
    replay = trace.get("replay")

    lines = [
        "# Harness Debug Report",
        "",
        "## Summary",
        "",
        f"- Target: {session.get('targetName', 'unknown')}",
        f"- Session: {session.get('id', 'unknown')}",
        f"- Proxy URL: {session.get('proxyUrl', 'unknown')}",
        f"- Events: {len(events)}",
        f"- Snapshots: {len(snapshots)}",
        f"- Console entries: {len(console)}",
        f"- Errors: {len(errors)}",
        "",
        "## Operation Timeline",
        "",
    ]

    for index, event in enumerate(events[:50]):
        target = event.get("target") or {}
        lines.append(f"{index + 1}. `{event.get('type')}` on `{target.get('selectorHint', '')}` at `{event.get('time', '')}`")

    if not events:
        lines.append("No user events were captured.")

    lines.extend(["", "## Errors", ""])
    if errors:
        for error in errors[:20]:
            lines.append(f"- `{error.get('type', 'error')}` {error.get('message') or error.get('reason')}")
    else:
        lines.append("No runtime errors were captured.")

    lines.extend(["", "## Console Warnings And Errors", ""])
    console_findings = [entry for entry in console if entry.get("level") in {"warn", "error"}]
    if console_findings:
        for entry in console_findings[:20]:
            lines.append(f"- `{entry.get('level')}` {entry.get('args')}")
    else:
        lines.append("No console warnings or errors were captured.")

    lines.extend(["", "## Replay", ""])
    if replay is None:
        lines.append("Replay has not been run for this trace.")
    elif replay.get("ok"):
        lines.append(f"Replay passed after `{replay.get('completedEvents', 0)}` event(s).")
    else:
        lines.append("Replay failed; first divergence is listed below.")
        lines.append("")
        lines.append("```json")
        lines.append(str(replay.get("firstFailure")))
        lines.append("```")

    lines.extend(["", "## Snapshot Evidence", ""])
    for snapshot in snapshots[:20]:
        lines.append(f"- `{snapshot.get('reason')}` state summary: `{snapshot.get('stateSummary')}` debug snapshot: `{snapshot.get('debugSnapshot')}`")

    if not snapshots:
        lines.append("No snapshots were captured.")

    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Wire report CLI**

Modify `harness/cli.py` so `report_main()` becomes:

```python
def report_main() -> int:
    import json
    from harness.report import build_report_markdown

    parser = build_report_parser()
    args = parser.parse_args()
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    markdown = build_report_markdown(trace)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    return 0
```

- [ ] **Step 5: Run report tests**

Run:

```bash
pytest tests/test_report.py -v
```

Expected: PASS.

- [ ] **Step 6: Manual report check**

Run:

```bash
python report_generator.py traces/<trace-file>.json --out reports/simple-report.md
```

Expected: `reports/simple-report.md` exists and includes Summary, Operation Timeline, Errors, Console Warnings And Errors, Replay, and Snapshot Evidence.

- [ ] **Step 7: Commit**

```bash
git add harness/report.py harness/cli.py tests/test_report.py reports/.gitkeep
git commit -m "Add Markdown trace reports"
```

If `reports/.gitkeep` does not exist, create an empty file there and do not commit generated report Markdown unless it is a curated example.

---

### Task 7: End-To-End Harness Validation Against Reference Target

**Files:**
- Modify: `docs/superpowers/plans/2026-04-30-zero-mod-debug-harness.md`
- Optional create: `docs/runbooks/first-capture.md`

- [ ] **Step 1: Install dependencies**

Run:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Expected: pytest and Playwright install successfully, and Chromium is available.

- [ ] **Step 2: Run all automated tests**

Run:

```bash
pytest -v
```

Expected: PASS for all tests.

- [ ] **Step 3: Run fixture target capture**

Run:

```bash
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

In the browser:

1. Open `http://127.0.0.1:6173`.
2. Press `Start`.
3. Click `Increment`.
4. Type a short value into the input.
5. Click the canvas.
6. Press `Save`.

Expected: a trace file appears under `traces/`.

- [ ] **Step 4: Replay fixture trace**

Run:

```bash
python replay_runner.py traces/<trace-file>.json --headed
```

Expected: the replay command prints JSON with `completedEvents` greater than 0. If replay cannot reproduce a browser behavior, the JSON includes `firstFailure` with an event index and error.

- [ ] **Step 5: Generate fixture report**

Run:

```bash
python report_generator.py traces/<trace-file>.json --out reports/simple-report.md
```

Expected: the Markdown report contains the event count, snapshot count, and any replay result.

- [ ] **Step 6: Run reference target capture without modifying it**

Run:

```bash
git -C d:/claude status --short
python harness_server.py --target d:/claude --target-name claude-editor --port 6173
```

Open `http://127.0.0.1:6173`, press `Start`, perform one simple operation in the editor, press `Save`, then run:

```bash
git -C d:/claude status --short
```

Expected: both `git -C d:/claude status --short` outputs are identical. A trace file exists in `d:/harness/traces/`.

- [ ] **Step 7: Commit runbook if useful**

If the manual flow exposed command details worth preserving, create `docs/runbooks/first-capture.md`:

````markdown
# First Capture Runbook

## Fixture Target

```bash
python harness_server.py --target examples/targets/simple --target-name simple --port 6173
```

Open `http://127.0.0.1:6173`, press `Start`, interact with the page, and press `Save`.

## Reference Target

```bash
python harness_server.py --target d:/claude --target-name claude-editor --port 6173
```

Check `git -C d:/claude status --short` before and after capture to verify the target remains unmodified.
````

Commit:

```bash
git add docs/runbooks/first-capture.md
git commit -m "Document first capture workflow"
```

---

## Self-Review Notes

- Spec coverage: Tasks 1-2 build the standalone project and zero-mod proxy injection. Tasks 3-4 capture trace JSON, events, console, errors, and snapshots. Task 5 implements Playwright replay. Task 6 implements Markdown reports. Task 7 validates against both a fixture and `d:/claude` without modifying the target.
- Scope check: V1 does not include raw memory scanning, AST instrumentation, autonomous AI operation, breakpoints, or heap snapshots. Those remain V2 ideas from the spec.
- Type consistency: Trace records consistently use `version`, `session`, `events`, `snapshots`, `console`, `errors`, `screenshots`, and `replay`.
