import asyncio

from harness.replay import (
    attach_replay_result,
    extract_fixture_storage,
    replayable_events,
    resolve_volatile_fields,
    restore_environment_fixture,
)


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


def test_extract_file_payloads_returns_playwright_payloads():
    trace = {
        "fileFixtures": {
            "file_0001": {
                "name": "sample.txt",
                "type": "text/plain",
                "base64": "aGVsbG8=",
            }
        }
    }
    event = {"form": {"files": ["file_0001"]}}

    from harness.replay import extract_file_payloads

    payloads = extract_file_payloads(trace, event)

    assert payloads == [{"name": "sample.txt", "mimeType": "text/plain", "buffer": b"hello"}]


class FakeLocator:
    def __init__(self):
        self.input_files = []
        self.dispatched = []

    async def set_input_files(self, payloads):
        self.input_files.append(payloads)

    async def dispatch_event(self, event_type):
        self.dispatched.append(event_type)


class FakeFilePage:
    def __init__(self):
        self.fake_locator = FakeLocator()

    def locator(self, selector):
        assert selector == "#fileInput"
        return self.fake_locator


def test_apply_file_input_event_sets_files_and_skips_redundant_dispatch():
    from harness.replay import apply_event

    page = FakeFilePage()
    trace = {
        "fileFixtures": {
            "file_0001": {
                "name": "sample.txt",
                "type": "text/plain",
                "base64": "aGVsbG8=",
            }
        }
    }
    event = {
        "type": "change",
        "target": {"selectorHint": "#fileInput"},
        "form": {"files": ["file_0001"]},
    }

    asyncio.run(apply_event(page, event, trace))

    assert page.fake_locator.input_files == [[{"name": "sample.txt", "mimeType": "text/plain", "buffer": b"hello"}]]
    # Playwright's set_input_files already triggers DOM input/change events; dispatching
    # the captured event ourselves would replay the same selection twice.
    assert page.fake_locator.dispatched == []


def test_apply_input_event_without_files_still_dispatches_normally():
    from harness.replay import apply_event

    page = FakeFilePage()
    event = {
        "type": "input",
        "target": {"selectorHint": "#fileInput"},
        "form": {"valueLength": 0},
    }

    asyncio.run(apply_event(page, event, trace={"fileFixtures": {}}))

    # Without form.files, replay should fall back to a plain dispatch — no file payload, no swallowing.
    assert page.fake_locator.input_files == []
    assert page.fake_locator.dispatched == ["input"]


def test_apply_change_event_with_empty_files_list_skips_set_input_files():
    from harness.replay import apply_event

    page = FakeFilePage()
    event = {
        "type": "change",
        "target": {"selectorHint": "#fileInput"},
        "form": {"files": []},
    }

    asyncio.run(apply_event(page, event, trace={"fileFixtures": {}}))

    # form.files is present but empty -> no payload to install, fall back to dispatch.
    assert page.fake_locator.input_files == []
    assert page.fake_locator.dispatched == ["change"]


class FakeClickLocator:
    def __init__(self, exists: bool):
        self._count = 1 if exists else 0
        self.clicked = False
        self.first = self

    async def count(self):
        return self._count

    async def click(self):
        if self._count == 0:
            raise AssertionError("clicked a locator with count=0")
        self.clicked = True


class FakeMouse:
    def __init__(self):
        self.clicks: list[tuple[float, float]] = []

    async def click(self, x, y):
        self.clicks.append((x, y))

    async def move(self, x, y):
        pass


class FakeClickPage:
    def __init__(self, selector_exists: bool):
        self.locator_obj = FakeClickLocator(exists=selector_exists)
        self.mouse = FakeMouse()
        self.requested_selectors: list[str] = []

    def locator(self, selector):
        self.requested_selectors.append(selector)
        return self.locator_obj


def test_apply_click_event_prefers_selector_hint_over_raw_coordinates():
    """Walkthrough finding (2026-05-01): the simple-trace golden 'passed'
    only because capture and replay both missed the target. Replay's click
    must route through selectorHint when the element is present, so the
    button actually gets clicked instead of clicking a (95, 85) point in
    empty space."""
    from harness.replay import apply_event

    page = FakeClickPage(selector_exists=True)
    event = {
        "type": "click",
        "target": {"selectorHint": "#incrementBtn"},
        "pointer": {"x": 95, "y": 85},
    }

    asyncio.run(apply_event(page, event, trace={}))

    assert page.locator_obj.clicked is True
    assert page.mouse.clicks == [], "must not fall back to raw coords when selector hits"
    assert page.requested_selectors == ["#incrementBtn"]


def test_apply_click_event_falls_back_to_coords_when_selector_missing():
    """Canvas / svg clicks have no selectorHint pointing at a real element.
    Coordinate fallback keeps those traces replayable."""
    from harness.replay import apply_event

    page = FakeClickPage(selector_exists=False)
    event = {
        "type": "click",
        "target": {"selectorHint": "#noSuchElement"},
        "pointer": {"x": 80, "y": 120},
    }

    asyncio.run(apply_event(page, event, trace={}))

    assert page.locator_obj.clicked is False
    assert page.mouse.clicks == [(80, 120)]


def test_apply_click_event_falls_back_to_coords_when_no_selector_hint():
    """Pre-selector traces (or events on text nodes) have no hint at all."""
    from harness.replay import apply_event

    page = FakeClickPage(selector_exists=False)
    event = {
        "type": "click",
        "target": {"tag": "div"},  # no selectorHint
        "pointer": {"x": 50, "y": 50},
    }

    asyncio.run(apply_event(page, event, trace={}))

    assert page.mouse.clicks == [(50, 50)]
    # locator() must not even be called when there's no hint
    assert page.requested_selectors == []


def test_resolve_volatile_fields_uses_trace_when_no_override():
    trace = {"session": {"volatileFields": ["a", "b"]}}

    assert resolve_volatile_fields(trace, override=None) == ["a", "b"]


def test_resolve_volatile_fields_override_replaces_trace_list():
    trace = {"session": {"volatileFields": ["frozen.policy"]}}

    assert resolve_volatile_fields(trace, override=["live.policy"]) == ["live.policy"]


def test_resolve_volatile_fields_extra_appends_to_base():
    trace = {"session": {"volatileFields": ["a"]}}

    assert resolve_volatile_fields(trace, override=None, extra=["b", "c"]) == ["a", "b", "c"]


def test_resolve_volatile_fields_override_combines_with_extra():
    trace = {"session": {"volatileFields": ["frozen"]}}

    assert resolve_volatile_fields(
        trace, override=["live"], extra=["explicit"]
    ) == ["live", "explicit"]


def test_resolve_volatile_fields_empty_override_disables_trace_policy():
    trace = {"session": {"volatileFields": ["frozen.policy"]}}

    # override=[] is the explicit "no policy" signal — it must not fall
    # through to the trace's frozen list.
    assert resolve_volatile_fields(trace, override=[]) == []


def test_resolve_volatile_fields_handles_missing_session():
    assert resolve_volatile_fields({}, override=None) == []
    assert resolve_volatile_fields({}, override=None, extra=["x"]) == ["x"]
