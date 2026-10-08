"""Independent numerical expectations and immutable pure derivation boundaries."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from latency_fingerprinting.analytical.responses import derive_analytical_response
from latency_fingerprinting.models import FeaturePolicyV1, ObservationRecordV2
from latency_fingerprinting.pipeline import canonical_json
from tests.models.v2_cases import pair_payload, window_payload

from .cases import policy_payload, response_payload

FEATURE = "transport.jitter_ms"
RATE = "client.frames_decoded_rate_fps"


def derive(payload):
    return derive_analytical_response(
        ObservationRecordV2.model_validate(payload),
        FeaturePolicyV1.model_validate(policy_payload()),
    )


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"degraded": (0, 0, 0), "relief": (0, 0, 0)},
        {"degraded": (0, 0, 0), "relief": (0, 2, 4)},
        {"degraded": (0, 30, 60), "relief": (0, 60, 120)},
        {"degraded": (0, 0.25, 0.5), "relief": (0, 0.5, 1)},
        {"degraded": (None, None, None)},
        {"relief": (None, None, None)},
        {"degraded": (0, None, 120)},
        {"relief": (0, None, 60)},
        {"degraded": (None, None, None), "rejected": True},
        *[{"confounder": key} for key in ("degraded_window", "relief_window", "intervention")],
        *[
            {
                "degraded": (None, None, None),
                "relief": (None, None, None),
                "source_state": (phase, state),
            }
            for phase in ("degraded_window", "relief_window")
            for state in ("unsupported", "unavailable")
        ],
    ],
)
def test_derivation_equals_independently_authored_full_record(changes):
    expected = response_payload(**changes)
    result = derive(expected["observation"])
    assert result.model_dump(mode="json", by_alias=True) == expected
    assert not any(name.endswith("window_total") for name in result.features)
    assert "encoder.pipeline_delay_proxy_ms" not in result.features


@pytest.mark.parametrize(
    "degraded,relief,delta,denominator,normalized",
    [
        (0, 0, 0, 1, 0),
        (0, 2, 2, 1, 2),
        (0.25, 0.5, 0.25, 1, 0.25),
        (60, 30, -30, 60, -0.5),
        (30, 60, 30, 30, 1),
    ],
)
def test_signed_gauge_and_rate_math_with_explicit_floor(
    degraded, relief, delta, denominator, normalized
):
    pair = pair_payload()
    pair["degraded_window"] = window_payload(values=(0, degraded, 2 * degraded))
    pair["relief_window"] = window_payload(phase="relief", values=(0, relief, 2 * relief))
    result = derive(pair)
    for name in (FEATURE, RATE):
        feature = result.features[name]
        assert feature.state == "eligible"
        assert feature.raw_delta == delta
        assert feature.reference_value == degraded
        assert feature.denominator == denominator
        assert feature.normalized_value == normalized
        assert not feature.was_clipped and feature.unclipped_value is None


def test_equivalent_counter_activity_across_cadences_uses_rate_not_total():
    results = []
    for duration, degraded, relief in [
        (2000, (0, 60, 120), (0, 30, 60)),
        (4000, (0, 120, 240), (0, 60, 120)),
    ]:
        pair = pair_payload()
        pair["degraded_window"] = window_payload(duration=duration, values=degraded)
        pair["relief_window"] = window_payload(phase="relief", duration=duration, values=relief)
        results.append(derive(pair))
    for name, reference in [(RATE, 60), ("client.freeze_count_rate_per_min", 3600)]:
        a, b = [result.features[name] for result in results]
        assert a.reference_value == b.reference_value == reference
        assert a.normalized_value == b.normalized_value == -0.5
    total = "client.frames_decoded_window_total"
    assert [r.observation.degraded_window.measurements[total].summary.value for r in results] == [
        120,
        240,
    ]
    assert results[0].response_id != results[1].response_id


def test_partial_inventory_preserves_missing_feature_but_keeps_other_features():
    pair = pair_payload()
    missing = window_payload(values=(None, None, None))
    pair["degraded_window"]["measurements"][FEATURE] = missing["measurements"][FEATURE]
    result = derive(pair)
    assert result.is_valid and result.invalid_reason_codes == ()
    excluded = result.features[FEATURE]
    assert excluded.exclusion_codes == ("degraded_missing",)
    assert excluded.degraded.primary_value is None and excluded.normalized_value is None
    assert result.features[RATE].normalized_value == 0
    assert sum(f.state == "eligible" for f in result.features.values()) == 21


def test_deterministic_detached_result_and_unchanged_inputs():
    payload = pair_payload()
    original = deepcopy(payload)
    observation = ObservationRecordV2.model_validate(payload)
    policy = FeaturePolicyV1.model_validate(policy_payload())
    before = (canonical_json(observation), canonical_json(policy))
    a = derive_analytical_response(observation, policy)
    b = derive_analytical_response(observation, policy)
    assert canonical_json(a) == canonical_json(b)
    assert payload == original and before == (canonical_json(observation), canonical_json(policy))
    payload["degraded_window"]["window_id"] = "changed"
    assert a.observation.degraded_window.window_id == "window-degraded"
    with pytest.raises(TypeError):
        a.features[FEATURE] = a.features[RATE]
    with pytest.raises(ValidationError):
        a.features[FEATURE].normalized_value = 99


@pytest.mark.parametrize("boundary", ["policy", "observation", "summary", "clock"])
def test_copied_model_tampering_is_revalidated(boundary):
    observation = ObservationRecordV2.model_validate(pair_payload())
    policy = FeaturePolicyV1.model_validate(policy_payload())
    if boundary == "policy":
        policy = policy.model_copy(update={"maximum_ranked_candidates": True})
    elif boundary == "observation":
        observation = observation.model_copy(update={"observation_id": ""})
    else:
        window = observation.degraded_window
        if boundary == "clock":
            window = window.model_copy(
                update={"clock": window.clock.model_copy(update={"duration_ms": float("inf")})}
            )
        else:
            measurements = dict(window.measurements)
            metric = measurements[FEATURE]
            measurements[FEATURE] = metric.model_copy(
                update={"summary": metric.summary.model_copy(update={"coverage": True})}
            )
            window = window.model_copy(update={"measurements": measurements})
        observation = observation.model_copy(update={"degraded_window": window})
    with pytest.raises(ValidationError):
        derive_analytical_response(observation, policy)


def test_large_finite_activity_is_preserved_without_clipping():
    pair = pair_payload()
    pair["degraded_window"] = window_payload(values=(0, 0, 0))
    pair["relief_window"] = window_payload(phase="relief", values=(0, 1e300, 2e300))
    result = derive(pair)
    assert result.features[FEATURE].normalized_value == 1e300
    assert result.features[RATE].normalized_value == 1e300
    assert result.is_valid
