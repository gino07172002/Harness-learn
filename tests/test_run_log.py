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
