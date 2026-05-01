from __future__ import annotations

import html
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from harness.run_log import RunLogger
from harness.trace_store import TraceStore


CLIENT_ROUTE = "/__harness__/client.js"


def resolve_target_path(target_root: Path, request_path: str) -> Path:
    root = target_root.resolve()
    parsed_path = unquote(urlparse(request_path).path)
    relative = parsed_path.lstrip("/") or "index.html"
    candidate = (root / relative).resolve()
    if root != candidate and root not in candidate.parents:
        raise PermissionError(f"Request path resolves outside target root: {request_path}")
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def build_injected_html(
    html_text: str,
    target_name: str,
    harness_run_id: str | None = None,
    debug_methods: tuple[str, ...] | list[str] | None = None,
    state_globals: tuple[str, ...] | list[str] | None = None,
    console_ignore_patterns: tuple[str, ...] | list[str] | None = None,
    volatile_fields: tuple[str, ...] | list[str] | None = None,
    passive_probes: dict | None = None,
    environment_capture: dict | None = None,
) -> str:
    bootstrap = {
        "version": 1,
        "targetName": target_name,
        "harnessRunId": harness_run_id,
        "debugMethods": list(debug_methods) if debug_methods is not None else None,
        "stateGlobals": list(state_globals) if state_globals is not None else None,
        "consoleIgnorePatterns": list(console_ignore_patterns) if console_ignore_patterns is not None else None,
        "volatileFields": list(volatile_fields) if volatile_fields is not None else None,
        "passiveProbes": passive_probes,
        "environmentCapture": environment_capture,
    }
    script = (
        "<script>"
        f"window.__HARNESS_BOOTSTRAP__ = {json.dumps(bootstrap)};"
        "</script>"
        f'<script src="{CLIENT_ROUTE}"></script>'
    )
    lower = html_text.lower()
    body_index = lower.rfind("</body>")
    if body_index == -1:
        return html_text + script
    return html_text[:body_index] + script + html_text[body_index:]


class HarnessProxyHandler(BaseHTTPRequestHandler):
    target_root: Path
    target_name: str
    client_path: Path
    trace_store: TraceStore
    run_logger: RunLogger
    run_id: str
    debug_methods: tuple[str, ...] | None = None
    state_globals: tuple[str, ...] | None = None
    console_ignore_patterns: tuple[str, ...] | None = None
    volatile_fields: tuple[str, ...] | None = None
    passive_probes: dict | None = None
    environment_capture: dict | None = None

    def do_GET(self) -> None:
        if urlparse(self.path).path == CLIENT_ROUTE:
            self.run_logger.record("client.served", path=CLIENT_ROUTE)
            self._send_file(self.client_path, "application/javascript", inject=False)
            return

        try:
            target_path = resolve_target_path(self.target_root, self.path)
        except PermissionError as exc:
            self.send_error(403, str(exc))
            return

        if not target_path.exists() or not target_path.is_file():
            self.send_error(404, f"Not found: {html.escape(self.path)}")
            return

        content_type = mimetypes.guess_type(target_path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/html"):
            self.run_logger.record(
                "html.injected",
                path=str(target_path.relative_to(self.target_root.resolve())),
            )
        self._send_file(target_path, content_type, inject=content_type.startswith("text/html"))

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/__harness__/trace":
            self.send_error(404, f"Not found: {html.escape(self.path)}")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        try:
            trace = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.send_error(400, f"Invalid JSON: {exc}")
            return

        trace.setdefault("session", {})["harnessRunId"] = self.run_id
        self.run_logger.record(
            "trace.received",
            eventCount=len(trace.get("events", [])),
            snapshotCount=len(trace.get("snapshots", [])),
        )
        path = self.trace_store.write_trace(trace)
        self.run_logger.record("trace.saved", path=str(path))
        response = json.dumps({"ok": True, "path": str(path)}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _send_file(self, path: Path, content_type: str, inject: bool) -> None:
        data = path.read_bytes()
        if inject:
            text = data.decode("utf-8")
            data = build_injected_html(
                text,
                self.target_name,
                self.run_id,
                debug_methods=self.debug_methods,
                state_globals=self.state_globals,
                console_ignore_patterns=self.console_ignore_patterns,
                volatile_fields=self.volatile_fields,
                passive_probes=self.passive_probes,
                environment_capture=self.environment_capture,
            ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_proxy_server(
    target_root: Path,
    target_name: str,
    host: str,
    port: int,
    debug_methods: tuple[str, ...] | None = None,
    state_globals: tuple[str, ...] | None = None,
    console_ignore_patterns: tuple[str, ...] | None = None,
    volatile_fields: tuple[str, ...] | None = None,
    passive_probes: dict | None = None,
    environment_capture: dict | None = None,
) -> None:
    client_path = Path(__file__).parent / "static" / "harness_client.js"
    trace_store = TraceStore(Path("traces"))
    run_logger = RunLogger(Path("runs"))
    run_logger.record("proxy.started", port=port, host=host, targetName=target_name, targetRoot=str(target_root))

    class ConfiguredHarnessProxyHandler(HarnessProxyHandler):
        pass

    ConfiguredHarnessProxyHandler.target_root = target_root
    ConfiguredHarnessProxyHandler.target_name = target_name
    ConfiguredHarnessProxyHandler.client_path = client_path
    ConfiguredHarnessProxyHandler.trace_store = trace_store
    ConfiguredHarnessProxyHandler.run_logger = run_logger
    ConfiguredHarnessProxyHandler.run_id = run_logger.run_id
    ConfiguredHarnessProxyHandler.debug_methods = debug_methods
    ConfiguredHarnessProxyHandler.state_globals = state_globals
    ConfiguredHarnessProxyHandler.console_ignore_patterns = console_ignore_patterns
    ConfiguredHarnessProxyHandler.volatile_fields = volatile_fields
    ConfiguredHarnessProxyHandler.passive_probes = passive_probes
    ConfiguredHarnessProxyHandler.environment_capture = environment_capture
    server = ThreadingHTTPServer((host, port), ConfiguredHarnessProxyHandler)
    print(f"Serving {target_root} as {target_name} at http://{host}:{port}")
    server.serve_forever()
