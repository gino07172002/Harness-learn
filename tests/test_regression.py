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
