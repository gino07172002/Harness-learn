from pathlib import Path

from harness.doctor import (
    CheckResult,
    check_target_path,
    check_volatility_suppression,
    check_writable_directory,
    render_doctor_text,
)


def test_check_target_path_passes_for_directory_with_index(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "index.html").write_text("<html></html>", encoding="utf-8")

    result = check_target_path(target)

    assert result.name == "target.index_html"
    assert result.ok is True


def test_check_target_path_fails_for_missing_index(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()

    result = check_target_path(target)

    assert result.ok is False
    assert "index.html" in result.message


def test_check_writable_directory_creates_directory_and_writes_probe(tmp_path: Path):
    directory = tmp_path / "runs"

    result = check_writable_directory("runs.writable", directory)

    assert result.ok is True
    assert directory.exists()
    assert not any(directory.iterdir())


def test_render_doctor_text_summarizes_results():
    text = render_doctor_text([
        CheckResult("python.version", True, "Python 3.13"),
        CheckResult("port.available", False, "Port 6173 is already in use"),
    ])

    assert "HARNESS_DOCTOR" in text
    assert "ok: false" in text
    assert "python.version: ok" in text
    assert "port.available: fail - Port 6173 is already in use" in text


def test_volatility_suppression_passes_when_no_fields_declared():
    result = check_volatility_suppression(None)

    assert result.name == "volatility.suppression"
    assert result.ok is True


def test_volatility_suppression_passes_with_normal_field():
    result = check_volatility_suppression(["state.tickCount"])

    assert result.ok is True
    assert "1 volatile field" in result.message


def test_check_target_path_failure_includes_actionable_hint(tmp_path: Path):
    missing = tmp_path / "does-not-exist"

    result = check_target_path(missing)

    assert result.ok is False
    assert result.hint is not None
    assert "check --target" in result.hint


def test_check_writable_directory_failure_includes_hint(tmp_path: Path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")

    result = check_writable_directory("blocker.writable", blocker)

    assert result.ok is False
    assert result.hint is not None
    assert "permissions" in result.hint or "writable" in result.hint


def test_render_doctor_text_shows_hint_on_failure():
    from harness.doctor import render_doctor_text

    text = render_doctor_text([
        CheckResult(
            "chromium.launch",
            False,
            "Chromium could not launch",
            detail="Executable doesn't exist",
            duration_ms=312,
            hint="run `python -m playwright install chromium`",
        ),
    ])

    assert "fail - Chromium could not launch" in text
    assert "hint: run `python -m playwright install chromium`" in text
    assert "duration: 312 ms" in text


def test_render_doctor_text_summary_lists_failed_checks_when_any_fail():
    """Walkthrough finding (2026-05-01): a long ok=true block can hide a
    single fail in CI logs. The trailing SUMMARY line gives a one-shot
    verdict you can grep for or read off the tail."""
    from harness.doctor import render_doctor_text

    text = render_doctor_text([
        CheckResult("python.version", True, "Python 3.13"),
        CheckResult("port.available", False, "Port 6173 is already in use"),
        CheckResult("target.index_html", False, "Target path does not exist"),
    ])

    last_line = text.strip().splitlines()[-1]
    assert last_line == "SUMMARY: 2 failed (port.available, target.index_html), 1 ok"


def test_render_doctor_text_summary_says_all_passed_when_clean():
    from harness.doctor import render_doctor_text

    text = render_doctor_text([
        CheckResult("python.version", True, "Python 3.13"),
        CheckResult("port.available", True, "Port 6173 is available"),
    ])

    last_line = text.strip().splitlines()[-1]
    assert last_line == "SUMMARY: all 2 checks passed"


def test_render_doctor_text_shows_detail_on_success():
    from harness.doctor import render_doctor_text

    text = render_doctor_text([
        CheckResult(
            "playwright.import",
            True,
            "playwright importable",
            detail="playwright 1.51.0",
            duration_ms=84,
        ),
    ])

    assert "playwright.import: ok" in text
    assert "playwright 1.51.0" in text
    assert "84 ms" in text
