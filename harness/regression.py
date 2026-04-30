from __future__ import annotations

import json
from pathlib import Path

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


def run_report_regression(golden_trace: Path, golden_report: Path) -> list[str]:
    trace = json.loads(golden_trace.read_text(encoding="utf-8"))
    errors = validate_trace(trace)
    if errors:
        return errors
    replay_result = replay_trace(trace)
    if not replay_result.get("ok"):
        return [f"golden replay failed: {replay_result.get('firstFailure') or replay_result.get('error')}"]
    current_report = build_report_markdown(attach_replay_result(trace, replay_result))
    return compare_reports(current_report, golden_report.read_text(encoding="utf-8"))
