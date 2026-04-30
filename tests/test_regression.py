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
