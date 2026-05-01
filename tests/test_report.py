from harness.report import build_report_markdown


def test_build_report_markdown_includes_high_signal_sections():
    trace = {
        "version": 1,
        "session": {"id": "abc", "targetName": "simple", "proxyUrl": "http://127.0.0.1:6173"},
        "events": [{"type": "click", "target": {"selectorHint": "#incrementBtn"}}],
        "snapshots": [{"reason": "after:click", "debugSnapshot": {"ok": True, "value": {"count": 1}}}],
        "console": [{"level": "warn", "args": [{"type": "string", "sample": "careful"}]}],
        "errors": [{"type": "error", "message": "boom"}],
        "replay": {"ok": False, "firstFailure": {"eventIndex": 0, "error": "miss"}}
    }

    markdown = build_report_markdown(trace)

    assert "# Harness Debug Report" in markdown
    assert "simple" in markdown
    assert "Events: 1" in markdown
    assert "boom" in markdown
    assert "first divergence" in markdown.lower()


def test_report_generated_event_payload_is_stable():
    from harness.report import build_report_generated_event

    payload = build_report_generated_event("reports/simple-report.md")

    assert payload == {"path": "reports/simple-report.md"}


def test_report_flags_repeated_pointer_attempt_without_capture_state_change():
    trace = {
        "version": 1,
        "session": {"id": "abc", "targetName": "claude", "proxyUrl": "http://127.0.0.1:6180"},
        "events": [
            {"type": "pointerdown", "target": {"selectorHint": "#workspaceTabObject"}},
            {"type": "pointerup", "target": {"selectorHint": "#workspaceTabObject"}},
            {"type": "pointerdown", "target": {"selectorHint": "#workspaceTabObject"}},
            {"type": "pointerup", "target": {"selectorHint": "#workspaceTabObject"}},
            {"type": "pointerdown", "target": {"selectorHint": "#workspaceTabObject"}},
            {"type": "pointerup", "target": {"selectorHint": "#workspaceTabObject"}},
        ],
        "snapshots": [
            {"reason": "capture:start", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "rig"}}}},
            {"reason": "after:pointerdown", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "rig"}}}},
            {"reason": "after:pointerup", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "rig"}}}},
            {"reason": "after:pointerdown", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "rig"}}}},
            {"reason": "after:pointerup", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "rig"}}}},
            {"reason": "after:pointerdown", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "rig"}}}},
            {"reason": "after:pointerup", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "rig"}}}},
        ],
        "console": [],
        "errors": [],
        "replay": {
            "ok": True,
            "completedEvents": 6,
            "snapshots": [
                {"reason": "capture:start", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "rig"}}}},
                {"reason": "after:pointerdown", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "rig"}}}},
                {"reason": "after:pointerup", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "object"}}}},
                {"reason": "after:pointerdown", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "object"}}}},
                {"reason": "after:pointerup", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "object"}}}},
                {"reason": "after:pointerdown", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "object"}}}},
                {"reason": "after:pointerup", "debugSnapshot": {"ok": True, "value": {"workspace": {"ws": "object"}}}},
            ],
            "errors": [],
            "divergence": {
                "kind": "snapshot",
                "stepIndex": 2,
                "reason": "after:pointerup",
                "path": "debugSnapshot.value.workspace.ws",
                "expected": "rig",
                "actual": "object",
            },
        },
    }

    markdown = build_report_markdown(trace)

    assert "## Intent Diagnostics" in markdown
    assert "#workspaceTabObject" in markdown
    assert "pointerdown/up: `3/3`" in markdown
    assert "clicks: `0`" in markdown
    assert "debugSnapshot.value.workspace.ws" in markdown
    assert "capture stayed `rig`; replay reached `object`" in markdown


def test_report_says_no_intent_diagnostics_for_normal_click_trace():
    trace = {
        "version": 1,
        "session": {"id": "abc", "targetName": "simple", "proxyUrl": "http://127.0.0.1:6173"},
        "events": [{"type": "click", "target": {"selectorHint": "#incrementBtn"}}],
        "snapshots": [
            {"reason": "capture:start", "debugSnapshot": {"ok": True, "value": {"count": 0}}},
            {"reason": "after:click", "debugSnapshot": {"ok": True, "value": {"count": 1}}},
        ],
        "console": [],
        "errors": [],
        "replay": {
            "ok": True,
            "completedEvents": 1,
            "snapshots": [
                {"reason": "capture:start", "debugSnapshot": {"ok": True, "value": {"count": 0}}},
                {"reason": "after:click", "debugSnapshot": {"ok": True, "value": {"count": 1}}},
            ],
            "errors": [],
            "divergence": None,
        },
    }

    markdown = build_report_markdown(trace)

    assert "## Intent Diagnostics" in markdown
    assert "No repeated pointer intent failures were detected." in markdown
