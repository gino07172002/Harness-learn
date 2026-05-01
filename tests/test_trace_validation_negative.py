from pathlib import Path

import pytest

from harness.trace_validation import load_trace, validate_trace


INVALID_DIR = Path("examples/golden/invalid")


def _cases() -> list[tuple[Path, Path]]:
    pairs = []
    for json_path in sorted(INVALID_DIR.glob("*.json")):
        expected_path = json_path.with_suffix(".expected.txt")
        pairs.append((json_path, expected_path))
    return pairs


@pytest.mark.parametrize("json_path,expected_path", _cases(), ids=lambda p: p.name)
def test_invalid_golden_produces_expected_messages(json_path: Path, expected_path: Path):
    expected_messages = [
        line.strip()
        for line in expected_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    errors = validate_trace(load_trace(json_path))
    for message in expected_messages:
        assert message in errors, (
            f"{json_path.name}: expected error {message!r} not found in {errors}"
        )


def test_negative_corpus_is_non_empty():
    assert _cases(), "expected at least one invalid golden fixture"
