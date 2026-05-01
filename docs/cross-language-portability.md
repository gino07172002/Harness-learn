# Cross-Language Portability of Harness Engineering

This document captures a discussion held on 2026-05-02 about whether the
techniques in `d:\harness` apply to non-web programs (specifically C++).
It is written for a future AI agent inheriting the repo who is asked the
same question or wants to understand which parts of this project are
load-bearing concepts vs. web-specific implementation details.

## Why this document exists

The repo is a learning project. Most of what's checked in is *one*
implementation of harness engineering — zero-mod browser observation
via HTML injection plus Playwright replay. A reader who only sees the
implementation can easily mistake "harness engineering" for "browser
debug tool", and conclude the techniques don't apply to other domains.

That conclusion is wrong, but the truth is layered. This file separates
the layers.

## What this harness actually does

Strip away the implementation details and the project does four things:

| Layer | This repo's web implementation | The underlying concept |
|---|---|---|
| Boundary | Don't modify target source files | Observe the system under test from outside; do not couple harness to target |
| Instrumentation | Inject `harness_client.js` into HTML responses at the proxy | Attach observers at runtime; target needs zero awareness of the harness |
| Trace artifact | events / snapshots / console / errors / replay → JSON | Compress one execution into an offline-reviewable object |
| Replay + diff | Playwright re-runs the trace; `harness/divergence.py` diffs against capture | Use the trace as input to produce a second execution; surface where they drift |

**None of these four are web-specific.** Browser, DOM, Playwright are
implementation choices. The four ideas are the actual product.

## Layer-by-layer portability to C++

### Boundary — fully portable, more options than web

Web's "don't modify target source" comes from the proxy injecting
script tags. C++ has more outside-in observation tools, not fewer:

- Linux: `ptrace`, `LD_PRELOAD`, eBPF, gdb scripts, DynamoRIO,
  Frida-gum
- Windows: Detours, minhook, ETW providers, Frida
- macOS: dtrace, Frida

The boundary concept transfers as-is. There is no architectural
obstacle.

### Instrumentation — portable concept, an order of magnitude more cost

JS injection is string concatenation plus a `<script>` tag. C++ has no
such cheap path:

- **No runtime introspection like `window.debug.snapshot()`.** Reading
  game state requires knowing struct layout (DWARF debug info or a
  hand-written schema), de-referencing pointers from another process's
  memory, and dealing with ABI / calling convention / optimizer
  variable elision.
- **No equivalent of `target.selectorHint`.** A web `#incrementBtn`
  can be hit precisely from outside. Reproducing a click in a C++
  program means locating the function (symbol? vtable? inlined?) and
  driving an input event via OS-level synthetic input, or patching the
  function entry to jump to a fake handler.
- **Snapshots are the worst part.** Web does
  `JSON.stringify(window.state)` in one line. C++ requires
  per-struct serializers, or reflection (which C++ lacks — workarounds
  are Boost.PFR, hand-rolled, or Clang AST tools that auto-generate).

**Practical scale**: this repo's web harness took an afternoon to
bootstrap. A minimum viable C++ harness with comparable surface is
probably two weeks of focused work, and only covers a narrow slice of
the program.

### Trace artifact — concept transfers directly; prior art exists

The JSON trace layer is language-neutral. For C++ the contents shift:

- events become syscall hits / function entry-exit / lock
  acquire-release / hook hits
- snapshots become register dumps / heap-region hashes / serialized
  structs of interest
- console / errors become stderr capture / signals / asserts

This is well-trodden ground. The most relevant prior art:

- **`rr` (Mozilla)** — record-replay debugger for native Linux.
  Records the entire process execution, can replay deterministically,
  set breakpoints inside replay, and compare two replays. The closest
  spiritual cousin to this repo, more mature for C++ than this repo
  is for web.
- **Pernosco** — rr's commercial cloud / UI offering.
- **Time-travel debugging in WinDbg** — Windows equivalent.
- **DTrace / eBPF** — instrumentation layer.
- **Apple Instruments / Tracy / Optick** — game and perf tracing.

**Conclusion for the trace layer**: don't reinvent it. Build on `rr` or
similar. This repo's `harness/trace_store.py` and the streaming JSONL
of `harness/run_log.py` are the right shape but wrong primitive for
deeply non-deterministic native code.

### Replay + diff — two very different worlds

Web replay is easy because the browser handles most non-determinism
for you: deterministic input, mostly stateless DOM, viewport already
fixed. C++ replay is hard because of thread scheduling, malloc
addresses, time-of-day, syscall ordering. **This is exactly why `rr`
is a notable engineering achievement** — it intercepts every
non-deterministic syscall and records its result so replay can feed
the same answer back.

For a C++ harness you have three options:

1. Use `rr`. Strong but Linux-only and high perf cost.
2. Bake determinism in (fix random seeds, fix time, fix thread
   schedule). Many game engines already do this for replay; viable for
   a controlled codebase.
3. Accept that replay is impossible and use the trace only for
   invariant comparison.

The **divergence diff** part of this repo (see
[harness/divergence.py](../harness/divergence.py), `volatileFields`,
the comparison-time override discussion in
[docs/decisions.md](decisions.md)) transfers cleanly. Path-based
volatility filtering and the override-at-comparison-time pattern are
language-neutral. If you have structured snapshots in any format, this
diff engine works on them.

### Trace → human-reviewable artifact — fully portable, high value, undertargeted in C++

[harness/report.py](../harness/report.py) turns a trace into a
Markdown report a human can paste into a PR or issue. The codex review
loop in this project (see commits c96b266 → 01c077d) only worked
because reviewers could cite report line numbers.

Native C++ tools generally don't produce a self-contained
human-reviewable narrative. Tracy gives a frame timeline. `rr` gives a
call-graph dump. Neither is "here is a Markdown summary of what
happened, paste it into a PR." This is a real cultural gap between web
tracing and native tracing.

**This is the layer with the highest return on investment if you
adapt the harness to C++.** It does not require solving any hard
problem (no replay, no instrumentation), only post-processing whatever
trace your tool already produces.

## Where the techniques apply best in C++ land

Suitability of harness-engineering techniques depends heavily on
target type:

| C++ program type | Fit | Why |
|---|---|---|
| Game engine / interactive simulation | High | Frame loop = natural snapshot tick; external-device input is easy to mock; many engines already have deterministic replay infrastructure |
| Pure algorithm / math kernel | High | input → output; deterministic; replay equals unit test |
| Network protocol implementation | High | Trace = packet log (already industry practice via Wireshark / tcpdump); only the replay + diff layer is missing |
| OS / driver / kernel-mode | Medium | rr unavailable; ETW / eBPF / DTrace required; instrumentation cost high but value high |
| GUI desktop app (Qt etc.) | Medium | Closest to web, but no unified DOM-style query API; rely on accessibility tree (UIA / AT-SPI) |
| Real-time embedded | Low | Instrumentation breaks timing; replay typically impossible; tracing must go through hardware probes |
| HFT / low-latency | Low | Any hook is unacceptable |

## Recommended path if you actually want a C++ harness

Do not start from zero. The `apply_event` / `harness_server` /
`harness_client.js` triplet is web-specific and 0% transferable.

The transferable assets in this repo, in approximate order of how
ready they are to be lifted:

1. **`harness/trace_schema.py`** — schema-as-code, `(errors,
   warnings)` validator, `--strict` mode, negative goldens. Direct
   model.
2. **`harness/divergence.py`** — path-based diff with volatile-field
   suppression. Language-neutral, lift verbatim.
3. **`harness/report.py`** — trace-to-Markdown narrative. Easiest
   high-value win.
4. **`harness/regression.py`** — golden trace + report comparison.
   Direct model.
5. **`harness/doctor.py`** — pre-flight environment checks with
   actionable hints, plus a self-test that verifies the harness's own
   wiring. Direct model. The "doctor self-test" pattern (see the
   `volatility.suppression` check) is the most underappreciated idea
   here.
6. **`harness/run_log.py`** — JSONL run log with `timed()` context
   manager. Direct model.
7. **The decisions log convention** — see
   [docs/decisions.md](decisions.md). Append-only, newest on top, one
   non-obvious choice per entry, with why and alternative considered.
   The single most portable thing in this whole project. Has nothing
   to do with web.

For the parts that actually need solving:

- Replay layer: build on `rr` (Linux), Time Travel Debugging
  (Windows), or accept "trace + invariant check, no replay".
- Instrumentation: pick one of LD_PRELOAD / Frida / DynamoRIO /
  ETW based on target OS and depth needed.
- Snapshot serialization: hand-rolled per struct, or generate from
  Clang AST.

## What this repo cannot teach you about non-web

Two genuine limits worth being honest about:

1. **Performance budgets.** This harness instruments a browser; the
   user does not notice 10 ms of overhead. Native programs in the HFT
   / RT / kernel space have nanosecond budgets where any hook is
   unacceptable. The patterns here will not advise you on lock-free
   tracing, ring-buffer design, probe effect minimization.
2. **Multi-threaded determinism.** Nothing in this repo deals with
   concurrent code. Web's single-threaded JS execution makes the
   "replay produces the same result" assumption almost free. C++
   replay engineering is a different field; consult `rr`'s papers.

## Bottom line

The four layers — boundary, instrumentation, trace artifact, replay +
diff — are language-neutral. The instrumentation details are not. The
review-cycle artifacts (this repo's run logs, reports, golden traces,
decisions log, doctor self-tests) are the most portable assets and the
ones a future C++ harness would benefit from imitating verbatim.

If a future agent is asked "can we apply harness engineering to a C++
project," the right framing is: **most of the techniques port; the
specific implementation does not. Build on existing C++ replay infra;
spend your effort on the trace-to-narrative and golden-regression
layers, where the C++ ecosystem is genuinely under-served.**

## Related reading inside this repo

- [docs/decisions.md](decisions.md) — the architecture decisions, all
  written to be language-neutral
- [docs/architecture.md](architecture.md) — boundary diagram for the
  web implementation; useful as a template for what a C++ version's
  diagram would look like
- [docs/superpowers/specs/](superpowers/specs/) — the specs for each
  component; read the goals and non-goals, ignore the web-specific
  implementation
- [docs/AI_HANDOFF.zh-TW.md](AI_HANDOFF.zh-TW.md) — overall project
  handoff
