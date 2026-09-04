"""Generic configuration and scalar math for feature normalization."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeatureNormalizationConfig:
    """Unit, numerical floor, and optional clipping for one feature."""

    unit: str
    epsilon: float
    clip_min: float | None = None
    clip_max: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.unit, str):
            raise ValueError("normalization feature unit must be a string")
        if not self.unit.strip():
            raise ValueError("normalization feature unit cannot be empty")
        epsilon = _finite_number(self.epsilon, name="normalization epsilon")
        if epsilon <= 0:
            raise ValueError("normalization epsilon must be finite and greater than zero")
        clip_min = (
            _finite_number(self.clip_min, name="clip_min") if self.clip_min is not None else None
        )
        clip_max = (
            _finite_number(self.clip_max, name="clip_max") if self.clip_max is not None else None
        )
        if clip_min is not None and clip_max is not None and clip_min > clip_max:
            raise ValueError("clip_min must not exceed clip_max")
        object.__setattr__(self, "epsilon", epsilon)
        object.__setattr__(self, "clip_min", clip_min)
        object.__setattr__(self, "clip_max", clip_max)


def _finite_number(value: object, *, name: str) -> float:
    """Return one strict finite real without accepting booleans as numbers."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{name} must be finite") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def normalize_feature_value(
    raw_delta: float,
    reference_value: float,
    config: FeatureNormalizationConfig,
) -> tuple[float, bool, float | None]:
    """Return the canonical value and clipping metadata for one feature."""

    if not isinstance(config, FeatureNormalizationConfig):
        raise ValueError("config must be a FeatureNormalizationConfig")
    raw = _finite_number(raw_delta, name="raw_delta")
    reference = _finite_number(reference_value, name="reference_value")
    unclipped = raw / max(abs(reference), config.epsilon)
    if not math.isfinite(unclipped):
        raise ValueError("normalized feature value exceeds the finite numeric range")
    value = unclipped
    if config.clip_min is not None:
        value = max(value, config.clip_min)
    if config.clip_max is not None:
        value = min(value, config.clip_max)
    was_clipped = value != unclipped
    return value, was_clipped, unclipped if was_clipped else None


__all__ = ["FeatureNormalizationConfig", "normalize_feature_value"]
