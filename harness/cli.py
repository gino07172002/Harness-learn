from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def resolve_target_settings(args: argparse.Namespace, *, require_target: bool = True) -> dict[str, Any]:
    from harness.profile import load_profile

    profile = load_profile(args.profile) if getattr(args, "profile", None) else None

    def pick(attr: str, profile_value: Any, fallback: Any) -> Any:
        cli_value = getattr(args, attr, None)
        if cli_value is not None:
            return cli_value
        return profile_value if profile is not None else fallback

    target = pick("target", profile.root if profile else None, None)
    target_name = pick("target_name", profile.name if profile else None, "target")
    host = pick("host", profile.host if profile else None, "127.0.0.1")
    port = pick("port", profile.port if profile else None, 6173)

    if require_target and target is None:
        raise SystemExit("error: --target is required (or pass --profile)")
    passive_probes_dict = None
    if profile is not None:
        pp = profile.passive_probes
        passive_probes_dict = {
            "domSnapshot": pp.dom_snapshot,
            "domSelectors": list(pp.dom_selectors),
            "storage": pp.storage,
            "windowGlobalsScan": pp.window_globals_scan,
            "network": pp.network,
        }
    environment_capture_dict = None
    if profile is not None:
        env = profile.environment_capture
        environment_capture_dict = {
            "localStorage": {
                "mode": env.local_storage.mode,
                "keys": list(env.local_storage.keys),
            },
            "sessionStorage": {
                "mode": env.session_storage.mode,
                "keys": list(env.session_storage.keys),
            },
            "maxValueBytes": env.max_value_bytes,
        }
    file_capture_dict = None
    if profile is not None:
        fc = profile.file_capture
        file_capture_dict = {
            "mode": fc.mode,
            "selectors": list(fc.selectors),
            "maxFileBytes": fc.max_file_bytes,
            "maxFiles": fc.max_files,
        }
    return {
        "target": target,
        "target_name": target_name,
        "host": host,
        "port": port,
        "debug_methods": profile.debug_methods if profile else None,
        "state_globals": profile.state_globals if profile else None,
        "console_ignore_patterns": profile.console_ignore_patterns if profile else None,
        "volatile_fields": profile.volatile_fields if profile else None,
        "passive_probes": passive_probes_dict,
        "environment_capture": environment_capture_dict,
        "file_capture": file_capture_dict,
    }


def build_server_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zero-mod browser debug harness server")
    parser.add_argument("--profile", type=Path, help="Path to a harness.profile.json (defaults sourced from it)")
    parser.add_argument("--target", type=Path, help="Target app directory to serve read-only")
    parser.add_argument("--target-name", help="Human-readable target name")
    parser.add_argument("--port", type=int, help="Proxy server port")
    parser.add_argument("--host", help="Proxy server host")
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
    parser.add_argument("--profile", type=Path, help="Path to a harness.profile.json (defaults sourced from it)")
    parser.add_argument("--target", type=Path, help="Target app directory to verify")
    parser.add_argument("--port", type=int, help="Port to check")
    parser.add_argument("--host", help="Host to check")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def build_validate_trace_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a harness trace JSON file")
    parser.add_argument("trace", type=Path, help="Trace JSON file")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Promote schema warnings to errors (e.g. unknown fields, unrecognized event types)",
    )
    return parser


def build_regress_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run golden trace regression")
    parser.add_argument("--golden", type=Path, required=True, help="Golden trace JSON path")
    parser.add_argument("--report", type=Path, help="Golden report Markdown path")
    parser.add_argument("--profile", type=Path, default=Path("examples/targets/simple/harness.profile.json"), help="Path to a harness.profile.json (defaults sourced from it)")
    parser.add_argument("--target", type=Path, help="Target directory (overrides profile)")
    parser.add_argument("--target-name", help="Target name (overrides profile)")
    parser.add_argument("--host", help="Fixture server host (overrides profile)")
    parser.add_argument("--port", type=int, help="Fixture server port (overrides profile)")
    parser.add_argument("--no-server", action="store_true", help="Skip starting a fixture server (assume one is already running)")
    parser.add_argument("--server-startup-timeout", type=float, default=15.0, help="Seconds to wait for the fixture server to become healthy")
    return parser


def server_main() -> int:
    from harness.proxy import run_proxy_server

    parser = build_server_parser()
    args = parser.parse_args()
    settings = resolve_target_settings(args)
    run_proxy_server(
        settings["target"],
        settings["target_name"],
        settings["host"],
        settings["port"],
        debug_methods=settings["debug_methods"],
        state_globals=settings["state_globals"],
        console_ignore_patterns=settings["console_ignore_patterns"],
        volatile_fields=settings["volatile_fields"],
        passive_probes=settings["passive_probes"],
        environment_capture=settings["environment_capture"],
        file_capture=settings["file_capture"],
    )
    return 0


def replay_main() -> int:
    import json
    from harness.replay import attach_replay_result, build_replay_completed_event, replay_trace
    from harness.run_log import RunLogger

    parser = build_replay_parser()
    args = parser.parse_args()
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    logger = RunLogger(args.run_log.parent, run_id=args.run_log.stem) if args.run_log else None

    if logger is not None:
        with logger.timed("replay.completed", trace=str(args.trace)) as completion:
            result = replay_trace(trace, headed=args.headed)
            completion.update(build_replay_completed_event(result))
    else:
        result = replay_trace(trace, headed=args.headed)

    args.trace.write_text(json.dumps(attach_replay_result(trace, result), indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def report_main() -> int:
    import json
    from harness.report import build_report_generated_event, build_report_markdown
    from harness.run_log import RunLogger

    parser = build_report_parser()
    args = parser.parse_args()
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    logger = RunLogger(args.run_log.parent, run_id=args.run_log.stem) if args.run_log else None
    report_path = str(args.out) if args.out else "<stdout>"

    if logger is not None:
        with logger.timed("report.generated", trace=str(args.trace)) as completion:
            markdown = build_report_markdown(trace)
            completion.update(build_report_generated_event(report_path))
    else:
        markdown = build_report_markdown(trace)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    return 0


def doctor_main() -> int:
    from harness.doctor import render_doctor_json, render_doctor_text, run_doctor_checks

    parser = build_doctor_parser()
    args = parser.parse_args()
    settings = resolve_target_settings(args)
    results = run_doctor_checks(
        settings["target"],
        settings["port"],
        settings["host"],
        volatile_fields=settings.get("volatile_fields"),
    )
    print(render_doctor_json(results) if args.json else render_doctor_text(results), end="")
    return 0 if all(result.ok for result in results) else 1


def validate_trace_main() -> int:
    from harness.trace_validation import load_trace, validate_trace_with_warnings

    parser = build_validate_trace_parser()
    args = parser.parse_args()
    outcome = validate_trace_with_warnings(load_trace(args.trace))

    errors = list(outcome.errors)
    warnings = list(outcome.warnings)

    if args.strict:
        errors = errors + warnings
        warnings = []

    if errors:
        for error in errors:
            print(error)
        if warnings:
            print("warnings:")
            for warning in warnings:
                print(f"  {warning}")
        return 1

    if warnings:
        print("warnings:")
        for warning in warnings:
            print(f"  {warning}")
    print(f"Trace valid: {args.trace}")
    return 0


def regress_main() -> int:
    from contextlib import nullcontext

    from harness.regression import managed_fixture_server, run_report_regression

    parser = build_regress_parser()
    args = parser.parse_args()
    golden_report = args.report or args.golden.with_name(args.golden.stem.replace("-trace", "-report") + ".md")
    settings = resolve_target_settings(args, require_target=not args.no_server)

    if args.no_server:
        server_ctx = nullcontext()
    else:
        server_ctx = managed_fixture_server(
            target=settings["target"],
            target_name=settings["target_name"],
            host=settings["host"],
            port=settings["port"],
            startup_timeout=args.server_startup_timeout,
        )

    with server_ctx:
        errors = run_report_regression(args.golden, golden_report)

    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Golden regression passed: {args.golden}")
    return 0
