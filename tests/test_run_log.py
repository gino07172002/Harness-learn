import json
from pathlib import Path

from harness.run_log import RunLogger, make_run_id


def test_make_run_id_is_filename_safe():
    run_id = make_run_id()
    assert ":" not in run_id
    assert "/" not in run_id
    assert "\\" not in run_id
    assert len(run_id) >= 15


def test_run_logger_writes_jsonl_events(tmp_path: Path):
    logger = RunLogger(tmp_path, run_id="run-1")

    logger.record("proxy.started", port=6173, targetName="simple")
    logger.record("trace.saved", path="traces/example.json")

    lines = (tmp_path / "run-1.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["event"] == "proxy.started"
    assert json.loads(lines[0])["port"] == 6173
    assert json.loads(lines[1])["event"] == "trace.saved"


def test_timed_records_started_and_completed_with_duration(tmp_path: Path):
    logger = RunLogger(tmp_path, run_id="run-timed")

    with logger.timed("replay.completed", trace="x") as completion:
        completion["ok"] = True
        completion["completedEvents"] = 3

    lines = (tmp_path / "run-timed.jsonl").read_text(encoding="utf-8").splitlines()
    started = json.loads(lines[0])
    completed = json.loads(lines[1])
    assert started["event"] == "replay.started"
    assert started["trace"] == "x"
    assert completed["event"] == "replay.completed"
    assert "durationMs" in completed
    assert isinstance(completed["durationMs"], int)
    assert completed["ok"] is True
    assert completed["completedEvents"] == 3


def test_timed_records_duration_even_on_exception(tmp_path: Path):
    logger = RunLogger(tmp_path, run_id="run-fail")

    try:
        with logger.timed("replay.completed", trace="y"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    lines = (tmp_path / "run-fail.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["event"] == "replay.started"
    assert json.loads(lines[1])["event"] == "replay.completed"
    assert "durationMs" in json.loads(lines[1])
