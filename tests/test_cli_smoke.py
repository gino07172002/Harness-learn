import subprocess
import sys


def run_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, script_name, *args],
        cwd=".",
        text=True,
        capture_output=True,
        check=False,
    )


def test_harness_server_help_exits_successfully():
    result = run_script("harness_server.py", "--help")
    assert result.returncode == 0
    assert "Zero-mod browser debug harness server" in result.stdout


def test_replay_runner_help_exits_successfully():
    result = run_script("replay_runner.py", "--help")
    assert result.returncode == 0
    assert "Replay a captured harness trace" in result.stdout


def test_report_generator_help_exits_successfully():
    result = run_script("report_generator.py", "--help")
    assert result.returncode == 0
    assert "Generate a Markdown report from a harness trace" in result.stdout


def test_harness_doctor_help_exits_successfully():
    result = run_script("harness_doctor.py", "--help")
    assert result.returncode == 0
    assert "Check whether the harness can run on this machine" in result.stdout


def test_harness_validate_trace_help_exits_successfully():
    result = run_script("harness_validate_trace.py", "--help")
    assert result.returncode == 0
    assert "Validate a harness trace JSON file" in result.stdout


def test_harness_regress_help_exits_successfully():
    result = run_script("harness_regress.py", "--help")
    assert result.returncode == 0
    assert "Run golden trace regression" in result.stdout


def test_replay_runner_accepts_profile_and_volatile_field_flags():
    """Codex review (post 7a263df / c96b266): the architecture decision is
    that profile is the source of truth at comparison time, but replay used
    to read only trace.session.volatileFields. The CLI must surface the
    override knob so a user can re-diff old traces under a new policy."""
    result = run_script("replay_runner.py", "--help")
    assert result.returncode == 0
    assert "--profile" in result.stdout
    assert "--volatile-field" in result.stdout


def test_harness_regress_accepts_volatile_override_flags():
    result = run_script("harness_regress.py", "--help")
    assert result.returncode == 0
    assert "--volatile-field" in result.stdout
    assert "--ignore-trace-volatile-fields" in result.stdout


def test_validate_trace_strict_passes_realistic_session_fixture():
    """Strict mode promotes warnings to errors. A realistic fixture that
    includes the live session fields, capture:save snapshot reason, and
    the environmentFixture / fileFixtures top-level objects must pass."""
    result = run_script(
        "harness_validate_trace.py",
        "--strict",
        "examples/golden/realistic-session-trace.json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Trace valid" in result.stdout
    assert "warnings:" not in result.stdout
