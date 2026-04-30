import json
from pathlib import Path

from harness.trace_store import TraceStore, make_trace_id


def test_make_trace_id_is_filename_safe():
    trace_id = make_trace_id()
    assert ":" not in trace_id
    assert "/" not in trace_id
    assert "\\" not in trace_id
    assert len(trace_id) >= 15


def test_trace_store_writes_json(tmp_path: Path):
    store = TraceStore(tmp_path)
    trace = {"version": 1, "events": [{"type": "click"}]}

    path = store.write_trace(trace, trace_id="example-trace")

    assert path == tmp_path / "example-trace.json"
    assert json.loads(path.read_text(encoding="utf-8")) == trace
