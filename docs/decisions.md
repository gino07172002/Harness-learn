# Decisions Log

Append-only, newest on top. One entry per non-obvious choice. Format:
heading with date and short summary, then a paragraph of context, then
the alternative considered and why it was rejected.

When you make a call a future reader will second-guess, add an entry.
Do not retroactively backfill history.

---

## 2026-05-01 — Volatility override at comparison time (clarification)

The earlier entry said the profile is the single source of truth and a
trace can be re-diffed under different policies. In practice the client
*also* snapshots the active `volatileFields` into `trace.session` at
capture time, and `harness/replay.py` was reading that frozen list. Net
effect: changing the profile only affected *future* captures; existing
traces kept their old policy.

Reconciled by giving replay and regression an explicit override knob
rather than re-routing capture. `replay_trace_async` and
`run_report_regression` accept `volatile_fields_override` (replaces the
trace's frozen list) and `extra_volatile_fields` (appends). The CLIs
expose this as `replay_runner.py --profile / --volatile-field` and
`harness_regress.py --volatile-field / --ignore-trace-volatile-fields`.

`harness_regress.py` uses the profile's `volatileFields` as the override
*only when the user actually passes `--profile`* (matching the
architecture decision); when `--profile` is omitted, the trace's frozen
list is the fallback. An earlier iteration of this fix had the parser
default `--profile` to the simple profile silently, which made the
override path always fire and dropped the trace's policy. The parser
default is now `None`; the simple profile is only injected as a target /
port fallback when the regress flow needs to spawn a fixture server.

The trace continues to record the policy at capture time as historical
context, but it is no longer load-bearing if a profile is supplied.

Alternative considered: stop writing `volatileFields` into the trace
entirely and have replay always re-read the profile. Rejected because
some traces are reviewed standalone (no profile available, e.g. a trace
file shared in a bug report), and the snapshot-into-trace path keeps
those self-contained. Policy *override* preserves both properties: the
trace remains self-describing, but the profile wins when present.

---

## 2026-05-01 — Volatility lives in the profile, not the trace

`harness.profile.json` carries `volatileFields`; the trace itself stores
raw values. Comparison-time suppression keeps capture honest and lets a
single trace be re-diffed against multiple volatility policies later.

Alternative considered: write a per-target suppression list into every
trace at capture time. Rejected because traces would become a moving
target — every policy change would re-bake every golden, and an old
trace could not be re-evaluated under a new policy.

(See the 2026-05-01 clarification above for the implementation gap and
override knobs.)

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
