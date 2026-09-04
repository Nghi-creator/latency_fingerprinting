"""Tests for response-vector normalization."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from latency_fingerprinting.measurement.feature_config import normalize_feature_value
from latency_fingerprinting.models import (
    FeatureDelta,
    NormalizedFeature,
    NormalizedResponse,
    ResponseDelta,
)
from latency_fingerprinting.normalization import (
    P0_FEATURE_CONFIG,
    FeatureNormalizationConfig,
    NormalizationError,
    normalize_response,
)


def feature(
    degraded: float,
    relief: float,
    *,
    unit: str,
    aggregation: str = "median",
) -> FeatureDelta:
    return FeatureDelta(
        unit=unit,
        aggregation=aggregation,
        degraded_value=degraded,
        relief_value=relief,
        raw_delta=relief - degraded,
    )


def make_response(
    *,
    features: dict[str, FeatureDelta] | None = None,
    missing_features: list[str] | None = None,
    rejected_features: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> ResponseDelta:
    return ResponseDelta(
        degraded_window_id="window-degraded",
        relief_window_id="window-relief",
        features=features
        if features is not None
        else {
            "client.received_fps": feature(35, 55, unit="fps"),
            "transport.jitter_ms": feature(20, 8, unit="ms"),
        },
        missing_features=missing_features or [],
        rejected_features=rejected_features or {},
        is_valid=True,
        warnings=warnings or [],
    )


def test_p0_configuration_covers_v1_and_v2_adapter_metrics() -> None:
    assert {
        "client.available_incoming_bitrate_kbps",
        "client.decode_time_mean_ms",
        "client.frames_decoded_delta",
        "client.frames_dropped_delta",
        "client.freeze_count_delta",
        "client.freeze_duration_ms_delta",
        "client.jitter_buffer_delay_mean_ms",
        "client.received_fps",
        "client.received_bitrate_kbps",
        "encoder.frames_dropped_delta",
        "encoder.frames_in_delta",
        "encoder.frames_out_delta",
        "encoder.pipeline_delay_proxy_ms",
        "encoder.queue_level_buffers",
        "host.camera_cpu_percent",
        "host.camera_rss_mb",
        "host.game_cpu_percent",
        "host.game_rss_mb",
        "host.node_cpu_percent",
        "host.node_rss_mb",
        "transport.jitter_ms",
        "transport.packets_lost_delta",
        "transport.round_trip_time_ms",
    } <= set(P0_FEATURE_CONFIG)


def test_p0_configuration_is_immutable() -> None:
    with pytest.raises(TypeError):
        P0_FEATURE_CONFIG["review.mutation"] = next(  # type: ignore[index]
            iter(P0_FEATURE_CONFIG.values())
        )


def test_normalization_uses_degraded_value_as_reference_after_raw_delta() -> None:
    response = make_response()
    normalized = normalize_response(response)

    jitter = normalized.features["transport.jitter_ms"]
    fps = normalized.features["client.received_fps"]
    assert jitter.value == pytest.approx(-12 / 20)
    assert jitter.reference_value == 20
    assert jitter.epsilon == 0.1
    assert fps.value == pytest.approx(20 / 35)
    assert fps.reference_value == 35
    assert response.features["transport.jitter_ms"].raw_delta == -12


def test_zero_and_near_zero_references_use_epsilon_and_remain_finite() -> None:
    response = make_response(
        features={
            "client.received_fps": feature(0, 5, unit="fps"),
            "transport.jitter_ms": feature(0.01, 0.06, unit="ms"),
        }
    )
    normalized = normalize_response(response)

    assert normalized.features["client.received_fps"].value == pytest.approx(5.0)
    assert normalized.features["transport.jitter_ms"].value == pytest.approx(0.5)
    assert all(math.isfinite(item.value) for item in normalized.features.values())


def test_missing_and_rejected_features_remain_non_numeric() -> None:
    response = make_response(
        features={"transport.jitter_ms": feature(20, 8, unit="ms")},
        missing_features=["client.received_bitrate_kbps"],
        rejected_features={"transport.packets_lost_delta": "relief: counter reset"},
    )
    normalized = normalize_response(response)

    assert "client.received_bitrate_kbps" not in normalized.features
    assert "transport.packets_lost_delta" not in normalized.features
    assert normalized.missing_features == ["client.received_bitrate_kbps"]
    assert normalized.rejected_features == {"transport.packets_lost_delta": "relief: counter reset"}


def test_optional_clipping_retains_unclipped_value_and_warning() -> None:
    response = make_response(features={"transport.jitter_ms": feature(20, 8, unit="ms")})
    config = {
        "transport.jitter_ms": FeatureNormalizationConfig(
            unit="ms", epsilon=0.1, clip_min=-0.5, clip_max=0.5
        )
    }
    normalized = normalize_response(response, feature_config=config)
    jitter = normalized.features["transport.jitter_ms"]

    assert jitter.value == -0.5
    assert jitter.was_clipped
    assert jitter.unclipped_value == pytest.approx(-0.6)
    assert normalized.warnings == [
        "normalized feature 'transport.jitter_ms' was clipped from -0.6 to -0.5"
    ]


def test_unclipped_feature_has_no_redundant_unclipped_value() -> None:
    normalized = normalize_response(
        make_response(features={"transport.jitter_ms": feature(20, 8, unit="ms")})
    )
    jitter = normalized.features["transport.jitter_ms"]

    assert not jitter.was_clipped
    assert jitter.unclipped_value is None


def test_invalid_raw_response_remains_invalid_without_numeric_features() -> None:
    response = ResponseDelta(
        degraded_window_id="window-degraded",
        relief_window_id="window-relief",
        features={},
        missing_features=["client.received_bitrate_kbps"],
        rejected_features={"transport.packets_lost_delta": "invalid counter"},
        is_valid=False,
        invalid_reasons=["context_mismatch: contexts differ"],
        warnings=["source pair retained for audit"],
    )
    normalized = normalize_response(response)

    assert not normalized.is_valid
    assert normalized.features == {}
    assert normalized.invalid_reasons == ["context_mismatch: contexts differ"]
    assert normalized.missing_features == ["client.received_bitrate_kbps"]
    assert normalized.rejected_features == {"transport.packets_lost_delta": "invalid counter"}
    assert normalized.warnings == ["source pair retained for audit"]


def test_missing_feature_configuration_is_an_explicit_error() -> None:
    response = make_response(features={"future.encode_queue_ms": feature(10, 5, unit="ms")})
    with pytest.raises(NormalizationError, match="no declared normalization configuration"):
        normalize_response(response)


def test_feature_unit_must_match_normalization_configuration() -> None:
    response = make_response(features={"transport.jitter_ms": feature(0.020, 0.008, unit="s")})
    with pytest.raises(NormalizationError, match="normalization expects 'ms'"):
        normalize_response(response)


@pytest.mark.parametrize(
    "config",
    [
        {"unit": None, "epsilon": 1},
        {"unit": "", "epsilon": 1},
        {"unit": "ms", "epsilon": True},
        {"unit": "ms", "epsilon": "1"},
        {"unit": "ms", "epsilon": 10**400},
        {"unit": "ms", "epsilon": 0},
        {"unit": "ms", "epsilon": -1},
        {"unit": "ms", "epsilon": float("nan")},
        {"unit": "ms", "epsilon": 1, "clip_min": float("-inf")},
        {"unit": "ms", "epsilon": 1, "clip_max": float("inf")},
        {"unit": "ms", "epsilon": 1, "clip_min": 2, "clip_max": 1},
    ],
)
def test_invalid_feature_configuration_is_rejected(config: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        FeatureNormalizationConfig(**config)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("raw_delta", "reference_value"),
    [
        (True, 1.0),
        (1.0, False),
        (float("nan"), 1.0),
        (1.0, float("inf")),
    ],
)
def test_scalar_normalization_rejects_invalid_runtime_numbers(
    raw_delta: object,
    reference_value: object,
) -> None:
    with pytest.raises(ValueError):
        normalize_feature_value(  # type: ignore[arg-type]
            raw_delta,
            reference_value,
            FeatureNormalizationConfig(unit="ms", epsilon=0.1),
        )


def test_scalar_normalization_rejects_invalid_config_object() -> None:
    with pytest.raises(ValueError, match="FeatureNormalizationConfig"):
        normalize_feature_value(1.0, 1.0, object())  # type: ignore[arg-type]


def test_response_normalization_rejects_invalid_config_object() -> None:
    with pytest.raises(NormalizationError, match="FeatureNormalizationConfig"):
        normalize_response(
            make_response(features={"transport.jitter_ms": feature(20, 8, unit="ms")}),
            feature_config={"transport.jitter_ms": object()},  # type: ignore[dict-item]
        )


def test_normalization_overflow_is_a_domain_error() -> None:
    response = make_response(
        features={
            "transport.jitter_ms": feature(0.0, float.fromhex("0x1.fffffffffffffp+1023"), unit="ms")
        }
    )

    with pytest.raises(NormalizationError, match="exceeds the finite numeric range"):
        normalize_response(response)


def test_normalized_model_enforces_clipping_and_availability_invariants() -> None:
    with pytest.raises(ValidationError, match="requires its unclipped_value"):
        NormalizedFeature(
            value=0.5,
            epsilon=0.1,
            reference_value=20,
            was_clipped=True,
        )

    normalized_feature = NormalizedFeature(value=-0.6, epsilon=0.1, reference_value=20)
    with pytest.raises(ValidationError, match="exactly one measured, missing or rejected state"):
        NormalizedResponse(
            features={"transport.jitter_ms": normalized_feature},
            missing_features=["transport.jitter_ms"],
        )


def test_normalization_is_deterministic_round_trippable_and_non_mutating() -> None:
    response = make_response(warnings=["input warning"])
    response_before = response.model_dump()

    first = normalize_response(response)
    second = normalize_response(response)

    assert first == second
    assert response.model_dump() == response_before
    assert NormalizedResponse.model_validate_json(first.model_dump_json(by_alias=True)) == first
