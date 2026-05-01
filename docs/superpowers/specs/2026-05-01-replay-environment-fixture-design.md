# Replay Environment Fixture Design

## Purpose

The harness can already record user events, snapshots, console output, and replay results. The next generalization is to record enough browser environment state to make replay start from the same initial conditions as capture.

This is not a target-specific autosave fix. It is a target-neutral fixture layer for browser applications that depend on local storage or session storage before the first user event.

## Problem

Replay currently opens `trace.session.proxyUrl`, immediately takes `capture:start`, and then replays events. That works only when the target has deterministic empty-start behavior.

Real browser apps often initialize from:

- `localStorage`
- `sessionStorage`
- cookies
- URL path, query, and hash
- IndexedDB or Cache API

The first observed failure came from a target whose initial mesh and slot data were restored from `localStorage`. Capture started with a loaded project, while replay started with an empty project. Event replay succeeded, but state comparison diverged before the first event.

## Scope

V1 supports:

- Capturing selected `localStorage` keys with full values.
- Capturing selected `sessionStorage` keys with full values.
- Restoring those values before replay navigation.
- Keeping existing passive storage summaries for reports.
- Configuring capture policy through target profiles.

V1 does not support:

- Cookies.
- IndexedDB.
- Cache API.
- Service workers.
- File inputs.
- Persisting arbitrary browser context state outside JSON trace data.

These are later layers, not prerequisites for solving the current reproducibility gap.

## Profile Model

Profiles get a new optional block:

```json
{
  "environmentCapture": {
    "localStorage": {
      "mode": "allowlist",
      "keys": ["mesh_deformer_autosave_v1", "uiLayout:v3"]
    },
    "sessionStorage": {
      "mode": "none"
    },
    "maxValueBytes": 5000000
  }
}
```

Supported storage modes:

- `none`: do not capture full values.
- `allowlist`: capture only listed keys.
- `all`: capture all keys up to `maxValueBytes` per value.

Defaults are conservative:

- `localStorage.mode = "none"`
- `sessionStorage.mode = "none"`
- `maxValueBytes = 1000000`

This avoids surprising users by storing large or sensitive browser state without profile opt-in.

## Trace Model

Capture adds a top-level field:

```json
{
  "environmentFixture": {
    "version": 1,
    "url": "http://127.0.0.1:6180/",
    "storage": {
      "localStorage": {
        "mode": "allowlist",
        "items": {
          "mesh_deformer_autosave_v1": "{...}"
        },
        "skipped": []
      },
      "sessionStorage": {
        "mode": "none",
        "items": {},
        "skipped": []
      }
    }
  }
}
```

Skipped entries include the key and reason:

```json
{ "key": "largeBlob", "reason": "value-too-large", "valueLength": 2500000 }
```

The existing `snapshot.passive.storage` remains a compact summary used for diagnostics. `environmentFixture` is the replay seed.

## Replay Flow

Replay changes from:

1. Open browser.
2. Open page.
3. `goto(proxyUrl)`.
4. Take `capture:start`.
5. Replay events.

To:

1. Open browser.
2. Open browser context.
3. Open a page at the proxy origin.
4. Apply `environmentFixture.storage`.
5. Navigate to the recorded URL or proxy URL.
6. Take `capture:start`.
7. Replay events.

Storage restore must run before app startup code reads storage. For same-origin browser storage, Playwright can first navigate to the origin, set storage with `page.evaluate`, then navigate to the target URL.

## Security And Size

The harness stores full browser storage values only when a profile opts in. Profiles should prefer `allowlist` for real targets.

If a value exceeds `maxValueBytes`, the key is skipped and the trace records why. Replay should restore available keys and continue.

## Testing Strategy

Unit tests cover:

- Profile parsing defaults and custom environment capture settings.
- Pure environment fixture builder behavior for `none`, `allowlist`, `all`, missing keys, and oversized values.
- Replay restoration JavaScript generation/application using a fake page object.

Fixture-level tests cover:

- A minimal target that reads `localStorage` on startup can replay with matching initial state when the fixture is present.

V1 implementation can start with unit tests and a small replay helper test. A full Playwright integration test is useful later, but not required to prove the core data model.

## Acceptance Criteria

- Profiles can opt into full local/session storage capture.
- Captured traces include `environmentFixture` only when full-value capture is configured.
- Replay restores fixture storage before taking the first replay snapshot.
- Existing profiles without `environmentCapture` keep current behavior.
- Existing tests and JS syntax checks pass.
