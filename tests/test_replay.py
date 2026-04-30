from harness.replay import attach_replay_result, replayable_events


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
