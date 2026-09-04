"""Frozen feature-normalization configuration for the P0 contract."""

from __future__ import annotations

from collections.abc import Mapping

from .feature_config import FeatureNormalizationConfig

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


__all__ = ["P0_FEATURE_CONFIG"]
