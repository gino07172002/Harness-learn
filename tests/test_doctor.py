from pathlib import Path

from harness.doctor import CheckResult, check_target_path, check_writable_directory, render_doctor_text


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
