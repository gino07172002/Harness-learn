# Decisions Log

Append-only, newest on top. One entry per non-obvious choice. Format:
heading with date and short summary, then a paragraph of context, then
the alternative considered and why it was rejected.

When you make a call a future reader will second-guess, add an entry.
Do not retroactively backfill history.

---

## 2026-05-01 — Volatility lives in the profile, not the trace

`harness.profile.json` carries `volatileFields`; the trace itself stores
raw values. Comparison-time suppression keeps capture honest and lets a
single trace be re-diffed against multiple volatility policies later.

Alternative considered: write a per-target suppression list into every
trace at capture time. Rejected because traces would become a moving
target — every policy change would re-bake every golden, and an old
trace could not be re-evaluated under a new policy.

---

## 2026-05-01 — Trace schema is dataclasses + small validator, not pydantic

`harness/trace_schema.py` describes the shape with plain Python and a
hand-rolled validator that returns `(errors, warnings)`. The file is
meant to read as documentation.

Alternative considered: pydantic or jsonschema. Rejected to keep the
runtime dependency surface tiny (the project installs from a 2-line
requirements.txt) and to keep error messages under our control. Schema
versioning rule is documented in the spec; when complexity grows, we can
revisit.

---

## 2026-05-01 — Doctor is a separate CLI, not folded into the proxy

`harness_doctor.py` is its own command. The proxy assumes the
environment is already trusted.

Alternative considered: have `harness_server.py` run doctor checks on
startup. Rejected because doctor's value is *pre-flight*: a user who
already started the server has lost the chance to act on failures
cleanly. Doctor must be runnable independently, in CI, before any
process holds open ports.

---

## 2026-05-01 — Run logs are JSONL, not a database

`runs/*.jsonl` is one event per line. Append-only. No schema migrations,
no query layer.

Alternative considered: SQLite. Rejected because every consumer of run
logs (a tail, a grep, a quick script, a CI artifact upload) handles JSONL
trivially. The project optimizes for "an agent reads this in 30 seconds",
not "an analyst queries 10M rows".

---

## 2026-05-01 — Goldens are checked-in fixtures, not regenerated each run

`examples/golden/simple-trace.json` and friends live in git. The
regression command compares against them.

Alternative considered: regenerate the golden on every CI run and verify
it round-trips. Rejected because that proves nothing about *drift*. A
checked-in golden forces a human to inspect changes during code review,
which is the entire point of the regression: catching the harness
silently changing its own output.

---

## 2026-05-01 — Replay uses Playwright, not Puppeteer / CDP-direct

`harness/replay.py` uses `playwright.async_api`.

Alternative considered: Puppeteer (Node) or raw CDP over websocket.
Rejected because Playwright gives us cross-browser support for free, has
a Python binding that fits the rest of the toolchain, and has a stable
API. Direct CDP is reserved for the future "GDB-like debugging" stage
where we need pause/step semantics that Playwright does not expose.

---

## 2026-05-01 — HTML injection at proxy time, not via a service worker

`build_injected_html` rewrites HTML responses before they reach the
browser.

Alternative considered: a service worker that injects the client script
client-side. Rejected because service workers add scope and lifetime
complexity that hides the boundary we are trying to keep visible. A
proxy that mutates HTML on the way through is honest: the user can read
the network response and see exactly what was injected.
