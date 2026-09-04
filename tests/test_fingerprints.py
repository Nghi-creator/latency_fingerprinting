"""Tests for the deterministic file-based fingerprint repository."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import latency_fingerprinting.fingerprints as fingerprints_module
from latency_fingerprinting.fingerprints import (
    FingerprintEntry,
    FingerprintRejectionReason,
    FingerprintRepository,
    FingerprintRepositoryError,
    load_fingerprint_repository,
)
from latency_fingerprinting.models import Fingerprint, ValidationStatus
from latency_fingerprinting.synthetic_fixtures import (
    DEFAULT_FIXTURE_DIRECTORY,
    SYNTHETIC_COMPATIBILITY_GROUP,
)

REFERENCE_DIRECTORY = DEFAULT_FIXTURE_DIRECTORY / "reference_cases"


def fingerprint_path(label: str) -> Path:
    return REFERENCE_DIRECTORY / label / "fingerprint.json"


def fingerprint_payload(label: str) -> dict[str, object]:
    return json.loads(fingerprint_path(label).read_text(encoding="utf-8"))


def write_payload(directory: Path, name: str, payload: object) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_three_reference_fingerprints_load_in_deterministic_id_order() -> None:
    repository = load_fingerprint_repository(REFERENCE_DIRECTORY)

    assert repository.is_clean
    assert [fingerprint.fingerprint_id for fingerprint in repository.fingerprints] == [
        "fingerprint-healthy-v1",
        "fingerprint-host_encoder_pressure-v1",
        "fingerprint-network_pressure-v1",
    ]
    assert [
        entry.path.relative_to(REFERENCE_DIRECTORY).as_posix() for entry in repository.entries
    ] == [
        "healthy/fingerprint.json",
        "host_encoder_pressure/fingerprint.json",
        "network_pressure/fingerprint.json",
    ]


def test_repository_filters_by_all_p0_compatibility_keys() -> None:
    repository = load_fingerprint_repository(REFERENCE_DIRECTORY)

    candidates = repository.compatible_candidates(
        compatibility_group=SYNTHETIC_COMPATIBILITY_GROUP,
        probe_type="stream_profile_relief",
    )
    assert candidates == repository.fingerprints
    assert (
        repository.compatible_candidates(
            compatibility_group="different-group",
            probe_type="stream_profile_relief",
        )
        == ()
    )
    assert (
        repository.compatible_candidates(
            compatibility_group=SYNTHETIC_COMPATIBILITY_GROUP,
            probe_type="unsupported-probe",
        )
        == ()
    )
    assert (
        repository.compatible_candidates(
            compatibility_group=SYNTHETIC_COMPATIBILITY_GROUP,
            probe_type="stream_profile_relief",
            contract_version="2.0.0",
        )
        == ()
    )


def test_repository_never_returns_rejected_fingerprint_as_candidate() -> None:
    repository = load_fingerprint_repository(REFERENCE_DIRECTORY)
    rejected = Fingerprint.model_validate(
        {
            **repository.entries[0].fingerprint.model_dump(),
            "validation_status": ValidationStatus.REJECTED,
        }
    )
    rejected_repository = FingerprintRepository(
        entries=(FingerprintEntry(path=repository.entries[0].path, fingerprint=rejected),)
    )

    assert (
        rejected_repository.compatible_candidates(
            compatibility_group=SYNTHETIC_COMPATIBILITY_GROUP,
            probe_type="stream_profile_relief",
        )
        == ()
    )


def test_repository_get_returns_one_fingerprint_or_none() -> None:
    repository = load_fingerprint_repository(REFERENCE_DIRECTORY)
    fingerprint = repository.get("fingerprint-network_pressure-v1")

    assert isinstance(fingerprint, Fingerprint)
    assert fingerprint.bottleneck_label == "network_pressure"
    assert repository.get("does-not-exist") is None


def test_flat_repository_supports_arbitrary_json_filenames(tmp_path: Path) -> None:
    write_payload(tmp_path, "network.json", fingerprint_payload("network_pressure"))
    write_payload(tmp_path, "encoder.json", fingerprint_payload("host_encoder_pressure"))

    repository = load_fingerprint_repository(tmp_path)
    assert [fingerprint.bottleneck_label for fingerprint in repository.fingerprints] == [
        "host_encoder_pressure",
        "network_pressure",
    ]


def test_named_fingerprint_discovery_ignores_other_case_json(tmp_path: Path) -> None:
    case_directory = tmp_path / "case"
    write_payload(case_directory, "fingerprint.json", fingerprint_payload("healthy"))
    write_payload(case_directory, "observation.json", {"not": "a fingerprint"})

    repository = load_fingerprint_repository(tmp_path)
    assert len(repository.fingerprints) == 1
    assert repository.fingerprints[0].bottleneck_label == "healthy"
    assert repository.rejections == ()


def test_corrupt_file_is_reported_and_strict_loading_fails(tmp_path: Path) -> None:
    write_payload(tmp_path, "healthy.json", fingerprint_payload("healthy"))
    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text("{not-json", encoding="utf-8")

    repository = load_fingerprint_repository(tmp_path, strict=False)
    assert len(repository.fingerprints) == 1
    assert len(repository.rejections) == 1
    assert repository.rejections[0].path == corrupt_path
    assert repository.rejections[0].reason is FingerprintRejectionReason.INVALID_JSON

    with pytest.raises(FingerprintRepositoryError, match="invalid_json") as raised:
        load_fingerprint_repository(tmp_path)
    assert raised.value.repository == repository


@pytest.mark.parametrize(
    ("change", "expected_reason"),
    [
        ({"schemaVersion": "fingerprint-v2"}, FingerprintRejectionReason.SCHEMA_VERSION_MISMATCH),
        ({"contractVersion": "2.0.0"}, FingerprintRejectionReason.CONTRACT_VERSION_MISMATCH),
    ],
)
def test_incompatible_versions_are_rejected(
    tmp_path: Path,
    change: dict[str, object],
    expected_reason: FingerprintRejectionReason,
) -> None:
    payload = fingerprint_payload("healthy")
    payload.update(change)
    write_payload(tmp_path, "fingerprint.json", payload)

    repository = load_fingerprint_repository(tmp_path, strict=False)
    assert repository.fingerprints == ()
    assert repository.rejections[0].reason is expected_reason
    assert repository.rejections[0].fingerprint_id == "fingerprint-healthy-v1"


@pytest.mark.parametrize("missing_field", ["schemaVersion", "contractVersion"])
def test_missing_root_version_is_rejected(tmp_path: Path, missing_field: str) -> None:
    payload = fingerprint_payload("healthy")
    del payload[missing_field]
    write_payload(tmp_path, "fingerprint.json", payload)

    repository = load_fingerprint_repository(tmp_path, strict=False)
    assert repository.rejections[0].reason is FingerprintRejectionReason.MISSING_VERSION


def test_non_object_and_contract_invalid_json_are_distinguished(tmp_path: Path) -> None:
    write_payload(tmp_path, "array.json", ["not", "an", "object"])
    invalid = fingerprint_payload("healthy")
    del invalid["context"]
    write_payload(tmp_path, "invalid.json", invalid)

    repository = load_fingerprint_repository(tmp_path, strict=False)
    assert [rejection.reason for rejection in repository.rejections] == [
        FingerprintRejectionReason.INVALID_ROOT,
        FingerprintRejectionReason.VALIDATION_ERROR,
    ]


def test_every_copy_of_a_duplicate_id_is_rejected(tmp_path: Path) -> None:
    payload = fingerprint_payload("network_pressure")
    first = write_payload(tmp_path, "a.json", payload)
    second = write_payload(tmp_path, "b.json", payload)

    repository = load_fingerprint_repository(tmp_path, strict=False)
    assert repository.fingerprints == ()
    assert [rejection.path for rejection in repository.rejections] == [first, second]
    assert all(
        rejection.reason is FingerprintRejectionReason.DUPLICATE_FINGERPRINT_ID
        for rejection in repository.rejections
    )


def test_mixed_repository_retains_only_non_duplicate_valid_entries(tmp_path: Path) -> None:
    duplicate = fingerprint_payload("network_pressure")
    write_payload(tmp_path, "a.json", duplicate)
    write_payload(tmp_path, "b.json", duplicate)
    write_payload(tmp_path, "healthy.json", fingerprint_payload("healthy"))

    repository = load_fingerprint_repository(tmp_path, strict=False)
    assert [fingerprint.bottleneck_label for fingerprint in repository.fingerprints] == ["healthy"]
    assert len(repository.rejections) == 2


def test_empty_repository_is_valid_and_paths_are_checked(tmp_path: Path) -> None:
    repository = load_fingerprint_repository(tmp_path)
    assert repository.is_clean
    assert repository.fingerprints == ()

    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        load_fingerprint_repository(missing)

    file_path = tmp_path / "not-a-directory.json"
    file_path.write_text("{}", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        load_fingerprint_repository(file_path)


def test_repository_traversal_bounds_all_directory_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fingerprints_module, "MAX_FINGERPRINT_DIRECTORY_ENTRIES", 2)
    for index in range(3):
        (tmp_path / f"unrelated-{index}.txt").write_text("ignored", encoding="utf-8")

    with pytest.raises(ValueError, match="more than 2 directory entries"):
        load_fingerprint_repository(tmp_path)


def test_repository_traversal_has_a_depth_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fingerprints_module, "MAX_FINGERPRINT_DIRECTORY_DEPTH", 1)
    (tmp_path / "one" / "two").mkdir(parents=True)

    with pytest.raises(ValueError, match="maximum directory depth of 1"):
        load_fingerprint_repository(tmp_path)


def test_repository_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    rendered = json.dumps(fingerprint_payload("healthy"))
    path = tmp_path / "fingerprint.json"
    path.write_text(
        rendered.replace(
            '"schemaVersion": "fingerprint-v1"',
            '"schemaVersion": "fingerprint-v1", "schemaVersion": "fingerprint-v1"',
        ),
        encoding="utf-8",
    )

    repository = load_fingerprint_repository(tmp_path, strict=False)

    assert repository.fingerprints == ()
    assert repository.rejections[0].reason is FingerprintRejectionReason.INVALID_JSON
    assert "duplicate JSON object key" in repository.rejections[0].message


def test_repository_rejects_fingerprint_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text(json.dumps(fingerprint_payload("healthy")), encoding="utf-8")
    link = tmp_path / "fingerprint.json"
    link.symlink_to(source)

    repository = load_fingerprint_repository(tmp_path, strict=False)

    assert repository.fingerprints == ()
    assert repository.rejections[0].reason is FingerprintRejectionReason.UNSAFE_LINK
