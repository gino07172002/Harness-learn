# Zero-Modification Browser Debug Harness Design

## Goal

Build a learning project for software harness engineering around the existing
animation editor in `d:/claude`.

The harness must help a human and AI debug difficult browser-editor bugs by
capturing user operations, app state changes, console output, errors,
screenshots, and replay results. The first version must not modify any file in
`d:/claude`.

This project intentionally feels like a browser-oriented cousin of gdb or
valgrind, but it does not claim raw process-memory access. Browser JavaScript is
sandboxed and does not expose arbitrary memory addresses. The practical target
is deep observability through proxy injection, browser automation, safe object
inspection, and deterministic replay.

## Non-Goals

- Do not edit `d:/claude/index.html` or any source file in the target project.
- Do not build a general-purpose browser DevTools replacement.
- Do not allow AI to freely operate the UI in V1.
- Do not attempt raw memory scanning of the browser process in V1.
- Do not use source-code rewriting or AST instrumentation in V1.

## System Under Test

The SUT is the animation editor in `d:/claude`:

- Vanilla HTML, CSS, and JavaScript.
- Served locally with `python -m http.server 5173`.
- Exposes existing diagnostic surfaces such as `window.debug.snapshot()`,
  `debug.actionLog()`, `debug.errors()`, and `debug.timing()`.
- Uses many global functions and variables because scripts are loaded directly
  by `index.html`.

The harness lives in `d:/harness` and treats the SUT as read-only.

## V1 Architecture

V1 uses a hybrid design:

1. A local proxy server serves the target project from `d:/claude`.
2. The proxy dynamically injects a harness client script into HTML responses.
3. The harness client records browser-side events and snapshots.
4. A Playwright-controlled Chromium window opens the proxied app.
5. User actions are captured as a trace file.
6. Replay reads the trace and replays user-like input through Playwright.
7. A report generator summarizes the capture, replay, state changes, and errors.

The expected layout is:

```text
d:/harness
  harness_server.py
  harness_client.js
  replay_runner.py
  report_generator.py
  traces/
  reports/
  docs/superpowers/specs/
```

## Control Model

V1 supports user control and AI replay only:

- During capture, the user controls the editor.
- The AI observes the trace artifacts and generated report.
- The AI may replay a saved trace.
- The AI does not freely explore, click unknown controls, or take over live use.

The trace must record control-mode metadata so future versions can safely add
AI control:

```json
{
  "controller": "user",
  "mode": "capture"
}
```

## Capture Layer

The injected client records low-level and semantic browser activity:

- Pointer events: `pointerdown`, throttled `pointermove`, `pointerup`, `click`,
  `dblclick`, `contextmenu`.
- Keyboard events: `keydown`, `keyup`, with typed text sanitized.
- Form events: `input`, `change`, `focus`, `blur`, with value summaries rather
  than raw sensitive values.
- Wheel events with compact delta data.
- Console calls: `log`, `info`, `warn`, `error`, `debug`.
- Runtime failures: `window.onerror` and `unhandledrejection`.
- Page metadata: URL, viewport, user agent, timestamp, and capture version.

Each recorded event should include enough target metadata to replay and debug:

```json
{
  "type": "pointerdown",
  "time": 1234.56,
  "target": {
    "tag": "canvas",
    "id": "overlay",
    "classes": [],
    "selectorHint": "#overlay"
  },
  "pointer": {
    "x": 512,
    "y": 348,
    "button": 0,
    "buttons": 1
  }
}
```

## State Inspection Layer

V1 gathers state without requiring the target app to add new hooks.

The snapshot strategy is layered:

1. If `window.debug.snapshot()` exists, call it and capture the result.
2. If `window.debug.actionLog()`, `debug.errors()`, or `debug.timing()` exist,
   capture compact versions of those outputs.
3. If `window.state` exists, safely summarize it.
4. Scan selected global names on `window` and summarize serializable values.

Snapshots must use safe serialization:

- Detect cycles.
- Limit depth.
- Limit array length.
- Limit string length.
- Record type, keys, constructor name, length, and compact samples.
- Avoid copying huge binary, canvas, image, DOM, WebGL, or function internals.
- Record serialization failures as data, not as fatal errors.

The goal is not to dump everything. The goal is to preserve enough state shape
and deltas that an AI can identify the first suspicious transition.

## Trace Format

A trace is a stable JSON artifact:

```json
{
  "version": 1,
  "session": {
    "id": "2026-04-30T12-00-00Z",
    "targetRoot": "d:/claude",
    "proxyUrl": "http://localhost:6173",
    "viewport": { "width": 1440, "height": 900 }
  },
  "events": [],
  "snapshots": [],
  "console": [],
  "errors": [],
  "screenshots": [],
  "replay": null
}
```

The trace must prefer stable, small, AI-readable records over giant raw dumps.
Large artifacts such as screenshots should be stored as separate files and
referenced from the JSON.

## Replay Layer

Replay uses Playwright to act like a user:

- Open Chromium in headed mode.
- Navigate to the proxy URL.
- Apply the same viewport as capture.
- Recreate pointer, keyboard, wheel, and form actions in order.
- Take screenshots at configured checkpoints.
- Capture console output and runtime errors during replay.
- Compare replay snapshots to capture snapshots.

Replay should report the first divergence:

- Event index.
- Original event summary.
- Replay action attempted.
- Capture snapshot summary.
- Replay snapshot summary.
- Console or error output near that step.

V1 does not need perfect replay for every browser behavior. It should make
failures explicit and useful.

## Report Layer

The report generator produces Markdown for humans and AI:

- Session summary.
- User operation timeline.
- Console warnings and errors.
- State changes grouped by event.
- Screenshots or screenshot paths.
- Replay success or failure.
- First divergence, if found.
- Suspected related variables, DOM targets, and app debug outputs.

The report should start with the high-signal summary and put machine evidence
later.

## Learning Milestones

This project teaches harness engineering through six milestones:

1. Harness boundary: separate the SUT from the harness.
2. Capture: instrument user-visible browser behavior.
3. State inspection: collect safe state snapshots and diffs.
4. Trace design: store repeatable debug artifacts.
5. Replay: reproduce captured behavior deterministically enough to debug.
6. Reporting: turn traces into useful AI-readable diagnosis.

## V2 Ideas

After V1 works, possible extensions include:

- Chrome DevTools Protocol heap snapshots.
- Pause-on-exception with call-frame local variable capture.
- Breakpoint management.
- Performance traces.
- In-memory source instrumentation through proxy rewriting.
- AI-suggested replay checkpoints.
- Optional adapter files for target projects that want deeper semantic state.

## Success Criteria

V1 is successful when:

- `d:/claude` remains unmodified.
- The harness can launch the editor through a proxy.
- A user can record a real interaction as a trace.
- The trace contains events, snapshots, console output, and errors.
- Playwright can replay at least basic click, drag, keyboard, input, and wheel
  events from the trace.
- Replay produces a useful pass/fail result and identifies the first divergence
  when behavior differs.
- A Markdown report gives an AI enough context to start debugging without
  asking the user to manually describe every step.
