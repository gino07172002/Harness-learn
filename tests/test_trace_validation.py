from harness.trace_validation import validate_trace, validate_trace_with_warnings


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


def test_validate_trace_accepts_optional_environment_fixture_object():
    trace = valid_trace()
    trace["environmentFixture"] = {
        "version": 1,
        "storage": {
            "localStorage": {"items": {"autosave": "{}"}},
            "sessionStorage": {"items": {}},
        },
    }

    assert validate_trace(trace) == []


def test_validate_trace_accepts_optional_file_fixtures_object():
    trace = valid_trace()
    trace["fileFixtures"] = {
        "file_0001": {
            "name": "sample.txt",
            "type": "text/plain",
            "size": 5,
            "base64": "aGVsbG8=",
        }
    }

    assert validate_trace(trace) == []


def test_validate_trace_with_warnings_is_silent_on_real_client_session_fields():
    """Trace produced by harness_client.js should not warn about its own
    session fields. Mirrors what the live recorder writes today."""
    trace = valid_trace()
    trace["session"].update(
        {
            "id": "session-1",
            "targetRoot": "examples/targets/simple",
            "url": "http://127.0.0.1:6173/",
            "viewport": {"width": 1440, "height": 900},
            "harnessRunId": "20260501T000000Z",
            "controller": "user",
            "mode": "capture",
            "startedAt": 1234567,
            "userAgent": "Mozilla/5.0",
        }
    )

    outcome = validate_trace_with_warnings(trace)

    assert outcome.errors == []
    assert outcome.warnings == []


def test_validate_trace_with_warnings_accepts_capture_stop_and_save_reasons():
    trace = valid_trace()
    trace["snapshots"] = [
        {"reason": "capture:start"},
        {"reason": "capture:stop"},
        {"reason": "capture:save"},
    ]

    outcome = validate_trace_with_warnings(trace)

    assert outcome.errors == []
    assert outcome.warnings == []


def test_validate_trace_rejects_environment_fixture_not_dict():
    trace = valid_trace()
    trace["environmentFixture"] = "not-object"

    errors = validate_trace(trace)

    assert "trace.environmentFixture: expected dict, got str" in errors


def test_validate_trace_rejects_file_fixtures_not_dict():
    trace = valid_trace()
    trace["fileFixtures"] = "not-object"

    errors = validate_trace(trace)

    assert "trace.fileFixtures: expected dict, got str" in errors


def test_validate_trace_rejects_file_fixture_entry_missing_required():
    trace = valid_trace()
    trace["fileFixtures"] = {"file_0001": {"name": "x.txt"}}

    errors = validate_trace(trace)

    assert "trace.fileFixtures['file_0001'].type: missing" in errors
    assert "trace.fileFixtures['file_0001'].size: missing" in errors
    assert "trace.fileFixtures['file_0001'].base64: missing" in errors


def test_validate_trace_rejects_file_fixture_size_wrong_type():
    trace = valid_trace()
    trace["fileFixtures"] = {
        "file_0001": {"name": "x", "type": "t", "size": "big", "base64": "AA=="}
    }

    errors = validate_trace(trace)

    assert "trace.fileFixtures['file_0001'].size: expected number, got str" in errors


def test_validate_trace_rejects_environment_fixture_storage_not_dict():
    trace = valid_trace()
    trace["environmentFixture"] = {"version": 1, "storage": "not-a-dict"}

    errors = validate_trace(trace)

    assert "trace.environmentFixture.storage: expected dict, got str" in errors


def test_validate_trace_rejects_environment_fixture_storage_layer_items_not_dict():
    trace = valid_trace()
    trace["environmentFixture"] = {
        "storage": {"localStorage": {"items": []}}
    }

    errors = validate_trace(trace)

    assert (
        "trace.environmentFixture.storage.localStorage.items: expected dict, got list"
        in errors
    )
