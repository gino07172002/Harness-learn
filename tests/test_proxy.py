from pathlib import Path

from harness.proxy import build_injected_html, resolve_target_path


def test_resolve_target_path_allows_files_under_target(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()
    index = target / "index.html"
    index.write_text("<html></html>", encoding="utf-8")

    resolved = resolve_target_path(target, "/index.html")

    assert resolved == index.resolve()


def test_resolve_target_path_blocks_directory_escape(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()

    try:
        resolve_target_path(target, "/../secret.txt")
    except PermissionError as exc:
        assert "outside target root" in str(exc)
    else:
        raise AssertionError("Expected PermissionError")


def test_build_injected_html_inserts_client_before_body_close():
    html = "<!doctype html><html><body><h1>Target</h1></body></html>"

    injected = build_injected_html(html, target_name="demo")

    assert "<script" in injected
    assert "/__harness__/client.js" in injected
    assert "window.__HARNESS_BOOTSTRAP__" in injected
    assert injected.index("/__harness__/client.js") < injected.index("</body>")


def test_build_injected_html_embeds_inspector_config_in_bootstrap():
    html = "<!doctype html><html><body></body></html>"

    injected = build_injected_html(
        html,
        target_name="claude",
        debug_methods=("snapshot", "mesh"),
        state_globals=("state", "appState"),
        console_ignore_patterns=("CONTEXT_LOST_WEBGL",),
    )

    assert '"debugMethods": ["snapshot", "mesh"]' in injected
    assert '"stateGlobals": ["state", "appState"]' in injected
    assert '"consoleIgnorePatterns": ["CONTEXT_LOST_WEBGL"]' in injected
