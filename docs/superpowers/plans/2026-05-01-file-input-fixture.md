# File Input Fixture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make traces that use `<input type="file">` replayable by capturing selected file payloads during recording and restoring them with Playwright during replay.

**Architecture:** Build on `feature/environment-fixture` commit `36ab2e2`. Add a profile-driven `fileCapture` policy, capture selected file metadata/content in `trace.fileFixtures`, attach fixture IDs to file input events, and make replay call `locator.set_input_files()` before dispatching file input/change events. Keep it target-neutral: no special cases for `D:/claude`, `#fileInput`, or `#projectLoadInput` outside the profile.

**Tech Stack:** Injected browser JavaScript, Python replay logic, Playwright `set_input_files`, pytest, existing harness profile/bootstrap plumbing.

---

## Context For Claude

Start in:

```powershell
cd D:\harness\.worktrees\environment-fixture
git status --short --branch
git log --oneline -3
```

Expected branch:

```text
## feature/environment-fixture
36ab2e2 Add replay environment fixtures
```

Observed failure from real traces:

- `traces/20260501T045942984648Z.json`
- Capture changes from `hasMesh=false` to `hasMesh=true` after `#fileInput` change.
- Replay completes all events but stays `hasMesh=false`.
- Root cause: current replay only dispatches `input` / `change`; it never provides the selected file payload.

## File Structure

- Modify `harness/profile.py`: add file capture policy dataclasses and parser support.
- Modify `harness/cli.py`: serialize file capture settings from profile to server settings.
- Modify `harness/proxy.py`: inject `fileCapture` into `window.__HARNESS_BOOTSTRAP__`.
- Modify `harness/static/harness_client.js`: asynchronously capture file input payloads and add `trace.fileFixtures`.
- Modify `harness/replay.py`: extract file fixtures and use `locator.set_input_files()` for file input events.
- Modify `harness/trace_validation.py`: accept optional `fileFixtures` object.
- Modify `examples/targets/claude-ref/harness.profile.json`: opt into `#fileInput` and `#projectLoadInput`.
- Modify `tests/test_profile.py`: parser coverage.
- Modify `tests/test_proxy.py`: bootstrap coverage.
- Modify `tests/test_replay.py`: pure replay helper coverage.
- Modify `tests/test_trace_validation.py`: optional `fileFixtures` coverage.

## Data Model

Profile:

```json
{
  "fileCapture": {
    "mode": "allowlist",
    "selectors": ["#fileInput", "#projectLoadInput"],
    "maxFileBytes": 10000000,
    "maxFiles": 4
  }
}
```

Supported modes:

- `none`: default; do not capture file content.
- `allowlist`: capture files only from listed selectors.
- `all`: capture files from any file input up to size/count limits.

Trace:

```json
{
  "fileFixtures": {
    "file_0001": {
      "name": "example.png",
      "type": "image/png",
      "size": 12345,
      "base64": "iVBORw0KGgo..."
    }
  },
  "events": [
    {
      "type": "change",
      "target": { "selectorHint": "#fileInput" },
      "form": {
        "files": ["file_0001"]
      }
    }
  ]
}
```

If a file is skipped, record it on the event:

```json
"form": {
  "files": [],
  "fileSkips": [
    { "name": "huge.psd", "reason": "file-too-large", "size": 25000000 }
  ]
}
```

## Task 1: Profile File Capture Model

**Files:**
- Modify: `harness/profile.py`
- Test: `tests/test_profile.py`

- [ ] **Step 1: Write failing parser tests**

Append these tests to `tests/test_profile.py`:

```python
def test_parse_profile_defaults_file_capture_off():
    profile = parse_profile({"name": "x"}, Path("/fake/harness.profile.json"))

    fc = profile.file_capture
    assert fc.mode == "none"
    assert fc.selectors == ()
    assert fc.max_file_bytes == 10_000_000
    assert fc.max_files == 4


def test_parse_profile_reads_file_capture_block():
    profile = parse_profile(
        {
            "name": "x",
            "fileCapture": {
                "mode": "allowlist",
                "selectors": ["#fileInput", "#projectLoadInput"],
                "maxFileBytes": 12_345,
                "maxFiles": 2,
            },
        },
        Path("/fake/harness.profile.json"),
    )

    fc = profile.file_capture
    assert fc.mode == "allowlist"
    assert fc.selectors == ("#fileInput", "#projectLoadInput")
    assert fc.max_file_bytes == 12_345
    assert fc.max_files == 2
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_profile.py::test_parse_profile_defaults_file_capture_off tests/test_profile.py::test_parse_profile_reads_file_capture_block -v
```

Expected: fails with `AttributeError: 'Profile' object has no attribute 'file_capture'`.

- [ ] **Step 3: Implement profile parser**

In `harness/profile.py`, add:

```python
DEFAULT_MAX_FILE_BYTES = 10_000_000
DEFAULT_MAX_FILES = 4


@dataclass(frozen=True)
class FileCapture:
    mode: str = "none"
    selectors: tuple[str, ...] = ()
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_files: int = DEFAULT_MAX_FILES
```

Add `file_capture: FileCapture = FileCapture()` to `Profile`.

Add parser:

```python
def parse_file_capture(data: Any) -> FileCapture:
    raw = data if isinstance(data, dict) else {}
    mode = str(raw.get("mode", "none"))
    if mode not in {"none", "allowlist", "all"}:
        raise ValueError(f"Unsupported fileCapture mode: {mode}")
    return FileCapture(
        mode=mode,
        selectors=tuple(str(selector) for selector in raw.get("selectors", [])),
        max_file_bytes=int(raw.get("maxFileBytes", DEFAULT_MAX_FILE_BYTES)),
        max_files=int(raw.get("maxFiles", DEFAULT_MAX_FILES)),
    )
```

In `parse_profile()`, call:

```python
file_capture = parse_file_capture(data.get("fileCapture"))
```

Pass `file_capture=file_capture` to `Profile(...)`.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_profile.py -v
```

Expected: all profile tests pass.

- [ ] **Step 5: Commit**

```powershell
git add harness/profile.py tests/test_profile.py
git commit -m "Add file capture profile policy"
```

## Task 2: CLI And Proxy Bootstrap Wiring

**Files:**
- Modify: `harness/cli.py`
- Modify: `harness/proxy.py`
- Test: `tests/test_proxy.py`

- [ ] **Step 1: Write failing proxy test**

Append to `tests/test_proxy.py`:

```python
def test_build_injected_html_embeds_file_capture_in_bootstrap():
    html = "<!doctype html><html><body></body></html>"

    injected = build_injected_html(
        html,
        target_name="claude",
        file_capture={
            "mode": "allowlist",
            "selectors": ["#fileInput"],
            "maxFileBytes": 1234,
            "maxFiles": 1,
        },
    )

    assert '"fileCapture": {"mode": "allowlist", "selectors": ["#fileInput"]' in injected
    assert '"maxFileBytes": 1234' in injected
    assert '"maxFiles": 1' in injected
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_proxy.py::test_build_injected_html_embeds_file_capture_in_bootstrap -v
```

Expected: fails with `TypeError: build_injected_html() got an unexpected keyword argument 'file_capture'`.

- [ ] **Step 3: Implement bootstrap serialization**

In `harness/proxy.py`:

1. Add `file_capture: dict | None = None` to `build_injected_html(...)`.
2. Add `"fileCapture": file_capture` to the `bootstrap` dict.
3. Add `file_capture: dict | None = None` to `HarnessProxyHandler`.
4. Pass `file_capture=self.file_capture` in `_send_file()`.
5. Add `file_capture: dict | None = None` to `run_proxy_server(...)`.
6. Set `ConfiguredHarnessProxyHandler.file_capture = file_capture`.

In `harness/cli.py`, add this in `resolve_target_settings()`:

```python
file_capture_dict = None
if profile is not None:
    fc = profile.file_capture
    file_capture_dict = {
        "mode": fc.mode,
        "selectors": list(fc.selectors),
        "maxFileBytes": fc.max_file_bytes,
        "maxFiles": fc.max_files,
    }
```

Add `"file_capture": file_capture_dict` to the returned settings.

In `server_main()`, pass:

```python
file_capture=settings["file_capture"],
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_proxy.py tests/test_cli_smoke.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add harness/cli.py harness/proxy.py tests/test_proxy.py
git commit -m "Wire file capture into bootstrap"
```

## Task 3: Browser Capture For File Inputs

**Files:**
- Modify: `harness/static/harness_client.js`

- [ ] **Step 1: Add file fixture data structures**

Near existing bootstrap constants:

```javascript
  const fileCapture = bootstrap.fileCapture || {};
  let nextFileFixtureId = 1;
```

Add `fileFixtures: {},` to the top-level `trace` object.

- [ ] **Step 2: Add selector policy helpers**

Add these functions near the existing environment fixture helpers:

```javascript
  function filePolicyAllows(target) {
    const mode = fileCapture.mode || "none";
    if (mode === "none") return false;
    if (!target || target.type !== "file") return false;
    if (mode === "all") return true;
    if (mode !== "allowlist") return false;
    const selectors = Array.isArray(fileCapture.selectors) ? fileCapture.selectors : [];
    return selectors.some((selector) => {
      try { return target.matches(selector); } catch (_) { return false; }
    });
  }

  function maxFileBytes() {
    const value = Number(fileCapture.maxFileBytes);
    return Number.isFinite(value) ? value : 10000000;
  }

  function maxFiles() {
    const value = Number(fileCapture.maxFiles);
    return Number.isFinite(value) ? value : 4;
  }
```

- [ ] **Step 3: Add async file reader**

Add:

```javascript
  function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = String(reader.result || "");
        const comma = result.indexOf(",");
        resolve(comma >= 0 ? result.slice(comma + 1) : result);
      };
      reader.onerror = () => reject(reader.error || new Error("file read failed"));
      reader.readAsDataURL(file);
    });
  }

  async function captureInputFiles(target) {
    const files = Array.from(target && target.files ? target.files : []);
    const allowedCount = maxFiles();
    const fixtureIds = [];
    const skips = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (i >= allowedCount) {
        skips.push({ name: file.name, reason: "too-many-files", size: file.size });
        continue;
      }
      if (file.size > maxFileBytes()) {
        skips.push({ name: file.name, reason: "file-too-large", size: file.size });
        continue;
      }
      const id = "file_" + String(nextFileFixtureId++).padStart(4, "0");
      trace.fileFixtures[id] = {
        name: file.name,
        type: file.type || "application/octet-stream",
        size: file.size,
        base64: await readFileAsBase64(file)
      };
      fixtureIds.push(id);
    }
    return { files: fixtureIds, fileSkips: skips };
  }
```

- [ ] **Step 4: Add async record path for file input events**

Add:

```javascript
  async function recordFormEvent(event, extra) {
    const target = event.target;
    const form = Object.assign({}, extra && extra.form ? extra.form : {});
    if (filePolicyAllows(target)) {
      const captured = await captureInputFiles(target);
      form.files = captured.files;
      form.fileSkips = captured.fileSkips;
    }
    recordEvent(event, Object.assign({}, extra || {}, { form }));
  }
```

Replace the current `input` listener:

```javascript
  document.addEventListener("input", (event) => {
    const target = event.target;
    recordEvent(event, { form: { valueLength: target && "value" in target ? String(target.value).length : 0 } });
  }, true);
```

with:

```javascript
  document.addEventListener("input", (event) => {
    const target = event.target;
    recordFormEvent(event, { form: { valueLength: target && "value" in target ? String(target.value).length : 0 } });
  }, true);
```

Replace the current `change` listener:

```javascript
  document.addEventListener("change", (event) => {
    const target = event.target;
    recordEvent(event, { form: { checked: target && "checked" in target ? Boolean(target.checked) : null, selectedIndex: target && "selectedIndex" in target ? target.selectedIndex : null } });
  }, true);
```

with:

```javascript
  document.addEventListener("change", (event) => {
    const target = event.target;
    recordFormEvent(event, { form: { checked: target && "checked" in target ? Boolean(target.checked) : null, selectedIndex: target && "selectedIndex" in target ? target.selectedIndex : null } });
  }, true);
```

Do not `await` inside the DOM listener; `recordFormEvent()` handles the async work and records after the files are read.

- [ ] **Step 5: Verify JavaScript syntax**

Run:

```powershell
node --check harness/static/harness_client.js
```

Expected: exits 0.

- [ ] **Step 6: Commit**

```powershell
git add harness/static/harness_client.js
git commit -m "Capture file input fixtures"
```

## Task 4: Replay File Fixtures

**Files:**
- Modify: `harness/replay.py`
- Test: `tests/test_replay.py`

- [ ] **Step 1: Write failing replay helper tests**

Append to `tests/test_replay.py`:

```python
def test_extract_file_payloads_returns_playwright_payloads():
    trace = {
        "fileFixtures": {
            "file_0001": {
                "name": "sample.txt",
                "type": "text/plain",
                "base64": "aGVsbG8=",
            }
        }
    }
    event = {"form": {"files": ["file_0001"]}}

    from harness.replay import extract_file_payloads

    payloads = extract_file_payloads(trace, event)

    assert payloads == [{"name": "sample.txt", "mimeType": "text/plain", "buffer": b"hello"}]


class FakeLocator:
    def __init__(self):
        self.input_files = []
        self.dispatched = []

    async def set_input_files(self, payloads):
        self.input_files.append(payloads)

    async def dispatch_event(self, event_type):
        self.dispatched.append(event_type)


class FakeFilePage:
    def __init__(self):
        self.fake_locator = FakeLocator()

    def locator(self, selector):
        assert selector == "#fileInput"
        return self.fake_locator


def test_apply_file_input_event_sets_files_before_dispatch():
    from harness.replay import apply_event

    page = FakeFilePage()
    trace = {
        "fileFixtures": {
            "file_0001": {
                "name": "sample.txt",
                "type": "text/plain",
                "base64": "aGVsbG8=",
            }
        }
    }
    event = {
        "type": "change",
        "target": {"selectorHint": "#fileInput"},
        "form": {"files": ["file_0001"]},
    }

    asyncio.run(apply_event(page, event, trace))

    assert page.fake_locator.input_files == [[{"name": "sample.txt", "mimeType": "text/plain", "buffer": b"hello"}]]
    assert page.fake_locator.dispatched == ["change"]
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_replay.py::test_extract_file_payloads_returns_playwright_payloads tests/test_replay.py::test_apply_file_input_event_sets_files_before_dispatch -v
```

Expected: fails because `extract_file_payloads` does not exist and `apply_event()` does not accept the trace argument.

- [ ] **Step 3: Implement replay helpers**

In `harness/replay.py`, import base64:

```python
import base64
```

Add:

```python
def extract_file_payloads(trace: dict[str, Any], event: dict[str, Any]) -> list[dict[str, Any]]:
    fixture_map = trace.get("fileFixtures", {}) if isinstance(trace, dict) else {}
    ids = ((event.get("form") or {}).get("files") or [])
    payloads: list[dict[str, Any]] = []
    if not isinstance(fixture_map, dict):
        return payloads
    for file_id in ids:
        fixture = fixture_map.get(str(file_id))
        if not isinstance(fixture, dict):
            continue
        raw = fixture.get("base64")
        if not isinstance(raw, str):
            continue
        payloads.append({
            "name": str(fixture.get("name") or str(file_id)),
            "mimeType": str(fixture.get("type") or "application/octet-stream"),
            "buffer": base64.b64decode(raw),
        })
    return payloads
```

Change function signature:

```python
async def apply_event(page: Any, event: dict[str, Any], trace: dict[str, Any] | None = None) -> None:
```

In `replay_trace_async()`, change:

```python
await apply_event(page, event)
```

to:

```python
await apply_event(page, event, trace)
```

In the `input/change` branch, replace:

```python
if selector:
    await page.locator(selector).dispatch_event(event_type)
```

with:

```python
if selector:
    locator = page.locator(selector)
    payloads = extract_file_payloads(trace or {}, event)
    if payloads:
        await locator.set_input_files(payloads)
    await locator.dispatch_event(event_type)
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_replay.py -v
```

Expected: all replay tests pass.

- [ ] **Step 5: Commit**

```powershell
git add harness/replay.py tests/test_replay.py
git commit -m "Replay file input fixtures"
```

## Task 5: Validation And Claude Profile

**Files:**
- Modify: `harness/trace_validation.py`
- Modify: `examples/targets/claude-ref/harness.profile.json`
- Test: `tests/test_trace_validation.py`

- [ ] **Step 1: Write validation test**

Append to `tests/test_trace_validation.py`:

```python
def test_validate_trace_accepts_optional_file_fixtures_object():
    trace = valid_trace()
    trace["fileFixtures"] = {
        "file_0001": {
            "name": "sample.txt",
            "type": "text/plain",
            "size": 5,
            "base64": "aGVsbG8=",
        }
    }

    assert validate_trace(trace) == []
```

- [ ] **Step 2: Implement validation if needed**

If the test already passes, leave `harness/trace_validation.py` unchanged. If it fails, add optional validation:

```python
    file_fixtures = trace.get("fileFixtures")
    if file_fixtures is not None and not isinstance(file_fixtures, dict):
        errors.append(f"trace.fileFixtures: expected object, got {type_name(file_fixtures)}")
```

- [ ] **Step 3: Configure Claude reference profile**

In `examples/targets/claude-ref/harness.profile.json`, add a top-level `fileCapture` block:

```json
  "fileCapture": {
    "mode": "allowlist",
    "selectors": [
      "#fileInput",
      "#projectLoadInput"
    ],
    "maxFileBytes": 10000000,
    "maxFiles": 4
  }
```

Keep JSON valid. If this block is added after `environmentCapture`, add a comma between top-level objects.

- [ ] **Step 4: Verify selected tests**

Run:

```powershell
python -m pytest tests/test_trace_validation.py tests/test_profile.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add harness/trace_validation.py tests/test_trace_validation.py examples/targets/claude-ref/harness.profile.json
git commit -m "Enable file capture for claude reference profile"
```

## Task 6: End-To-End Manual Verification

**Files:**
- Generated only: `traces/*.json`, `reports/*.md`, `runs/*.jsonl`

- [ ] **Step 1: Run full automated verification**

Run:

```powershell
python -m pytest -v
node --check harness/static/harness_client.js
```

Expected:

- pytest reports all tests passed.
- node syntax check exits 0.

- [ ] **Step 2: Restart the harness server on port 6180**

From `D:\harness`, stop the old listener if needed:

```powershell
$listener = Get-NetTCPConnection -LocalPort 6180 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' } | Select-Object -First 1
if ($listener) { Stop-Process -Id $listener.OwningProcess -Force }
```

Start the feature branch server:

```powershell
cd D:\harness\.worktrees\environment-fixture
python harness_server.py --profile examples/targets/claude-ref/harness.profile.json --target d:/claude --port 6180
```

- [ ] **Step 3: Record a file input flow**

Open:

```text
http://127.0.0.1:6180/
```

Record this flow:

1. Start capture.
2. Use the app's file menu to import/load a file through `#fileInput` or `#projectLoadInput`.
3. Wait until the app state shows `hasMesh=true`.
4. Switch `Rig -> Slot -> Object -> Rig`.
5. Save trace.

- [ ] **Step 4: Inspect the trace for file fixtures**

Run:

```powershell
@'
import json
from pathlib import Path
trace_path = max(Path("traces").glob("*.json"), key=lambda p: p.stat().st_mtime)
trace = json.loads(trace_path.read_text(encoding="utf-8"))
print(trace_path)
print("fileFixtures", len(trace.get("fileFixtures", {})))
for i, event in enumerate(trace.get("events", [])):
    files = ((event.get("form") or {}).get("files") or [])
    if files:
        print(i, event.get("type"), (event.get("target") or {}).get("selectorHint"), files)
'@ | python -
```

Expected:

- `fileFixtures` count is at least `1`.
- The `input` or `change` event for `#fileInput` or `#projectLoadInput` contains a non-empty `form.files` list.

- [ ] **Step 5: Replay the trace**

Run:

```powershell
python replay_runner.py traces\<latest-trace>.json --run-log runs\<latest-run-log>.jsonl
```

Expected:

- `ok: true`
- `completedEvents` equals the number of replayable events.
- Ignoring WebGL/timing/actionLog volatile fields, the first meaningful divergence should no longer be `debugSnapshot.value.hasMesh` immediately after file input.

- [ ] **Step 6: Generate report**

Run:

```powershell
python report_generator.py traces\<latest-trace>.json --out reports\file-input-fixture-report.md --run-log runs\<latest-run-log>.jsonl
```

Expected:

- Report is generated.
- Replay section shows pass.
- Divergence, if any, should be a later semantic issue or known WebGL environment noise.

## Final Verification Checklist

- [ ] `python -m pytest -v` passes.
- [ ] `node --check harness/static/harness_client.js` passes.
- [ ] `examples/targets/claude-ref/harness.profile.json` is valid JSON.
- [ ] A newly captured trace includes `fileFixtures`.
- [ ] Replay calls `set_input_files()` through the new code path.
- [ ] Real `D:/claude` file import replay no longer stays `hasMesh=false` solely because file content was absent.

## Self-Review

- Spec coverage: The plan covers profile opt-in, bootstrap wiring, browser capture, replay restore, validation, target profile config, and manual E2E proof.
- Placeholder scan: No steps depend on unspecified code; all new public names are explicitly listed.
- Type consistency: `fileCapture` is the profile/bootstrap key; `fileFixtures` is the trace key; events refer to fixture IDs through `event.form.files`.
