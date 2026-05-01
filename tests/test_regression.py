from harness.regression import compare_reports, normalize_report_markdown


def test_normalize_report_removes_session_line():
    report = "# Harness Debug Report\n\n- Session: abc\n- Events: 2\n"

    normalized = normalize_report_markdown(report)

    assert "- Session: <normalized>" in normalized
    assert "- Events: 2" in normalized


def test_compare_reports_returns_empty_list_for_matching_normalized_reports():
    current = "# Harness Debug Report\n\n- Session: abc\n- Events: 2\n"
    golden = "# Harness Debug Report\n\n- Session: xyz\n- Events: 2\n"

    assert compare_reports(current, golden) == []


def test_compare_reports_explains_mismatch():
    current = "# Harness Debug Report\n\n- Events: 3\n"
    golden = "# Harness Debug Report\n\n- Events: 2\n"

    errors = compare_reports(current, golden)

    assert errors
    assert "normalized report differs" in errors[0]


def test_run_report_regression_forwards_volatile_override(tmp_path, monkeypatch):
    """Codex review follow-up: comparison-time volatility must come from
    profile, not from the trace's frozen list. Confirm the kwargs reach
    replay_trace."""
    from harness import regression as regression_module

    captured: dict = {}

    def fake_replay_trace(trace, **kwargs):
        captured.update(kwargs)
        return {"ok": True, "completedEvents": 0, "snapshots": [], "errors": []}

    monkeypatch.setattr(regression_module, "replay_trace", fake_replay_trace)
    monkeypatch.setattr(regression_module, "build_report_markdown", lambda trace: "x")
    monkeypatch.setattr(regression_module, "validate_trace", lambda trace: [])
    monkeypatch.setattr(regression_module, "compare_reports", lambda current, golden: [])

    golden_trace = tmp_path / "g.json"
    golden_trace.write_text('{"version":1}', encoding="utf-8")
    golden_report = tmp_path / "g.md"
    golden_report.write_text("x", encoding="utf-8")

    errors = regression_module.run_report_regression(
        golden_trace,
        golden_report,
        volatile_fields_override=["live.policy"],
        extra_volatile_fields=["explicit.path"],
    )

    assert errors == []
    assert captured.get("volatile_fields_override") == ["live.policy"]
    assert captured.get("extra_volatile_fields") == ["explicit.path"]


def test_volatile_field_suppression_proven_negatively_via_divergence():
    """Negative proof for volatility coverage spec.

    The volatile-fixture profile lists debugSnapshot.value.tick. Build a
    capture/replay pair where only that field differs and confirm the
    divergence engine suppresses it. Then confirm that *removing* the
    declared volatile list resurfaces the divergence — without this second
    check, a passing run would not prove suppression actually did work.
    """
    from harness.divergence import find_first_divergence

    capture = {
        "snapshots": [
            {
                "reason": "capture:start",
                "debugSnapshot": {"ok": True, "value": {"count": 0, "tick": 1}},
                "stateSummary": None,
            }
        ],
        "errors": [],
    }
    replay = {
        "snapshots": [
            {
                "reason": "capture:start",
                "debugSnapshot": {"ok": True, "value": {"count": 0, "tick": 999}},
                "stateSummary": None,
            }
        ],
        "errors": [],
    }

    suppressed = find_first_divergence(
        capture, replay, volatile_fields=["debugSnapshot.value.tick"]
    )
    assert suppressed is None, "volatile field should have been suppressed"

    surfaced = find_first_divergence(capture, replay, volatile_fields=[])
    assert surfaced is not None, "removing the volatile list must resurface the divergence"
    assert surfaced["path"] == "debugSnapshot.value.tick"
    assert surfaced["expected"] == 1
    assert surfaced["actual"] == 999
