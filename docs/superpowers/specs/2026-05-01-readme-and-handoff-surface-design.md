# README and Handoff Surface Design

## Goal

Make the first 60 seconds of contact with this repository informative for
both a human visitor and a fresh AI agent.

Today `README.md` is a single line. Anyone who arrives via GitHub, a file
explorer, or `cat README.md` sees nothing useful. The handoff document
`docs/AI_HANDOFF.zh-TW.md` is excellent but only an agent that has already
been told to read it will find it. New humans will not.

This stage gives the project a real entry surface without duplicating
content that already lives in `AI_HANDOFF.zh-TW.md`.

## Why This Is Harness Engineering

A harness whose value cannot be explained on its first page is a harness
that will be replaced by something the next engineer understands faster.
The artifacts inside this repo — traces, reports, run logs, golden
fixtures, doctor output — are unusually self-describing. The README is
the only place that lets a newcomer realize that *before* they start
poking at code.

This is also a harness engineering lesson in itself: the boundary between
"the project" and "the documentation" should be observable. A reader
should be able to tell at a glance which files are the harness, which are
fixtures, and which are docs.

## Scope

Three increments, in order:

1. README rewrite: one-screen overview, command quickstart, file map.
2. Architecture diagram: a single SVG/PNG (or ASCII if image is too
   heavyweight) showing the harness boundaries.
3. Decisions log: a short, append-only file capturing why non-obvious
   choices were made.

## Non-Goals

- Do not duplicate `AI_HANDOFF.zh-TW.md`. README links to it; it does
  not restate it.
- Do not split docs across more than one new top-level file. The README
  and one diagram and one decisions log are the entire surface this
  spec adds.
- Do not produce English translations of every existing doc. The
  handoff doc is in Traditional Chinese intentionally; the README will be
  bilingual where it improves discoverability and otherwise English-only.
- Do not introduce a docs site, MkDocs, or similar tooling.

## Increment 1: README Rewrite

The new `README.md` has these sections, in this order:

```text
# Harness Engineering Playground

One sentence: what this repo is.

## What is this?

Three to five sentences. The repo is the harness. External apps are
reference targets. The harness can capture, validate, replay, diff, and
regress browser sessions without modifying the target.

## Quick start

Three commands a fresh user can paste:

  python -m pip install -r requirements.txt
  python -m playwright install chromium
  python harness_regress.py --golden examples/golden/simple-trace.json

If the third one prints `Golden regression passed`, the harness works on
this machine.

## File map

Top-level directories with one-line descriptions, matching the
existing layout (harness/, examples/, traces/, reports/, runs/, docs/,
tests/).

## Where to go next

Three links:

  - For humans new to harness engineering:
    docs/runbooks/harness-engineering-walkthrough.md
  - For an AI agent inheriting this repo:
    docs/AI_HANDOFF.zh-TW.md
  - For the design decisions:
    docs/superpowers/specs/

## Status

A short status line: what works today, what is in progress.
```

The README must fit comfortably in one terminal screen at 80 columns.
Anything that does not fit moves to a linked document.

## Increment 2: Architecture Diagram

Add `docs/architecture.md` containing one ASCII or Mermaid diagram that
shows the four boundaries:

```text
+-------------------+
|  Browser target   |
|  (examples/...)   |
+----------+--------+
           |
           |  zero-mod injection
           v
+-------------------+      +------------------+
| harness/proxy.py  |<---->| harness_client.js|
+----------+--------+      +------------------+
           |
           |  trace POST
           v
+-------------------+      +------------------+
| traces/*.json     |----->| harness/replay.py|
+----------+--------+      +--------+---------+
           |                        |
           v                        v
+-------------------+      +------------------+
| harness/report.py |      | divergence diff  |
+-------------------+      +------------------+
           |
           v
       reports/*.md

(parallel, throughout the run)

+-------------------+
| harness/run_log.py|  ----> runs/*.jsonl
+-------------------+

(before any run)

+-------------------+
| harness/doctor.py |  ----> stdout / json
+-------------------+
```

Mermaid is preferred if it renders on GitHub; the ASCII diagram is the
fallback for offline / terminal viewers.

The diagram is the only one. If a future spec wants more, it adds them in
its own document.

## Increment 3: Decisions Log

Add `docs/decisions.md`. Append-only, newest-on-top, one entry per
non-obvious choice. Format:

```markdown
## 2026-05-01 — Why volatileFields lives in the profile, not the trace

Trade-off: capture should record raw values; suppression is a
comparison-time concern. Putting volatility in the profile means a single
target can be re-diffed against multiple volatility policies later.

Alternative considered: write the suppression list into the trace at
capture time. Rejected because traces become a moving target and goldens
would re-bake whenever the policy changes.
```

Seed entries to add now (each one short, the reasoning already exists
elsewhere — this is just collecting it):

- Why version 1 traces, not unversioned.
- Why HTML injection lives at proxy time, not via a service worker.
- Why JSONL for run logs.
- Why Playwright not Puppeteer.
- Why the doctor has its own CLI rather than being part of the proxy.
- Why goldens are checked-in fixtures rather than generated each run.

The list is short on purpose. Future agents add new entries when they
make a choice that a future reader will second-guess; they do not
retroactively backfill.

## Touch Points

```text
README.md            rewrite
docs/architecture.md new
docs/decisions.md    new
```

No code or test changes.

## Success Criteria

- `README.md` is at least 30 lines and at most 100, contains the three
  quick-start commands, and links to the handoff doc and walkthrough.
- A user with no prior context can run the third quick-start command
  successfully on a fresh clone.
- `docs/architecture.md` renders the boundary diagram so a reader can
  identify the harness, target, artifacts, and run log without reading
  source.
- `docs/decisions.md` contains the six seed entries listed above.
- No existing doc is broken or moved; cross-references in
  `AI_HANDOFF.zh-TW.md` still resolve.

## Teaching Notes

A README is not a marketing surface. It is a *routing* surface. Its job
is to send the reader to the right next file in under a minute. The
quick-start command exists because a working command builds more trust
in 10 seconds than three paragraphs of prose.

A decisions log is the one piece of documentation that does not rot,
because it is timestamped and append-only. Encourage the next agent to
write to it whenever they make a call that someone will later ask
"why?" about.
