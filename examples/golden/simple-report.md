# Harness Debug Report

## Summary

- Target: simple
- Session: golden-simple
- Proxy URL: http://127.0.0.1:6173
- Events: 3
- Snapshots: 4
- Console entries: 0
- Errors: 0

## Operation Timeline

1. `click` on `#incrementBtn` at `1`
2. `input` on `#nameInput` at `2`
3. `click` on `#drawCanvas` at `3`

## Errors

No runtime errors were captured.

## Console Warnings And Errors

No console warnings or errors were captured.

## Replay

Replay passed after `3` event(s).

## Divergence

Replay state matches captured state across all aligned snapshots.

## Intent Diagnostics

No repeated pointer intent failures were detected.

## Snapshot Evidence

- `capture:start` state summary: `{'ok': True, 'value': {'type': 'object', 'constructor': 'Object', 'keys': ['count', 'name', 'points']}}` debug snapshot: `{'ok': True, 'value': {'count': 0, 'nameLength': 0, 'pointCount': 0}}`
- `after:click` state summary: `{'ok': True, 'value': {'type': 'object', 'constructor': 'Object', 'keys': ['count', 'name', 'points']}}` debug snapshot: `{'ok': True, 'value': {'count': 1, 'nameLength': 0, 'pointCount': 0}}`
- `after:input` state summary: `{'ok': True, 'value': {'type': 'object', 'constructor': 'Object', 'keys': ['count', 'name', 'points']}}` debug snapshot: `{'ok': True, 'value': {'count': 1, 'nameLength': 0, 'pointCount': 0}}`
- `after:click` state summary: `{'ok': True, 'value': {'type': 'object', 'constructor': 'Object', 'keys': ['count', 'name', 'points']}}` debug snapshot: `{'ok': True, 'value': {'count': 1, 'nameLength': 0, 'pointCount': 1}}`
