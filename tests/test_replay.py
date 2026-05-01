import asyncio

from harness.replay import attach_replay_result, extract_fixture_storage, replayable_events, restore_environment_fixture


def test_replayable_events_keeps_user_input_events():
    trace = {
        "events": [
            {"type": "pointerdown", "time": 1},
            {"type": "pointermove", "time": 2},
            {"type": "pointerup", "time": 3},
            {"type": "click", "time": 4},
            {"type": "keydown", "time": 5},
            {"type": "keyup", "time": 6},
            {"type": "wheel", "time": 7},
            {"type": "input", "time": 8}
        ]
    }

    assert [event["type"] for event in replayable_events(trace)] == [
        "pointerdown",
        "pointermove",
        "pointerup",
        "click",
        "keydown",
        "keyup",
        "wheel",
        "input",
    ]


def test_replayable_events_drops_unknown_events():
    trace = {"events": [{"type": "custom"}, {"type": "click"}]}

    assert [event["type"] for event in replayable_events(trace)] == ["click"]


def test_attach_replay_result_keeps_original_trace_fields():
    trace = {"version": 1, "events": [{"type": "click"}], "replay": None}
    result = {"ok": True, "completedEvents": 1}

    updated = attach_replay_result(trace, result)

    assert updated["version"] == 1
    assert updated["events"] == [{"type": "click"}]
    assert updated["replay"] == result


def test_replay_result_event_payload_is_stable():
    from harness.replay import build_replay_completed_event

    payload = build_replay_completed_event({"ok": True, "completedEvents": 3})

    assert payload == {"ok": True, "completedEvents": 3}


def test_extract_fixture_storage_returns_local_and_session_items():
    trace = {
        "environmentFixture": {
            "storage": {
                "localStorage": {"items": {"autosave": "project-json"}},
                "sessionStorage": {"items": {"tab": "rig"}},
            }
        }
    }

    storage = extract_fixture_storage(trace)

    assert storage == {
        "localStorage": {"autosave": "project-json"},
        "sessionStorage": {"tab": "rig"},
    }


def test_extract_fixture_storage_defaults_missing_fixture_to_empty_items():
    assert extract_fixture_storage({}) == {"localStorage": {}, "sessionStorage": {}}


class FakeContext:
    def __init__(self):
        self.calls = []

    async def add_init_script(self, script=None, *, path=None):
        self.calls.append({"script": script, "path": path})


def test_restore_environment_fixture_writes_storage_values():
    context = FakeContext()
    trace = {
        "environmentFixture": {
            "storage": {
                "localStorage": {"items": {"autosave": "project-json"}},
                "sessionStorage": {"items": {"tab": "rig"}},
            }
        }
    }

    asyncio.run(restore_environment_fixture(context, trace))

    assert len(context.calls) == 1
    assert context.calls[0]["path"] is None
    assert "project-json" in context.calls[0]["script"]
    assert "window.localStorage.setItem(key, value)" in context.calls[0]["script"]


def test_restore_environment_fixture_skips_empty_fixture():
    context = FakeContext()

    asyncio.run(restore_environment_fixture(context, {}))

    assert context.calls == []
