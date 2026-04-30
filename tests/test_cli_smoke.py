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
