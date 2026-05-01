# Harness — a zero-mod debug harness for browser apps

[繁體中文版](README.zh-TW.md) · [Use cases](docs/USE_CASES.md) · [Architecture](docs/architecture.md) · [Decisions log](docs/decisions.md)

Harness wraps any local HTML/JavaScript app with an external observer.
You don't modify the target's source. You point Harness at its folder,
open the proxy URL in a browser, click around, and Harness captures a
trace you can validate, replay, diff against the original session, and
turn into a Markdown report.

## What you get

- **Capture without instrumentation** — Harness serves the target through
  a tiny HTTP proxy and injects a recorder script into every HTML
  response. The target doesn't import anything, doesn't know Harness
  exists, and remains runnable standalone.
- **Replay with Playwright** — feed a saved trace back; Harness reproduces
  the events headless and snapshots the same introspection points the
  capture saw.
- **Divergence diff** — capture vs. replay state is diffed field-by-field.
  Volatile fields (animation timers, generated ids, GPU availability)
  are filtered through a per-target policy so the first divergence
  reported is something semantic, not noise.
- **Markdown reports** — the trace becomes a self-contained file you can
  paste into a PR, an issue, or a chat with another agent.
- **Golden regression** — pin a known-good trace + report; Harness re-runs
  it on every commit and tells you when behavior drifted.
- **Doctor self-test** — before any run, Harness checks the environment
  (Python, Playwright, Chromium, port, target folder, write permissions)
  *and* verifies its own diff engine still suppresses the volatile fields
  the active profile lists.

## Install

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Python 3.10+ required. Linux / macOS / Windows all work.

## Hello-world: the bundled fixture

The repo ships a minimal target so you can verify the install in one
command without writing any config:

```bash
python harness_regress.py --golden examples/golden/simple-trace.json
```

Expected output:

```
Golden regression passed: examples/golden/simple-trace.json
```

That command spawns a fixture server, replays the bundled golden trace
through Playwright, regenerates the report, and compares it against the
checked-in reference. If it passes, your install can capture, replay,
diff, and report.

## Hello-world: capture your own trace

Point Harness at any local HTML/JS app. We'll use a real example below
([meshWarp2](https://github.com/gino07172002/meshWarp2), a browser-based
2D skeletal animation editor) but the same flow works for any static
web target.

Layout — Harness and the target sit as siblings:

```
projects/
├── harness/              ← this repo
└── meshWarp2/            ← the target (cloned separately)
    ├── index.html
    ├── app/
    └── ...
```

Inside `harness/`, drop a profile that describes the target:

```bash
mkdir -p examples/targets/meshwarp2
cat > examples/targets/meshwarp2/harness.profile.json <<'JSON'
{
  "name": "meshwarp2",
  "root": "../../../meshWarp2",
  "startupPath": "/",
  "host": "127.0.0.1",
  "port": 6181,
  "stateGlobals": [],
  "debugMethods": [
    "collectSlotBindingDebug",
    "collectAutosaveWeightDebug",
    "collectWeightedAttachmentIssues",
    "dumpGLState"
  ],
  "volatileFields": [
    "debugSnapshot.value.gl",
    "debugMethodResults.dumpGLState.value"
  ],
  "passiveProbes": {
    "domSnapshot": true,
    "domSelectors": [
      "#glCanvas", "#overlay", "#status",
      "#playBtn", "#stopBtn", "#animTime",
      "#fileSaveBtn", "#fileLoadBtn",
      "#undoBtn", "#redoBtn",
      "#boneTree", "#timelineTracks"
    ]
  },
  "environmentCapture": {
    "localStorage": {
      "mode": "allowlist",
      "keys": ["uiLayout:v3"]
    }
  }
}
JSON
```

A few honest notes about this profile, because they'll come up the first
time you write one for a real codebase:

- meshWarp2 doesn't expose a single `window.debug` namespace the way some
  Harness targets do. Its introspection helpers are scattered across
  flat globals (`window.collectSlotBindingDebug`, `window.dumpGLState`,
  etc.). Profiles handle that — `debugMethods` is just a list of
  function names to invoke off `window`. You don't need to refactor the
  target.
- `stateGlobals: []` is intentional. meshWarp2 keeps its main state
  module-scoped, not on `window`. Snapshots will skip the
  `stateSummary` field — that's fine.
- The autosave key (`mesh_deformer_autosave_v1`) is left out of
  `localStorage.keys`. It changes every frame and would either bloat the
  trace or fight the divergence engine. If you want it, add it and put
  the relevant subtree in `volatileFields`.
- WebGL availability differs between your machine and Playwright's
  headless replay. The `volatileFields` entries above tell the diff
  engine to ignore the entire `gl` subtree.

Now run capture:

```bash
python harness_server.py --profile examples/targets/meshwarp2/harness.profile.json
```

Open http://127.0.0.1:6181/ in any browser. You'll see a small "HARNESS"
panel docked top-right. Click **Start**, do whatever you want to record
in the target, click **Stop**, then **Save**. The trace lands in
`traces/<timestamp>.json`.

Now replay it:

```bash
python replay_runner.py traces/<timestamp>.json
```

And turn it into a report:

```bash
python report_generator.py traces/<timestamp>.json --out reports/my-session.md
```

The report has a divergence section that names the first state
field where replay and capture disagreed. If your `volatileFields` list
is right, that field is something semantic ("the bone tree didn't
expand") and not environmental ("WebGL was available on the host but
not in headless Chromium").

## What's in the box

```
harness/                 core modules: proxy, replay, report, doctor,
                         schema validator, divergence engine, regression
harness/static/          the injected recorder (harness_client.js)
examples/targets/        reference targets — the bundled fixture and
                         examples of profile shapes
examples/golden/         golden traces and reports for self-regression,
                         including negative goldens that prove the
                         schema validator rejects malformed traces
docs/                    architecture, decisions log, runbooks, specs,
                         use-cases, AI-handoff guide
tests/                   pytest coverage for every harness layer
```

## When Harness fits and when it doesn't

**Harness fits when** the target is a static or proxy-able HTML/JS app
you can run locally, you have access to its source for at least
inspection, and you want repeatable capture/replay/diff over UI behavior.
Typical use cases: regression-checking a creative tool you own, helping
an AI agent reproduce a UI bug deterministically, building golden
fixtures for visual / state regression in a single-page app.

**Harness doesn't fit when** the target is a remote production site you
can't proxy, requires login flows that don't survive replay, depends on
real-time multiplayer state, or runs on a non-web stack (mobile, native
desktop, embedded). For native code, see
[docs/cross-language-portability.md](docs/cross-language-portability.md).

## Documentation map

For humans:
- [Use cases](docs/USE_CASES.md) — concrete scenarios from "I want to
  test my own creative tool" to "I want to give an AI agent a
  reproducible bug report"
- [Walkthrough (English)](docs/runbooks/harness-engineering-walkthrough.md)
  /
  [(繁體中文)](docs/runbooks/harness-engineering-walkthrough.zh-TW.md) —
  step-by-step end-to-end run
- [First capture](docs/runbooks/first-capture.md)
- [Architecture diagram](docs/architecture.md)

For agents inheriting the project:
- [AI handoff (繁體中文)](docs/AI_HANDOFF.zh-TW.md)
- [Self-observing harness runbook](docs/runbooks/self-observing-harness.md)

For people deciding *whether* to use this:
- [Cross-language portability](docs/cross-language-portability.md) —
  what transfers to non-web stacks and what doesn't

For the design choices:
- [Decisions log](docs/decisions.md)
- [Specs](docs/superpowers/specs/)

## Status

Working today: zero-mod capture, Playwright replay, divergence diff
with comparison-time policy override, profile-driven inspectors, doctor
with actionable hints and timing, golden regression (positive and
negative), self-contained CI.

Not yet: deeper diagnostics (CDP-style breakpoints), event-level
divergence, headed authenticated capture flows.

## License

See [LICENSE](LICENSE) if present, otherwise treat as personal /
educational use until clarified.
