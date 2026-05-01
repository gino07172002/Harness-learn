# Use Cases

Concrete scenarios where Harness pays off, written in the form
"who's involved → what they want → how Harness gets them there →
what they get back". Each example is grounded in a real workflow,
not a hypothetical.

If your situation doesn't match any of these, see the [bottom of the
file](#when-harness-is-the-wrong-tool) for honest non-fits.

---

## 1. Reproduce a UI bug for an AI coding agent

**Who** — you're using Claude / Cursor / Codex / similar to fix bugs
in a single-page app you maintain. The bug is "after I import a
project file and click Save twice, the Undo stack is wrong". The
agent says it can't repro and asks for steps.

**Without Harness** — you write a bug report. The agent guesses,
asks follow-ups, you screenshot. Half the time the repro depends on
state you forgot to mention (a particular localStorage value, a
specific window size).

**With Harness** —

```bash
python harness_server.py --profile examples/targets/meshwarp2/harness.profile.json
# open http://127.0.0.1:6181/, click Start, do the reproducing
# steps, click Stop, click Save
python replay_runner.py traces/<timestamp>.json
python report_generator.py traces/<timestamp>.json --out reports/undo-bug.md
```

Hand the agent `reports/undo-bug.md`. It contains:

- The exact event timeline (which buttons in which order).
- A snapshot of `state` and `window.debug.*` results before and
  after each event.
- The localStorage values you had at capture time, so the agent
  knows the starting state — captured because your profile listed
  `localStorage.keys`.
- A divergence section: if the bug only fires under certain
  conditions, the report says exactly which state field changed
  unexpectedly.

The agent now has a deterministic repro it can read in 30 seconds
and a trace it can re-replay locally to verify the fix.

---

## 2. Regression-check your own creative tool

**Who** — you maintain a creative tool (animation editor, level
designer, diagram tool) as a side project. You add features in
bursts. Two months later you can't remember whether "loading a v1
project still works" without manually clicking through every flow.

**With Harness** — record one trace per critical user flow once,
check them in as goldens:

```bash
# After capturing the "load v1 project" flow:
cp traces/<timestamp>.json examples/golden/load-v1-trace.json
cp reports/<timestamp>.md examples/golden/load-v1-report.md

# Now CI / your local pre-commit can run:
python harness_regress.py --golden examples/golden/load-v1-trace.json \
    --target ../meshWarp2 --target-name meshwarp2 \
    --port 6181
```

If a future commit breaks "load v1 project", the regression goes red
with a divergence message naming the first state field that
diverged. The report tells you which event in the timeline
introduced the difference.

This is the same pattern that protects this very repo's own
behavior — see `examples/golden/simple-trace.json` and
`examples/golden/simple-report.md`.

---

## 3. Capture a session from a non-developer for triage

**Who** — a designer or QA on your team finds a bug in a tool you
own, but they can't write a useful bug report and they're not going
to set up a debugger.

**With Harness** — give them the proxy URL. They open it in their
browser, hit Start, reproduce the bug, hit Save. The trace lands in
`traces/`; they send you the JSON file (or copy the path that the
copy-path button gives them). You replay it locally, get a report,
and now have evidence-based triage instead of a vague description.

This works because the recorder is *injected by the proxy*, not
installed by the user. The non-dev sees a small panel labeled
HARNESS and three buttons. They never touch source code or DevTools.

---

## 4. Pin a UI behavior under environment noise

**Who** — your app uses WebGL, animations, generated ids, or any
state that legitimately differs between your machine and CI's
headless browser. Naive capture / replay diffs are noisy.

**With Harness** — the `volatileFields` list in the profile tells
the diff engine which paths to ignore. Real example from this repo
(`examples/targets/claude-ref/harness.profile.json`):

```json
"volatileFields": [
  "debugSnapshot.value.currentAnimId",
  "debugSnapshot.value.animTime",
  "debugSnapshot.value.gl",
  "debugTiming.value"
]
```

The first divergence reported by replay is now guaranteed to be
*not* one of these paths. If it shows up at all, it's something
real.

The doctor ([`harness_doctor.py`](../harness_doctor.py)) self-tests
this: it synthesizes a snapshot pair where only a volatile field
differs, runs the diff engine, and fails if the engine surfaces it.
You'll know the volatility wiring is healthy *before* you see a
green regression.

---

## 5. Onboard a new target without reading its source

**Who** — you've inherited a codebase. The handoff doc says
"there's a bug in the bone weight editor". You don't know what the
bone weight editor's DOM looks like, what state globals exist, or
what `window.debug` exposes.

**With Harness** — write a minimum profile, capture once, read the
report. Even an empty `debugMethods` list will produce a trace
showing every event you fired and every DOM selector you touched.
The first capture itself becomes documentation:

- Every selector you interacted with shows up in the operation
  timeline.
- Every console message and pageerror is recorded.
- If the target exposes any introspection method, listing it once
  in `debugMethods` makes its return value appear in every
  snapshot.

In other words, you don't read the codebase to figure out what to
record — you record first, look at the report, and *then* know what
to ask the codebase about.

---

## 6. Hand off a long debugging session to another agent

**Who** — you've been debugging with one AI agent for an hour.
Context window is filling up. You want to start fresh with a
different model or a new session.

**With Harness** — the artifacts under `traces/`, `reports/`, and
`runs/` are the entire context the next agent needs. Hand them:

- `traces/<latest>.json` — what happened
- `reports/<latest>.md` — human-readable summary, including
  divergence
- `runs/<latest>.jsonl` — what the harness itself did, with
  durations

Plus `docs/AI_HANDOFF.zh-TW.md` if the agent doesn't know the
project. The new agent has zero conversation history but has the
same evidence base you had.

This is how this very repo was developed. Multiple Codex review
cycles, each with no shared conversation context, all referenced
the same trace files and report line numbers.

---

## 7. Write a runnable bug report into a GitHub issue

**Who** — you're filing an issue against an upstream project (or
your own). Issues without repro steps get ignored or closed.

**With Harness** — paste the relevant section of the Markdown report
directly into the issue. The report is plain Markdown; GitHub
renders it natively. The reader gets:

- "Operation Timeline" section listing the steps
- "Errors" / "Console" sections with the raw browser output
- "Divergence" section if replay was run, naming the exact field
  that changed

Attach the JSON trace if the upstream maintainer wants to replay
it themselves.

---

## When Harness is the wrong tool

Be honest with yourself before adopting it:

- **Remote production sites you can't proxy.** Harness needs to
  serve the target locally. If the bug only fires against your
  prod API, Harness can't help directly — though it can help
  reproduce the *frontend half* once you have a local stub of the
  backend.
- **Login flows that don't survive replay.** Harness restores
  localStorage / sessionStorage but doesn't manage cookies, OAuth
  redirects, or session expiry. If your bug only happens 5
  minutes after login, you'll need to script the auth separately.
- **Real-time multiplayer state.** Replay assumes the world is
  deterministic. If another user's actions are part of the bug,
  Harness alone won't reproduce it.
- **Native, mobile, embedded.** Harness is web-only. The
  *concepts* port; the implementation does not. See
  [cross-language-portability.md](cross-language-portability.md).
- **You only need DOM snapshots, not behavior.** If "take a
  screenshot, save it, diff next time" is enough, use Percy /
  Chromatic / Playwright's own visual testing. Harness gives you
  state diff, not pixel diff.
- **Sub-millisecond performance work.** Harness instruments the
  page. If you're optimizing 100µs operations, the proxy and
  injected recorder add observable overhead. Use the browser's
  own perf tools.

---

## Profile cheat-sheet

Every use case above leans on a `harness.profile.json`. The fields
you'll actually touch:

| Field | What it does | Don't forget |
|---|---|---|
| `name` | Human label, appears in run logs and reports | Keep it short, used in filenames |
| `root` | Path to the target folder, relative to the profile | Should not be an absolute path; commit-friendly |
| `port` | Where the proxy listens | Pick a non-conflicting one per target |
| `stateGlobals` | `window.*` names that contain target state | Empty list is fine if state is module-scoped |
| `debugMethods` | `window.*` function names invoked every snapshot | Real apps often don't have a `window.debug` namespace; flat names are fine |
| `volatileFields` | Snapshot paths the diff engine should ignore | Add when divergence reports environment noise |
| `passiveProbes.domSelectors` | DOM ids whose state to capture each snapshot | These show up in the report's selector hint column |
| `environmentCapture.localStorage.keys` | Keys to record at capture and restore at replay | Allowlist; don't blanket-capture autosave keys |
| `fileCapture.selectors` / `mode` | File-input elements whose payloads should be captured | `mode: "allowlist"` is sane default |

Full schema: [harness/profile.py](../harness/profile.py).
Real-world example with annotations:
[examples/targets/claude-ref/harness.profile.json](../examples/targets/claude-ref/harness.profile.json).
