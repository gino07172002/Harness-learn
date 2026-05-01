# Replay Environment Fixture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a target-neutral environment fixture layer so replay can restore selected browser storage before app startup.

**Architecture:** Extend profiles with an `environmentCapture` policy, capture full selected storage values in the injected client as `trace.environmentFixture`, and restore those values in replay before the first snapshot. Keep passive probes as diagnostic summaries and use the new fixture only as replay seed data.

**Tech Stack:** Python dataclasses and pytest for profile/replay logic, injected browser JavaScript for capture, Playwright for replay.

---

## File Structure

- Modify `harness/profile.py`: add environment capture dataclasses and parser support.
- Modify `harness/proxy.py`: include environment capture settings in injected bootstrap JSON.
- Modify `harness/static/harness_client.js`: capture full selected local/session storage values into `trace.environmentFixture`.
- Modify `harness/replay.py`: restore fixture storage before capture-start snapshot.
- Modify `harness/trace_validation.py`: allow optional `environmentFixture`.
- Modify `examples/targets/claude-ref/harness.profile.json`: opt into the target's known autosave/layout keys without hardcoding behavior in harness code.
- Modify `tests/test_profile.py`: cover parser defaults and overrides.
- Modify `tests/test_proxy.py`: cover bootstrap injection.
- Modify `tests/test_replay.py`: cover storage restore helper behavior.

## Task 1: Profile Environment Capture Model

**Files:**
- Modify: `harness/profile.py`
- Test: `tests/test_profile.py`

- [ ] **Step 1: Write failing profile parser tests**

Add tests that expect default disabled environment capture and custom allowlist parsing.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_profile.py -v`

Expected: tests fail because `Profile.environment_capture` does not exist.

- [ ] **Step 3: Implement profile dataclasses and parser**

Add `StorageCapturePolicy` and `EnvironmentCapture` dataclasses. Parse `environmentCapture.localStorage`, `environmentCapture.sessionStorage`, and `environmentCapture.maxValueBytes`.

- [ ] **Step 4: Run profile tests**

Run: `python -m pytest tests/test_profile.py -v`

Expected: all profile tests pass.

## Task 2: Proxy Bootstrap Wiring

**Files:**
- Modify: `harness/proxy.py`
- Test: `tests/test_proxy.py`

- [ ] **Step 1: Write failing bootstrap test**

Add a test proving `environmentCapture` appears in `__HARNESS_BOOTSTRAP__`.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_proxy.py -v`

Expected: new test fails because bootstrap does not contain `environmentCapture`.

- [ ] **Step 3: Add bootstrap serialization**

Serialize the profile's environment capture settings into the injected bootstrap.

- [ ] **Step 4: Run proxy tests**

Run: `python -m pytest tests/test_proxy.py -v`

Expected: all proxy tests pass.

## Task 3: Browser Capture Fixture

**Files:**
- Modify: `harness/static/harness_client.js`

- [ ] **Step 1: Add browser-side fixture capture code**

Read `bootstrap.environmentCapture`, collect full selected storage values at capture start, and write `trace.environmentFixture`.

- [ ] **Step 2: Run JavaScript syntax check**

Run: `node --check harness/static/harness_client.js`

Expected: command exits 0.

## Task 4: Replay Storage Restore

**Files:**
- Modify: `harness/replay.py`
- Test: `tests/test_replay.py`

- [ ] **Step 1: Write failing replay helper tests**

Add tests for a pure helper that extracts local/session storage items from `trace.environmentFixture`.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_replay.py -v`

Expected: tests fail because helper functions do not exist.

- [ ] **Step 3: Implement replay storage restore helpers**

Add helpers for fixture extraction and an async `restore_environment_fixture(page, trace)` that sets local/session storage before replay snapshots.

- [ ] **Step 4: Run replay tests**

Run: `python -m pytest tests/test_replay.py -v`

Expected: all replay tests pass.

## Task 5: Validation And Claude Profile

**Files:**
- Modify: `harness/trace_validation.py`
- Modify: `examples/targets/claude-ref/harness.profile.json`

- [ ] **Step 1: Allow optional environment fixture in validation**

Ensure the validator accepts traces with optional `environmentFixture` while still requiring existing top-level trace fields.

- [ ] **Step 2: Configure the Claude reference profile**

Set `environmentCapture.localStorage` to allowlist `mesh_deformer_autosave_v1` and `uiLayout:v3`. Leave `sessionStorage` as `none`.

- [ ] **Step 3: Run full verification**

Run:

```powershell
python -m pytest -v
node --check harness/static/harness_client.js
```

Expected: all tests pass and JS syntax check exits 0.

## Self-Review

- Spec coverage: profile policy, trace model, browser capture, replay restore, and validation are covered.
- Placeholder scan: no task depends on unspecified future work.
- Type consistency: `environmentCapture` is the profile/bootstrap key; `environmentFixture` is the trace/replay key.
