"""Frozen feature-normalization configuration for the P0 contract."""

from __future__ import annotations

import math
from collections.abc import Mapping
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


P0_FEATURE_CONFIG: Mapping[str, FeatureNormalizationConfig] = {
    "client.available_incoming_bitrate_kbps": FeatureNormalizationConfig(unit="kbps", epsilon=1.0),
    "client.decode_time_mean_ms": FeatureNormalizationConfig(unit="ms", epsilon=0.1),
    "client.frames_decoded_delta": FeatureNormalizationConfig(unit="frames", epsilon=1.0),
    "client.frames_dropped_delta": FeatureNormalizationConfig(unit="frames", epsilon=1.0),
    "client.freeze_count_delta": FeatureNormalizationConfig(unit="freezes", epsilon=1.0),
    "client.freeze_duration_ms_delta": FeatureNormalizationConfig(unit="ms", epsilon=1.0),
    "client.jitter_buffer_delay_mean_ms": FeatureNormalizationConfig(unit="ms", epsilon=0.1),
    "client.received_fps": FeatureNormalizationConfig(unit="fps", epsilon=1.0),
    "client.received_bitrate_kbps": FeatureNormalizationConfig(unit="kbps", epsilon=1.0),
    "encoder.frames_dropped_delta": FeatureNormalizationConfig(unit="frames", epsilon=1.0),
    "encoder.frames_in_delta": FeatureNormalizationConfig(unit="frames", epsilon=1.0),
    "encoder.frames_out_delta": FeatureNormalizationConfig(unit="frames", epsilon=1.0),
    "encoder.pipeline_delay_proxy_ms": FeatureNormalizationConfig(unit="ms", epsilon=0.1),
    "encoder.queue_level_buffers": FeatureNormalizationConfig(unit="buffers", epsilon=1.0),
    "host.camera_cpu_percent": FeatureNormalizationConfig(unit="percent", epsilon=0.1),
    "host.camera_rss_mb": FeatureNormalizationConfig(unit="MiB", epsilon=1.0),
    "host.game_cpu_percent": FeatureNormalizationConfig(unit="percent", epsilon=0.1),
    "host.game_rss_mb": FeatureNormalizationConfig(unit="MiB", epsilon=1.0),
    "host.node_cpu_percent": FeatureNormalizationConfig(unit="percent", epsilon=0.1),
    "host.node_rss_mb": FeatureNormalizationConfig(unit="MiB", epsilon=1.0),
    "transport.jitter_ms": FeatureNormalizationConfig(unit="ms", epsilon=0.1),
    "transport.packets_lost_delta": FeatureNormalizationConfig(unit="packets", epsilon=1.0),
    "transport.round_trip_time_ms": FeatureNormalizationConfig(unit="ms", epsilon=0.1),
}


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


__all__ = [
    "P0_FEATURE_CONFIG",
    "FeatureNormalizationConfig",
    "normalize_feature_value",
]
