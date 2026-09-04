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
        if not self.unit.strip():
            raise ValueError("normalization feature unit cannot be empty")
        if not math.isfinite(self.epsilon) or self.epsilon <= 0:
            raise ValueError("normalization epsilon must be finite and greater than zero")
        if self.clip_min is not None and not math.isfinite(self.clip_min):
            raise ValueError("clip_min must be finite when provided")
        if self.clip_max is not None and not math.isfinite(self.clip_max):
            raise ValueError("clip_max must be finite when provided")
        if (
            self.clip_min is not None
            and self.clip_max is not None
            and self.clip_min > self.clip_max
        ):
            raise ValueError("clip_min must not exceed clip_max")


def normalize_feature_value(
    raw_delta: float,
    reference_value: float,
    config: FeatureNormalizationConfig,
) -> tuple[float, bool, float | None]:
    """Return the canonical value and clipping metadata for one feature."""

    unclipped = raw_delta / max(abs(reference_value), config.epsilon)
    value = unclipped
    if config.clip_min is not None:
        value = max(value, config.clip_min)
    if config.clip_max is not None:
        value = min(value, config.clip_max)
    was_clipped = value != unclipped
    return value, was_clipped, unclipped if was_clipped else None


__all__ = ["FeatureNormalizationConfig", "normalize_feature_value"]
