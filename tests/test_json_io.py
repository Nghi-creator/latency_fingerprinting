"""Strict, bounded JSON boundary behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from latency_fingerprinting.json_io import load_json_file, read_bounded_text, strict_json_loads


@pytest.mark.parametrize(
    "payload",
    [
        '{"schemaVersion":"observation-v1","schemaVersion":"fingerprint-v1"}',
        '{"nested":{"value":1,"value":2}}',
    ],
)
def test_duplicate_json_keys_are_rejected_at_any_depth(payload: str) -> None:
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        strict_json_loads(payload)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_standard_non_finite_json_numbers_are_rejected(constant: str) -> None:
    with pytest.raises(ValueError, match="must be finite"):
        strict_json_loads(f'{{"value":{constant}}}')


def test_file_reads_are_bounded_and_accept_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    path.write_bytes(b"\xef\xbb\xbf{}")
    assert load_json_file(path) == {}

    with pytest.raises(ValueError, match="too large"):
        read_bounded_text(path, maximum_bytes=1)
