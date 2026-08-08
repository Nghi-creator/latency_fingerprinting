"""Tests for degraded/relief window comparability validation."""

from __future__ import annotations

from typing import TypeVar

import pytest
from pydantic import BaseModel

from latency_fingerprinting.models import (
    ContextKey,
    MetricAggregate,
    ObservationWindow,
    Probe,
    ProbeApplicationMethod,
    ProbeExecutionStatus,
    ProvenanceKind,
    RestorationStatus,
    SourceArtifact,
    TimeBounds,
    ValidityState,
    WindowPhase,
)
from latency_fingerprinting.validation import (
    ComparabilityReason,
    validate_window_comparability,
)


def make_context(**changes: object) -> ContextKey:
    values: dict[str, object] = {
        "context_id": "context-p0-synthetic",
        "compatibility_group": "p0-synthetic-v1",
        "edge_node_class": "synthetic-edge",
        "node_id": "anonymous-node-001",
        "operating_system": "linux",
        "runtime_class": "container",
        "workload_id": "synthetic-game",
        "capture_implementation": "synthetic-fixture",
        "encoder_family": "vp8",
        "encoder_profile": "realtime",
        "transport_implementation": "webrtc",
        "connection_mode": "direct",
        "client_class": "chromium",
        "nominal_stream_profile": {"fps": 60, "bitrateKbps": 6000},
        "network_scenario": "controlled-synthetic",
    }
    values.update(changes)
    return ContextKey.model_validate(values)


def make_metric(value: float, *, unit: str = "ms", aggregation: str = "median") -> MetricAggregate:
    return MetricAggregate(
        unit=unit,
        aggregation=aggregation,
        value=value,
        count=20,
        median=value,
        minimum=value,
        maximum=value,
    )


def make_window(
    phase: WindowPhase,
    window_id: str,
    elapsed_start_s: float,
    value: float,
    *,
    context: ContextKey,
    duration_s: float = 10,
    provenance: ProvenanceKind = ProvenanceKind.SYNTHETIC,
    validity: ValidityState | None = None,
    comparison_case_id: str | None = "case-network-001",
    effective_settings: dict[str, object] | None = None,
    confounders: list[str] | None = None,
) -> ObservationWindow:
    return ObservationWindow(
        run_id="run-synthetic-001",
        window_id=window_id,
        comparison_case_id=comparison_case_id,
        context=context,
        phase=phase,
        bounds=TimeBounds(
            elapsed_start_s=elapsed_start_s,
            elapsed_end_s=elapsed_start_s + duration_s,
        ),
        duration_s=duration_s,
        sample_count=20,
        effective_settings=effective_settings
        or {"fps": 60 if phase is WindowPhase.DEGRADED else 30, "bitrateKbps": 6000},
        metrics={"transport.jitter_ms": make_metric(value)},
        validity=validity or ValidityState(is_valid=True),
        source_artifact=SourceArtifact(
            artifact_id=f"fixture-{window_id}", source_type="synthetic_fixture"
        ),
        provenance=provenance,
        confounders=confounders or [],
    )


def make_pair() -> tuple[ObservationWindow, ObservationWindow, Probe]:
    context = make_context()
    degraded = make_window(WindowPhase.DEGRADED, "window-degraded", 0, 20, context=context)
    relief = make_window(WindowPhase.RELIEF, "window-relief", 10, 8, context=context)
    probe = Probe(
        probe_id="probe-stream-relief-001",
        probe_type="stream_profile_relief",
        probe_version="1",
        requested_settings={"fps": 30},
        intensity=0.5,
        application_method=ProbeApplicationMethod.SIMULATED_PAIR,
        degraded_window_id=degraded.window_id,
        relief_window_id=relief.window_id,
        execution_status=ProbeExecutionStatus.NOT_EXECUTED,
        restoration_status=RestorationStatus.NOT_EXECUTED,
    )
    return degraded, relief, probe


ModelT = TypeVar("ModelT", bound=BaseModel)


def rebuild(model: ModelT, **changes: object) -> ModelT:
    payload = model.model_dump()
    payload.update(changes)
    return type(model).model_validate(payload)


def test_valid_synthetic_pair_is_comparable() -> None:
    degraded, relief, probe = make_pair()
    result = validate_window_comparability(degraded, relief, probe)

    assert result.is_comparable
    assert result.issues == ()
    assert result.warnings == ()
    assert result.shared_metrics == ("transport.jitter_ms",)
    assert result.changed_settings == ("fps",)


@pytest.mark.parametrize(
    ("input_name", "phase", "expected_reason"),
    [
        ("degraded", WindowPhase.BASELINE, ComparabilityReason.INCORRECT_DEGRADED_PHASE),
        ("relief", WindowPhase.RECOVERY, ComparabilityReason.INCORRECT_RELIEF_PHASE),
    ],
)
def test_incorrect_phases_are_rejected(
    input_name: str, phase: WindowPhase, expected_reason: ComparabilityReason
) -> None:
    degraded, relief, probe = make_pair()
    if input_name == "degraded":
        degraded = rebuild(degraded, phase=phase)  # type: ignore[assignment]
    else:
        relief = rebuild(relief, phase=phase)  # type: ignore[assignment]

    result = validate_window_comparability(degraded, relief, probe)
    assert expected_reason in result.reason_codes


@pytest.mark.parametrize(
    ("input_name", "expected_reason"),
    [
        ("degraded", ComparabilityReason.INVALID_DEGRADED_WINDOW),
        ("relief", ComparabilityReason.INVALID_RELIEF_WINDOW),
    ],
)
def test_invalid_windows_retain_their_reasons(
    input_name: str, expected_reason: ComparabilityReason
) -> None:
    degraded, relief, probe = make_pair()
    invalidity = ValidityState(is_valid=False, reasons=["inactive playback"])
    if input_name == "degraded":
        degraded = rebuild(degraded, validity=invalidity)  # type: ignore[assignment]
    else:
        relief = rebuild(relief, validity=invalidity)  # type: ignore[assignment]

    result = validate_window_comparability(degraded, relief, probe)
    issue = next(issue for issue in result.issues if issue.code is expected_reason)
    assert "inactive playback" in issue.message


def test_context_and_compatibility_group_mismatches_are_distinguished() -> None:
    degraded, relief, probe = make_pair()
    other_context = make_context(network_scenario="different-scenario")
    relief = rebuild(relief, context=other_context)  # type: ignore[assignment]

    result = validate_window_comparability(degraded, relief, probe)
    assert ComparabilityReason.CONTEXT_MISMATCH in result.reason_codes
    assert ComparabilityReason.COMPATIBILITY_GROUP_MISMATCH not in result.reason_codes

    incompatible_context = make_context(compatibility_group="different-group")
    relief = rebuild(relief, context=incompatible_context)  # type: ignore[assignment]
    result = validate_window_comparability(degraded, relief, probe)
    assert ComparabilityReason.CONTEXT_MISMATCH in result.reason_codes
    assert ComparabilityReason.COMPATIBILITY_GROUP_MISMATCH in result.reason_codes


@pytest.mark.parametrize(
    ("degraded_case", "relief_case", "expected_reason"),
    [
        (None, None, ComparabilityReason.MISSING_COMPARISON_CASE),
        ("case-a", "case-b", ComparabilityReason.COMPARISON_CASE_MISMATCH),
    ],
)
def test_comparison_case_must_be_present_and_equal(
    degraded_case: str | None,
    relief_case: str | None,
    expected_reason: ComparabilityReason,
) -> None:
    degraded, relief, probe = make_pair()
    degraded = rebuild(degraded, comparison_case_id=degraded_case)  # type: ignore[assignment]
    relief = rebuild(relief, comparison_case_id=relief_case)  # type: ignore[assignment]

    result = validate_window_comparability(degraded, relief, probe)
    assert expected_reason in result.reason_codes


def test_probe_must_reference_the_supplied_windows() -> None:
    degraded, relief, probe = make_pair()
    probe = rebuild(probe, relief_window_id="another-relief-window")  # type: ignore[assignment]

    result = validate_window_comparability(degraded, relief, probe)
    assert ComparabilityReason.PROBE_WINDOW_MISMATCH in result.reason_codes


def test_provenance_must_match() -> None:
    degraded, relief, probe = make_pair()
    relief = rebuild(relief, provenance=ProvenanceKind.CONTROLLED_REAL)  # type: ignore[assignment]

    result = validate_window_comparability(degraded, relief, probe)
    assert ComparabilityReason.PROVENANCE_MISMATCH in result.reason_codes


def test_unsupported_probe_is_rejected() -> None:
    degraded, relief, probe = make_pair()
    probe = rebuild(probe, probe_type="experimental_unknown_probe")  # type: ignore[assignment]

    result = validate_window_comparability(degraded, relief, probe)
    assert ComparabilityReason.UNSUPPORTED_PROBE in result.reason_codes


def test_duration_tolerance_is_explicit_and_configurable() -> None:
    degraded, relief, probe = make_pair()
    relief = make_window(
        WindowPhase.RELIEF,
        relief.window_id,
        10,
        8,
        context=relief.context,
        duration_s=11,
    )
    assert validate_window_comparability(degraded, relief, probe).is_comparable

    strict_result = validate_window_comparability(
        degraded, relief, probe, duration_relative_tolerance=0.05
    )
    assert ComparabilityReason.DURATION_MISMATCH in strict_result.reason_codes


@pytest.mark.parametrize("invalid_tolerance", [-0.01, 1.01, float("nan"), float("inf")])
def test_invalid_duration_tolerance_is_programmer_error(invalid_tolerance: float) -> None:
    degraded, relief, probe = make_pair()
    with pytest.raises(ValueError, match="duration_relative_tolerance"):
        validate_window_comparability(
            degraded, relief, probe, duration_relative_tolerance=invalid_tolerance
        )


@pytest.mark.parametrize(
    ("metric", "expected_reason"),
    [
        (make_metric(8, unit="s"), ComparabilityReason.METRIC_UNIT_MISMATCH),
        (
            make_metric(8, aggregation="p95"),
            ComparabilityReason.METRIC_AGGREGATION_MISMATCH,
        ),
    ],
)
def test_shared_metrics_require_compatible_units_and_aggregation(
    metric: MetricAggregate, expected_reason: ComparabilityReason
) -> None:
    degraded, relief, probe = make_pair()
    relief = rebuild(relief, metrics={"transport.jitter_ms": metric})  # type: ignore[assignment]

    result = validate_window_comparability(degraded, relief, probe)
    assert expected_reason in result.reason_codes


def test_requested_setting_must_be_applied_and_changed() -> None:
    degraded, relief, probe = make_pair()
    not_applied = rebuild(probe, requested_settings={"fps": 45})
    result = validate_window_comparability(degraded, relief, not_applied)  # type: ignore[arg-type]
    assert ComparabilityReason.REQUESTED_SETTING_NOT_APPLIED in result.reason_codes

    unchanged_relief = rebuild(relief, effective_settings={"fps": 60, "bitrateKbps": 6000})
    unchanged_probe = rebuild(probe, requested_settings={"fps": 60})
    result = validate_window_comparability(
        degraded,
        unchanged_relief,  # type: ignore[arg-type]
        unchanged_probe,  # type: ignore[arg-type]
    )
    assert ComparabilityReason.REQUESTED_SETTING_UNCHANGED in result.reason_codes


def test_unrelated_setting_changes_require_confounder_metadata() -> None:
    degraded, relief, probe = make_pair()
    changed_settings = {"fps": 30, "bitrateKbps": 3000}
    relief = rebuild(relief, effective_settings=changed_settings)  # type: ignore[assignment]

    result = validate_window_comparability(degraded, relief, probe)
    assert ComparabilityReason.UNDECLARED_SETTING_CHANGE in result.reason_codes
    assert result.changed_settings == ("bitrateKbps", "fps")

    relief_with_confounder = rebuild(
        relief,
        confounders=["Bitrate changed as a known composite-preset confounder."],
    )
    result = validate_window_comparability(
        degraded,
        relief_with_confounder,
        probe,  # type: ignore[arg-type]
    )
    assert result.is_comparable
    assert result.warnings
