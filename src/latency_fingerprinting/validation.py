"""Comparability validation for degraded and relief observation windows."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from .models import ObservationWindow, Probe, WindowPhase

DEFAULT_DURATION_RELATIVE_TOLERANCE = 0.10
SUPPORTED_P0_PROBE_TYPES = frozenset({"stream_profile_relief"})


class ComparabilityReason(StrEnum):
    """Stable reason codes for rejecting an observation-window pair."""

    INCORRECT_DEGRADED_PHASE = "incorrect_degraded_phase"
    INCORRECT_RELIEF_PHASE = "incorrect_relief_phase"
    INVALID_DEGRADED_WINDOW = "invalid_degraded_window"
    INVALID_RELIEF_WINDOW = "invalid_relief_window"
    CONTEXT_MISMATCH = "context_mismatch"
    COMPATIBILITY_GROUP_MISMATCH = "compatibility_group_mismatch"
    MISSING_COMPARISON_CASE = "missing_comparison_case"
    COMPARISON_CASE_MISMATCH = "comparison_case_mismatch"
    PROBE_WINDOW_MISMATCH = "probe_window_mismatch"
    PROVENANCE_MISMATCH = "provenance_mismatch"
    UNSUPPORTED_PROBE = "unsupported_probe"
    DURATION_MISMATCH = "duration_mismatch"
    METRIC_UNIT_MISMATCH = "metric_unit_mismatch"
    METRIC_AGGREGATION_MISMATCH = "metric_aggregation_mismatch"
    REQUESTED_SETTING_NOT_APPLIED = "requested_setting_not_applied"
    REQUESTED_SETTING_UNCHANGED = "requested_setting_unchanged"
    OBSERVED_SETTING_MISMATCH = "observed_setting_mismatch"
    UNDECLARED_SETTING_CHANGE = "undeclared_setting_change"


@dataclass(frozen=True, slots=True)
class ComparabilityIssue:
    """One reason why a pair cannot be treated as comparable."""

    code: ComparabilityReason
    message: str
    subject: str | None = None


@dataclass(frozen=True, slots=True)
class ComparabilityResult:
    """Structured output of pair validation, including useful audit context."""

    issues: tuple[ComparabilityIssue, ...]
    warnings: tuple[str, ...]
    shared_metrics: tuple[str, ...]
    changed_settings: tuple[str, ...]

    @property
    def is_comparable(self) -> bool:
        return not self.issues

    @property
    def reason_codes(self) -> tuple[ComparabilityReason, ...]:
        return tuple(issue.code for issue in self.issues)


def _issue(
    code: ComparabilityReason, message: str, subject: str | None = None
) -> ComparabilityIssue:
    return ComparabilityIssue(code=code, message=message, subject=subject)


def _duration_relative_difference(degraded_duration: float, relief_duration: float) -> float:
    return abs(degraded_duration - relief_duration) / max(degraded_duration, relief_duration)


def validate_window_comparability(
    degraded: ObservationWindow,
    relief: ObservationWindow,
    probe: Probe,
    *,
    duration_relative_tolerance: float = DEFAULT_DURATION_RELATIVE_TOLERANCE,
    supported_probe_types: frozenset[str] = SUPPORTED_P0_PROBE_TYPES,
) -> ComparabilityResult:
    """Evaluate whether two windows can support a P0 response calculation.

    Incomparability is returned as data because it is an expected analytical
    outcome. A ``ValueError`` is used only for invalid validator configuration.
    """

    if not math.isfinite(duration_relative_tolerance) or not 0 <= duration_relative_tolerance <= 1:
        raise ValueError("duration_relative_tolerance must be finite and between 0 and 1")

    issues: list[ComparabilityIssue] = []
    warnings: list[str] = []

    if degraded.phase is not WindowPhase.DEGRADED:
        issues.append(
            _issue(
                ComparabilityReason.INCORRECT_DEGRADED_PHASE,
                "the degraded input must use the degraded phase",
                degraded.window_id,
            )
        )
    if relief.phase is not WindowPhase.RELIEF:
        issues.append(
            _issue(
                ComparabilityReason.INCORRECT_RELIEF_PHASE,
                "the relief input must use the relief phase",
                relief.window_id,
            )
        )

    if not degraded.validity.is_valid:
        issues.append(
            _issue(
                ComparabilityReason.INVALID_DEGRADED_WINDOW,
                "the degraded window failed its validity checks: "
                + "; ".join(degraded.validity.reasons),
                degraded.window_id,
            )
        )
    if not relief.validity.is_valid:
        issues.append(
            _issue(
                ComparabilityReason.INVALID_RELIEF_WINDOW,
                "the relief window failed its validity checks: "
                + "; ".join(relief.validity.reasons),
                relief.window_id,
            )
        )

    if degraded.context.compatibility_group != relief.context.compatibility_group:
        issues.append(
            _issue(
                ComparabilityReason.COMPATIBILITY_GROUP_MISMATCH,
                "the windows use different compatibility groups",
            )
        )
    if degraded.context != relief.context:
        issues.append(
            _issue(
                ComparabilityReason.CONTEXT_MISMATCH,
                "the windows do not use the same declared context",
            )
        )

    if degraded.comparison_case_id is None or relief.comparison_case_id is None:
        issues.append(
            _issue(
                ComparabilityReason.MISSING_COMPARISON_CASE,
                "both paired windows require a comparison-case identifier",
            )
        )
    elif degraded.comparison_case_id != relief.comparison_case_id:
        issues.append(
            _issue(
                ComparabilityReason.COMPARISON_CASE_MISMATCH,
                "the windows use different comparison-case identifiers",
            )
        )

    if probe.degraded_window_id != degraded.window_id or probe.relief_window_id != relief.window_id:
        issues.append(
            _issue(
                ComparabilityReason.PROBE_WINDOW_MISMATCH,
                "the probe does not reference the supplied degraded and relief windows",
                probe.probe_id,
            )
        )

    if degraded.provenance is not relief.provenance:
        issues.append(
            _issue(
                ComparabilityReason.PROVENANCE_MISMATCH,
                "the windows use different provenance classes",
            )
        )

    if probe.probe_type not in supported_probe_types:
        issues.append(
            _issue(
                ComparabilityReason.UNSUPPORTED_PROBE,
                f"probe type {probe.probe_type!r} is not supported by P0",
                probe.probe_type,
            )
        )

    relative_duration_difference = _duration_relative_difference(
        degraded.duration_s, relief.duration_s
    )
    if relative_duration_difference > duration_relative_tolerance:
        issues.append(
            _issue(
                ComparabilityReason.DURATION_MISMATCH,
                "window durations differ by "
                f"{relative_duration_difference:.3f}, exceeding the "
                f"{duration_relative_tolerance:.3f} relative tolerance",
            )
        )

    shared_metrics = tuple(sorted(set(degraded.metrics).intersection(relief.metrics)))
    for feature in shared_metrics:
        degraded_metric = degraded.metrics[feature]
        relief_metric = relief.metrics[feature]
        if degraded_metric.unit != relief_metric.unit:
            issues.append(
                _issue(
                    ComparabilityReason.METRIC_UNIT_MISMATCH,
                    f"shared metric {feature!r} uses different units",
                    feature,
                )
            )
        if degraded_metric.aggregation != relief_metric.aggregation:
            issues.append(
                _issue(
                    ComparabilityReason.METRIC_AGGREGATION_MISMATCH,
                    f"shared metric {feature!r} uses different aggregation functions",
                    feature,
                )
            )

    setting_keys = set(degraded.effective_settings) | set(relief.effective_settings)
    changed_settings = tuple(
        sorted(
            key
            for key in setting_keys
            if degraded.effective_settings.get(key) != relief.effective_settings.get(key)
        )
    )
    requested_settings = set(probe.requested_settings)
    for setting, requested_value in sorted(probe.requested_settings.items()):
        if (
            setting not in relief.effective_settings
            or relief.effective_settings[setting] != requested_value
        ):
            issues.append(
                _issue(
                    ComparabilityReason.REQUESTED_SETTING_NOT_APPLIED,
                    f"relief setting {setting!r} does not equal the probe request",
                    setting,
                )
            )
        elif degraded.effective_settings.get(setting) == relief.effective_settings[setting]:
            issues.append(
                _issue(
                    ComparabilityReason.REQUESTED_SETTING_UNCHANGED,
                    f"probe setting {setting!r} did not change between windows",
                    setting,
                )
            )

    if probe.observed_settings is not None:
        for setting, observed_value in sorted(probe.observed_settings.items()):
            if (
                setting not in relief.effective_settings
                or relief.effective_settings[setting] != observed_value
            ):
                issues.append(
                    _issue(
                        ComparabilityReason.OBSERVED_SETTING_MISMATCH,
                        f"observed relief setting {setting!r} disagrees with the relief window",
                        setting,
                    )
                )

    undeclared_changes = sorted(set(changed_settings) - requested_settings)
    declared_confounders = degraded.confounders + relief.confounders + probe.known_confounders
    if undeclared_changes and not declared_confounders:
        for setting in undeclared_changes:
            issues.append(
                _issue(
                    ComparabilityReason.UNDECLARED_SETTING_CHANGE,
                    f"effective setting {setting!r} changed without probe or confounder metadata",
                    setting,
                )
            )
    elif undeclared_changes:
        warnings.append(
            "unrelated effective settings changed but confounders were recorded: "
            + ", ".join(undeclared_changes)
        )

    return ComparabilityResult(
        issues=tuple(issues),
        warnings=tuple(warnings),
        shared_metrics=shared_metrics,
        changed_settings=changed_settings,
    )


__all__ = [
    "DEFAULT_DURATION_RELATIVE_TOLERANCE",
    "SUPPORTED_P0_PROBE_TYPES",
    "ComparabilityIssue",
    "ComparabilityReason",
    "ComparabilityResult",
    "validate_window_comparability",
]
