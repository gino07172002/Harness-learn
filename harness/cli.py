from __future__ import annotations

import argparse
from pathlib import Path


def build_server_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zero-mod browser debug harness server")
    parser.add_argument("--target", type=Path, required=True, help="Target app directory to serve read-only")
    parser.add_argument("--target-name", default="target", help="Human-readable target name")
    parser.add_argument("--port", type=int, default=6173, help="Proxy server port")
    parser.add_argument("--host", default="127.0.0.1", help="Proxy server host")
    return parser


def build_replay_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay a captured harness trace")
    parser.add_argument("trace", type=Path, help="Trace JSON file")
    parser.add_argument("--headed", action="store_true", help="Run Chromium in headed mode")
    parser.add_argument("--run-log", type=Path, help="Optional JSONL run log path")
    return parser


def build_report_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Markdown report from a harness trace")
    parser.add_argument("trace", type=Path, help="Trace JSON file")
    parser.add_argument("--out", type=Path, help="Output Markdown path")
    parser.add_argument("--run-log", type=Path, help="Optional JSONL run log path")
    return parser


def build_doctor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether the harness can run on this machine")
    parser.add_argument("--target", type=Path, required=True, help="Target app directory to verify")
    parser.add_argument("--port", type=int, default=6173, help="Port to check")
    parser.add_argument("--host", default="127.0.0.1", help="Host to check")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def build_validate_trace_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a harness trace JSON file")
    parser.add_argument("trace", type=Path, help="Trace JSON file")
    return parser


def build_regress_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run golden trace regression")
    parser.add_argument("--golden", type=Path, required=True, help="Golden trace JSON path")
    parser.add_argument("--report", type=Path, help="Golden report Markdown path")
    return parser


def server_main() -> int:
    from harness.proxy import run_proxy_server

    parser = build_server_parser()
    args = parser.parse_args()
    run_proxy_server(args.target, args.target_name, args.host, args.port)
    return 0


def replay_main() -> int:
    import json
    from harness.replay import attach_replay_result, build_replay_completed_event, replay_trace
    from harness.run_log import RunLogger

    parser = build_replay_parser()
    args = parser.parse_args()
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    result = replay_trace(trace, headed=args.headed)
    args.trace.write_text(json.dumps(attach_replay_result(trace, result), indent=2), encoding="utf-8")
    if args.run_log:
        logger = RunLogger(args.run_log.parent, run_id=args.run_log.stem)
        logger.record("replay.completed", **build_replay_completed_event(result))
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def report_main() -> int:
    import json
    from harness.report import build_report_generated_event, build_report_markdown
    from harness.run_log import RunLogger

    parser = build_report_parser()
    args = parser.parse_args()
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    markdown = build_report_markdown(trace)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    if args.run_log:
        logger = RunLogger(args.run_log.parent, run_id=args.run_log.stem)
        report_path = str(args.out) if args.out else "<stdout>"
        logger.record("report.generated", **build_report_generated_event(report_path))
    return 0


def doctor_main() -> int:
    from harness.doctor import render_doctor_json, render_doctor_text, run_doctor_checks

    parser = build_doctor_parser()
    args = parser.parse_args()
    results = run_doctor_checks(args.target, args.port, args.host)
    print(render_doctor_json(results) if args.json else render_doctor_text(results), end="")
    return 0 if all(result.ok for result in results) else 1


def validate_trace_main() -> int:
    from harness.trace_validation import load_trace, validate_trace

    parser = build_validate_trace_parser()
    args = parser.parse_args()
    errors = validate_trace(load_trace(args.trace))
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Trace valid: {args.trace}")
    return 0


def regress_main() -> int:
    from harness.regression import run_report_regression

    parser = build_regress_parser()
    args = parser.parse_args()
    golden_report = args.report or args.golden.with_name(args.golden.stem.replace("-trace", "-report") + ".md")
    errors = run_report_regression(args.golden, golden_report)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Golden regression passed: {args.golden}")
    return 0
