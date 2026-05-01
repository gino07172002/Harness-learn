from harness.trace_validation import validate_trace


def valid_trace():
    return {
        "version": 1,
        "session": {"targetName": "simple", "proxyUrl": "http://127.0.0.1:6173"},
        "events": [],
        "snapshots": [],
        "console": [],
        "errors": [],
        "screenshots": [],
        "replay": None,
    }


def test_validate_trace_accepts_minimal_valid_trace():
    assert validate_trace(valid_trace()) == []


def test_validate_trace_reports_missing_session_field():
    trace = valid_trace()
    del trace["session"]["targetName"]

    errors = validate_trace(trace)

    assert "trace.session.targetName: missing" in errors


def test_validate_trace_reports_wrong_list_type():
    trace = valid_trace()
    trace["events"] = {}

    errors = validate_trace(trace)

    assert "trace.events: expected list, got dict" in errors


def test_validate_trace_reports_invalid_replay_type():
    trace = valid_trace()
    trace["replay"] = []

    errors = validate_trace(trace)

    assert "trace.replay: expected dict or null, got list" in errors
