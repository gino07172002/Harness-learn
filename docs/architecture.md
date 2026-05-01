# Harness Architecture

One diagram, four boundaries: target, proxy/client, artifacts, observers.

```
+-------------------+
|  Browser target   |
|  examples/...     |
+----------+--------+
           ^
           | zero-mod injection
           v
+-------------------+      +--------------------------+
| harness/proxy.py  |<---->| harness_client.js        |
|                   |      | (records events,         |
|                   |      |  snapshots, console)     |
+----------+--------+      +--------------------------+
           |
           | trace POST
           v
+-------------------+      +--------------------------+
| traces/*.json     |----->| harness/replay.py        |
|                   |      | (Playwright replay)      |
+----------+--------+      +-----------+--------------+
           |                           |
           |                           v
           |               +--------------------------+
           |               | harness/divergence.py    |
           |               | (capture vs replay diff, |
           |               |  honors volatileFields)  |
           |               +-----------+--------------+
           v                           |
+-------------------+                  |
| harness/report.py |<-----------------+
+----------+--------+
           |
           v
       reports/*.md


Self-observation, parallel to every run:

+-------------------+      +--------------------------+
| harness/run_log.py|----->| runs/*.jsonl             |
+-------------------+      | (proxy.started,          |
                           |  trace.saved,            |
                           |  replay.completed,       |
                           |  report.generated, ...)  |
                           +--------------------------+


Pre-flight, before any run:

+-------------------+      +--------------------------+
| harness/doctor.py |----->| stdout / --json          |
+-------------------+      | (detail, durationMs,     |
                           |  hint per check)         |
                           +--------------------------+


Schema contract for every trace artifact:

+-----------------------+
| harness/trace_schema  |  imported by validation,
|                       |  consumed by validator,
| (single source of     |  used by negative goldens
|  truth: event types,  |  in examples/golden/invalid/
|  reasons, divergence) |
+-----------------------+
```

## Boundaries in plain words

- **Target**: any HTML/JS app under `examples/targets/`. Source is never
  modified. The harness reaches it via the proxy.
- **Proxy + client**: `harness/proxy.py` serves the target through a tiny
  HTTP server, injects `harness_client.js` into every HTML response, and
  receives traces via POST. The client records events, snapshots,
  console output, and target-defined `window.debug` methods.
- **Artifacts**: traces (JSON), reports (Markdown), run logs (JSONL),
  golden fixtures (positive and negative). Every artifact has a known
  shape; the trace shape lives in [harness/trace_schema.py](harness/trace_schema.py).
- **Observers**: doctor (pre-flight environment + self-test), run log
  (during the run), report (after the run), divergence (capture vs
  replay), regression (current run vs golden).

## Why this layout

The zero-mod boundary is the load-bearing idea. If the target ever has to
know about the harness, the harness loses its value as an external
observer. Everything else — schema, run log, doctor, divergence — exists
to keep the harness honest about what it is and is not seeing.
