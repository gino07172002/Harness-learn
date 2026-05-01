from harness.divergence import (
    diff_value,
    find_first_divergence,
    first_error_divergence,
    first_snapshot_divergence,
)


def test_diff_value_returns_none_for_equal_nested_structures():
    assert diff_value({"a": [1, 2, {"b": 3}]}, {"a": [1, 2, {"b": 3}]}) is None


def test_diff_value_locates_divergence_in_nested_dict():
    result = diff_value({"a": {"b": 1}}, {"a": {"b": 2}})
    assert result == ("a.b", 1, 2)


def test_diff_value_reports_list_length_mismatch():
    result = diff_value([1, 2, 3], [1, 2])
    assert result == ("length", 3, 2)


def test_diff_value_reports_type_mismatch():
    result = diff_value(1, "1")
    assert result is not None
    path, expected, actual = result
    assert expected == 1 and actual == "1"


def test_first_snapshot_divergence_returns_none_when_aligned():
    capture = [{"reason": "capture:start", "debugSnapshot": {"ok": True, "value": {"count": 0}}, "stateSummary": None}]
    replay = [{"reason": "capture:start", "debugSnapshot": {"ok": True, "value": {"count": 0}}, "stateSummary": None}]

    assert first_snapshot_divergence(capture, replay) is None


def test_first_snapshot_divergence_finds_first_offset():
    capture = [
        {"reason": "capture:start", "debugSnapshot": {"ok": True, "value": {"count": 0}}, "stateSummary": None},
        {"reason": "after:click", "debugSnapshot": {"ok": True, "value": {"count": 1}}, "stateSummary": None},
    ]
    replay = [
        {"reason": "capture:start", "debugSnapshot": {"ok": True, "value": {"count": 0}}, "stateSummary": None},
        {"reason": "after:click", "debugSnapshot": {"ok": True, "value": {"count": 99}}, "stateSummary": None},
    ]

    divergence = first_snapshot_divergence(capture, replay)

    assert divergence is not None
    assert divergence["kind"] == "snapshot"
    assert divergence["stepIndex"] == 1
    assert divergence["reason"] == "after:click"
    assert divergence["path"] == "debugSnapshot.value.count"
    assert divergence["expected"] == 1
    assert divergence["actual"] == 99


def test_first_snapshot_divergence_reports_count_mismatch():
    capture = [{"reason": "capture:start", "debugSnapshot": None, "stateSummary": None}]
    replay = [
        {"reason": "capture:start", "debugSnapshot": None, "stateSummary": None},
        {"reason": "extra", "debugSnapshot": None, "stateSummary": None},
    ]

    divergence = first_snapshot_divergence(capture, replay)

    assert divergence is not None
    assert divergence["path"] == "snapshots.length"
    assert divergence["expected"] == 1
    assert divergence["actual"] == 2


def test_first_error_divergence_returns_none_when_both_empty():
    assert first_error_divergence([], []) is None


def test_first_error_divergence_finds_message_mismatch():
    capture = [{"message": "boom"}]
    replay = [{"message": "kaboom"}]

    divergence = first_error_divergence(capture, replay)

    assert divergence is not None
    assert divergence["kind"] == "error"
    assert divergence["expected"] == "boom"
    assert divergence["actual"] == "kaboom"


def test_find_first_divergence_prefers_snapshot_over_error():
    trace = {
        "snapshots": [{"reason": "x", "debugSnapshot": 1, "stateSummary": None}],
        "errors": [{"message": "boom"}],
    }
    replay = {
        "snapshots": [{"reason": "x", "debugSnapshot": 2, "stateSummary": None}],
        "errors": [],
    }

    divergence = find_first_divergence(trace, replay)

    assert divergence is not None
    assert divergence["kind"] == "snapshot"


def test_find_first_divergence_returns_none_when_aligned():
    trace = {"snapshots": [], "errors": []}
    replay = {"snapshots": [], "errors": []}

    assert find_first_divergence(trace, replay) is None
