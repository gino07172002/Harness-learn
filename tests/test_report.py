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
