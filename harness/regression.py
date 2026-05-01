from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.error import URLError
from urllib.request import urlopen

from harness.replay import attach_replay_result, replay_trace
from harness.report import build_report_markdown
from harness.trace_validation import validate_trace


def normalize_report_markdown(markdown: str) -> str:
    normalized_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("- Session:"):
            normalized_lines.append("- Session: <normalized>")
        elif line.startswith("- Proxy URL:"):
            normalized_lines.append("- Proxy URL: <normalized>")
        else:
            normalized_lines.append(line)
    return "\n".join(normalized_lines).strip() + "\n"


def compare_reports(current: str, golden: str) -> list[str]:
    if normalize_report_markdown(current) == normalize_report_markdown(golden):
        return []
    return ["normalized report differs from golden report"]


def _wait_for_http_ok(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1.0) as response:
                if 200 <= response.status < 500:
                    return
        except (URLError, ConnectionError, socket.timeout) as exc:
            last_error = exc
        time.sleep(0.2)
    raise TimeoutError(f"Fixture server at {url} did not become healthy within {timeout}s (last error: {last_error})")


@contextmanager
def managed_fixture_server(
    target: Path,
    target_name: str,
    host: str,
    port: int,
    startup_timeout: float = 15.0,
) -> Iterator[subprocess.Popen]:
    cmd = [
        sys.executable,
        "harness_server.py",
        "--target", str(target),
        "--target-name", target_name,
        "--host", host,
        "--port", str(port),
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _wait_for_http_ok(f"http://{host}:{port}/", startup_timeout)
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5.0)


def run_report_regression(
    golden_trace: Path,
    golden_report: Path,
    volatile_fields_override: list[str] | tuple[str, ...] | None = None,
    extra_volatile_fields: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    trace = json.loads(golden_trace.read_text(encoding="utf-8"))
    errors = validate_trace(trace)
    if errors:
        return errors
    replay_result = replay_trace(
        trace,
        volatile_fields_override=volatile_fields_override,
        extra_volatile_fields=extra_volatile_fields,
    )
    if not replay_result.get("ok"):
        return [f"golden replay failed: {replay_result.get('firstFailure') or replay_result.get('error')}"]
    current_report = build_report_markdown(attach_replay_result(trace, replay_result))
    return compare_reports(current_report, golden_report.read_text(encoding="utf-8"))
