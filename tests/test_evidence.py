"""Tests for per-feature candidate evidence and distance reconstruction."""

from __future__ import annotations

import math
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel

from latency_fingerprinting.evidence import (
    DEFAULT_SUPPORT_RESIDUAL_THRESHOLD,
    EvidenceError,
    build_candidate_evidence,
)
from latency_fingerprinting.models import (
    Fingerprint,
    NormalizedFeature,
    NormalizedResponse,
    ObservationRecord,
)
from latency_fingerprinting.synthetic_fixtures import DEFAULT_FIXTURE_DIRECTORY

ModelT = TypeVar("ModelT", bound=BaseModel)


def load_model(model_type: type[ModelT], path: Path) -> ModelT:
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


def load_fingerprint(label: str) -> Fingerprint:
    return load_model(
        Fingerprint,
        DEFAULT_FIXTURE_DIRECTORY / "reference_cases" / label / "fingerprint.json",
    )


def load_query(case_name: str) -> NormalizedResponse:
    observation = load_model(
        ObservationRecord,
        DEFAULT_FIXTURE_DIRECTORY / "query_cases" / case_name / "observation.json",
    )
    return observation.normalized_response


def rebuild(model: ModelT, **changes: object) -> ModelT:
    payload = model.model_dump()
    payload.update(changes)
    return type(model).model_validate(payload)


def test_clear_network_query_produces_deterministic_supporting_evidence() -> None:
    query = load_query("similar_network")
    candidate = load_fingerprint("network_pressure")

    first = build_candidate_evidence(query, candidate)
    second = build_candidate_evidence(query, candidate)

    assert first == second
    assert [item.feature for item in first.evidence] == sorted(
        candidate.normalized_response.features
    )
    assert first.supporting_evidence == first.evidence
    assert first.conflicting_evidence == ()
    assert first.ignored_evidence == ()
    assert first.shared_feature_count == 4
    assert first.feature_coverage == 1.0
    assert first.missing_features == ()
    assert first.rejected_features == ()


def test_per_feature_contributions_reconstruct_weighted_distance() -> None:
    evidence = build_candidate_evidence(
        load_query("similar_network"), load_fingerprint("network_pressure")
    )
    reconstructed_sum = sum(
        item.weight * (item.observed_value - item.candidate_value) ** 2
        for item in evidence.evidence
    )
    reconstructed_distance = math.sqrt(reconstructed_sum / evidence.total_weight)

    assert evidence.weighted_squared_residual_sum == pytest.approx(reconstructed_sum)
    assert evidence.distance == pytest.approx(reconstructed_distance)
    assert evidence.distance == pytest.approx(math.sqrt(0.0042 / 4))


def test_conflicting_query_separates_small_and_large_residuals() -> None:
    evidence = build_candidate_evidence(
        load_query("conflicting"), load_fingerprint("network_pressure")
    )

    assert [item.feature for item in evidence.conflicting_evidence] == ["client.received_fps"]
    assert {item.feature for item in evidence.supporting_evidence} == {
        "client.received_bitrate_kbps",
        "transport.jitter_ms",
        "transport.packets_lost_delta",
    }
    conflict = evidence.conflicting_evidence[0]
    assert conflict.residual == pytest.approx(0.45)
    assert conflict.weighted_squared_residual == pytest.approx(0.45**2)


def test_support_threshold_is_explicit_and_configurable() -> None:
    query = load_query("conflicting")
    candidate = load_fingerprint("network_pressure")
    default = build_candidate_evidence(query, candidate)
    relaxed = build_candidate_evidence(query, candidate, support_residual_threshold=0.5)

    assert DEFAULT_SUPPORT_RESIDUAL_THRESHOLD == 0.25
    assert default.conflicting_evidence
    assert relaxed.conflicting_evidence == ()
    assert relaxed.supporting_evidence == relaxed.evidence


@pytest.mark.parametrize("threshold", [-0.01, float("nan"), float("inf")])
def test_invalid_support_threshold_is_rejected(threshold: float) -> None:
    with pytest.raises(ValueError, match="support_residual_threshold"):
        build_candidate_evidence(
            load_query("similar_network"),
            load_fingerprint("network_pressure"),
            support_residual_threshold=threshold,
        )


def test_missing_candidate_feature_reduces_coverage_without_imputation() -> None:
    query = load_query("similar_network")
    features = dict(query.features)
    del features["transport.packets_lost_delta"]
    query = rebuild(
        query,
        features=features,
        missing_features=["transport.packets_lost_delta"],
    )

    evidence = build_candidate_evidence(query, load_fingerprint("network_pressure"))

    assert evidence.shared_feature_count == 3
    assert evidence.feature_coverage == 0.75
    assert evidence.missing_features == ("transport.packets_lost_delta",)
    assert all(item.feature != "transport.packets_lost_delta" for item in evidence.evidence)


def test_rejected_candidate_feature_is_reported_separately() -> None:
    query = load_query("similar_network")
    features = dict(query.features)
    del features["transport.packets_lost_delta"]
    query = rebuild(
        query,
        features=features,
        rejected_features={"transport.packets_lost_delta": "counter reset"},
    )

    evidence = build_candidate_evidence(query, load_fingerprint("network_pressure"))

    assert evidence.feature_coverage == 0.75
    assert evidence.missing_features == ()
    assert evidence.rejected_features == ("transport.packets_lost_delta",)


def test_query_only_feature_does_not_reduce_candidate_coverage() -> None:
    query = load_query("similar_network")
    features = {
        **query.features,
        "future.capture_queue_ms": NormalizedFeature(
            value=0.1,
            epsilon=0.1,
            reference_value=5,
        ),
    }
    query = rebuild(query, features=features)

    evidence = build_candidate_evidence(query, load_fingerprint("network_pressure"))
    assert evidence.shared_feature_count == 4
    assert evidence.feature_coverage == 1.0


def test_zero_weight_feature_is_audited_but_does_not_affect_distance() -> None:
    candidate = load_fingerprint("network_pressure")
    weights = dict(candidate.feature_weights)
    weights["client.received_fps"] = 0.0
    candidate = rebuild(candidate, feature_weights=weights)

    evidence = build_candidate_evidence(load_query("conflicting"), candidate)

    assert [item.feature for item in evidence.ignored_evidence] == ["client.received_fps"]
    assert all(item.feature != "client.received_fps" for item in evidence.conflicting_evidence)
    assert evidence.total_weight == 3.0
    expected_sum = sum(
        item.weighted_squared_residual
        for item in evidence.evidence
        if item.feature != "client.received_fps"
    )
    assert evidence.weighted_squared_residual_sum == pytest.approx(expected_sum)
    assert evidence.distance == pytest.approx(math.sqrt(expected_sum / 3))


def test_all_zero_weights_produce_degenerate_distance_without_division() -> None:
    candidate = load_fingerprint("network_pressure")
    candidate = rebuild(
        candidate,
        feature_weights={feature: 0.0 for feature in candidate.feature_weights},
    )

    evidence = build_candidate_evidence(load_query("similar_network"), candidate)

    assert evidence.total_weight == 0
    assert evidence.distance is None
    assert evidence.ignored_evidence == evidence.evidence


def test_invalid_query_is_an_analytical_error_for_evidence_stage() -> None:
    query = NormalizedResponse(
        features={},
        is_valid=False,
        invalid_reasons=["context_mismatch: contexts differ"],
    )
    with pytest.raises(EvidenceError, match="invalid query"):
        build_candidate_evidence(query, load_fingerprint("healthy"))


def test_evidence_builder_does_not_mutate_query_or_candidate() -> None:
    query = load_query("similar_encoder")
    candidate = load_fingerprint("host_encoder_pressure")
    query_before = query.model_dump()
    candidate_before = candidate.model_dump()

    build_candidate_evidence(query, candidate)

    assert query.model_dump() == query_before
    assert candidate.model_dump() == candidate_before
