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
    return parser


def build_report_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Markdown report from a harness trace")
    parser.add_argument("trace", type=Path, help="Trace JSON file")
    parser.add_argument("--out", type=Path, help="Output Markdown path")
    return parser


def server_main() -> int:
    from harness.proxy import run_proxy_server

    parser = build_server_parser()
    args = parser.parse_args()
    run_proxy_server(args.target, args.target_name, args.host, args.port)
    return 0


def replay_main() -> int:
    parser = build_replay_parser()
    args = parser.parse_args()
    print(f"Replay entry parsed trace={args.trace} headed={args.headed}")
    return 0


def report_main() -> int:
    parser = build_report_parser()
    args = parser.parse_args()
    print(f"Report entry parsed trace={args.trace} out={args.out}")
    return 0
