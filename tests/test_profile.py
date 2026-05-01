import json
from pathlib import Path

import pytest

from harness.profile import Profile, load_profile, parse_profile


def write_profile(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "harness.profile.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_parse_profile_applies_defaults():
    source = Path("/fake/harness.profile.json")

    profile = parse_profile({"name": "simple"}, source)

    assert profile.name == "simple"
    assert profile.startup_path == "/"
    assert profile.host == "127.0.0.1"
    assert profile.port == 6173
    assert profile.state_globals == ("state",)
    assert profile.volatile_fields == ()


def test_parse_profile_resolves_root_relative_to_source():
    source = Path("/fake/dir/harness.profile.json")

    profile = parse_profile({"name": "x", "root": "../target"}, source)

    assert profile.root == Path("/fake/target").resolve()


def test_parse_profile_overrides_all_fields():
    source = Path("/fake/harness.profile.json")

    profile = parse_profile(
        {
            "name": "claude",
            "root": ".",
            "startupPath": "/index.html",
            "host": "0.0.0.0",
            "port": 7000,
            "stateGlobals": ["state", "appState"],
            "volatileFields": ["debugTiming.value.frameMs"],
            "debugMethods": ["snapshot", "mesh", "slots"],
            "consoleIgnorePatterns": ["CONTEXT_LOST_WEBGL", "GroupMarkerNotSet"],
        },
        source,
    )

    assert profile.host == "0.0.0.0"
    assert profile.port == 7000
    assert profile.startup_path == "/index.html"
    assert profile.state_globals == ("state", "appState")
    assert profile.volatile_fields == ("debugTiming.value.frameMs",)
    assert profile.debug_methods == ("snapshot", "mesh", "slots")
    assert profile.console_ignore_patterns == ("CONTEXT_LOST_WEBGL", "GroupMarkerNotSet")


def test_parse_profile_defaults_inspector_fields():
    profile = parse_profile({"name": "x"}, Path("/fake/harness.profile.json"))
    assert profile.debug_methods == ("snapshot", "actionLog", "errors", "timing")
    assert profile.console_ignore_patterns == ()


def test_parse_profile_defaults_passive_probes_off():
    profile = parse_profile({"name": "x"}, Path("/fake/harness.profile.json"))
    pp = profile.passive_probes
    assert pp.dom_snapshot is False
    assert pp.dom_selectors == ()
    assert pp.storage is False
    assert pp.window_globals_scan is False
    assert pp.network is False


def test_parse_profile_reads_passive_probes_block():
    profile = parse_profile(
        {
            "name": "x",
            "passiveProbes": {
                "domSnapshot": True,
                "domSelectors": ["#status", "[data-testid=count]"],
                "storage": True,
                "windowGlobalsScan": True,
                "network": True,
            },
        },
        Path("/fake/harness.profile.json"),
    )
    pp = profile.passive_probes
    assert pp.dom_snapshot is True
    assert pp.dom_selectors == ("#status", "[data-testid=count]")
    assert pp.storage is True
    assert pp.window_globals_scan is True
    assert pp.network is True


def test_parse_profile_rejects_missing_name():
    with pytest.raises(ValueError, match="missing required field: name"):
        parse_profile({}, Path("/fake/harness.profile.json"))


def test_load_profile_reads_json_from_disk(tmp_path: Path):
    profile_path = write_profile(tmp_path, {"name": "simple", "port": 6200})

    profile = load_profile(profile_path)

    assert isinstance(profile, Profile)
    assert profile.name == "simple"
    assert profile.port == 6200
    assert profile.source_path == profile_path.resolve()
    assert profile.root == profile_path.parent.resolve()
