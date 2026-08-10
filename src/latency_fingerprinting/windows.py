"""Raw response-delta construction from comparable observation windows."""

from __future__ import annotations

from .models import FeatureDelta, ObservationWindow, Probe, ResponseDelta
from .validation import (
    DEFAULT_DURATION_RELATIVE_TOLERANCE,
    SUPPORTED_P0_PROBE_TYPES,
    validate_window_comparability,
)


def _feature_availability(
    degraded: ObservationWindow,
    relief: ObservationWindow,
) -> tuple[list[str], dict[str, str]]:
    """Return deterministic missing and rejected feature metadata."""

    rejected_features: dict[str, str] = {}
    rejected_names = set(degraded.rejected_metrics) | set(relief.rejected_metrics)
    for feature in sorted(rejected_names):
        reasons: list[str] = []
        if feature in degraded.rejected_metrics:
            reasons.append(f"degraded: {degraded.rejected_metrics[feature]}")
        if feature in relief.rejected_metrics:
            reasons.append(f"relief: {relief.rejected_metrics[feature]}")
        rejected_features[feature] = "; ".join(reasons)

    all_known_features = (
        set(degraded.metrics)
        | set(relief.metrics)
        | set(degraded.missing_metrics)
        | set(relief.missing_metrics)
        | rejected_names
    )
    shared_features = set(degraded.metrics).intersection(relief.metrics)
    missing_features = sorted(all_known_features - shared_features - rejected_names)
    return missing_features, rejected_features


def build_response_delta(
    degraded: ObservationWindow,
    relief: ObservationWindow,
    probe: Probe,
    *,
    duration_relative_tolerance: float = DEFAULT_DURATION_RELATIVE_TOLERANCE,
    supported_probe_types: frozenset[str] = SUPPORTED_P0_PROBE_TYPES,
) -> ResponseDelta:
    """Build an auditable raw response using ``relief - degraded``.

    An incomparable pair returns an invalid ``ResponseDelta`` containing stable
    validation reasons. Missing and rejected evidence is retained explicitly
    and never converted into a numeric zero.
    """

    comparability = validate_window_comparability(
        degraded,
        relief,
        probe,
        duration_relative_tolerance=duration_relative_tolerance,
        supported_probe_types=supported_probe_types,
    )
    missing_features, rejected_features = _feature_availability(degraded, relief)

    if not comparability.is_comparable:
        return ResponseDelta(
            degraded_window_id=degraded.window_id,
            relief_window_id=relief.window_id,
            features={},
            missing_features=missing_features,
            rejected_features=rejected_features,
            is_valid=False,
            invalid_reasons=[
                f"{issue.code.value}: {issue.message}" for issue in comparability.issues
            ],
            warnings=list(comparability.warnings),
        )

    features: dict[str, FeatureDelta] = {}
    for feature in comparability.shared_metrics:
        degraded_metric = degraded.metrics[feature]
        relief_metric = relief.metrics[feature]
        features[feature] = FeatureDelta(
            unit=degraded_metric.unit,
            aggregation=degraded_metric.aggregation,
            degraded_value=degraded_metric.value,
            relief_value=relief_metric.value,
            raw_delta=relief_metric.value - degraded_metric.value,
        )

    return ResponseDelta(
        degraded_window_id=degraded.window_id,
        relief_window_id=relief.window_id,
        features=features,
        missing_features=missing_features,
        rejected_features=rejected_features,
        is_valid=True,
        warnings=list(comparability.warnings),
    )


__all__ = ["build_response_delta"]
