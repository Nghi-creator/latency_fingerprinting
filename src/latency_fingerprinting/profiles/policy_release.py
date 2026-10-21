"""Repository-approved provisional N7 policy, independent of file paths and model imports."""

from copy import deepcopy

from ..analytical.policy_release import payload_hash

POLICY_HASH = "sha256:8e805ffb205e7808559c0eac30d286f3395f006c358b100aef1e95fc705ec641"
FEATURE_NAMES = (
    "client.available_incoming_bitrate_kbps",
    "client.decode_time_mean_ms",
    "client.frames_decoded_rate_fps",
    "client.frames_dropped_rate_fps",
    "client.freeze_count_rate_per_min",
    "client.freeze_duration_rate_ms_per_s",
    "client.jitter_buffer_delay_mean_ms",
    "client.received_bitrate_kbps",
    "client.received_fps",
    "encoder.frames_dropped_rate_fps",
    "encoder.frames_in_rate_fps",
    "encoder.frames_out_rate_fps",
    "encoder.queue_level_buffers",
    "host.camera_cpu_percent",
    "host.camera_rss_mib",
    "host.game_cpu_percent",
    "host.game_rss_mib",
    "host.node_cpu_percent",
    "host.node_rss_mib",
    "transport.jitter_ms",
    "transport.packets_lost_rate_per_s",
    "transport.round_trip_time_ms",
)

_APPROVED = {
    "calibration_method_release": "n6-calibration-evidence-v1",
    "content_hash": "sha256:8e805ffb205e7808559c0eac30d286f3395f006c358b100aef1e95fc705ec641",
    "feature_names": [
        "client.available_incoming_bitrate_kbps",
        "client.decode_time_mean_ms",
        "client.frames_decoded_rate_fps",
        "client.frames_dropped_rate_fps",
        "client.freeze_count_rate_per_min",
        "client.freeze_duration_rate_ms_per_s",
        "client.jitter_buffer_delay_mean_ms",
        "client.received_bitrate_kbps",
        "client.received_fps",
        "encoder.frames_dropped_rate_fps",
        "encoder.frames_in_rate_fps",
        "encoder.frames_out_rate_fps",
        "encoder.queue_level_buffers",
        "host.camera_cpu_percent",
        "host.camera_rss_mib",
        "host.game_cpu_percent",
        "host.game_rss_mib",
        "host.node_cpu_percent",
        "host.node_rss_mib",
        "transport.jitter_ms",
        "transport.packets_lost_rate_per_s",
        "transport.round_trip_time_ms",
    ],
    "gates": {
        "minimum_active_coverage": {"denominator": 4, "numerator": 3},
        "minimum_active_features": 17,
        "minimum_feature_availability": {"denominator": 5, "numerator": 4},
        "minimum_feature_groups": 5,
        "minimum_training_groups": 5,
    },
    "method_release": "n7-profile-statistics-v1",
    "parameter_provenance": "software_provisional",
    "policy_id": "profile-policy-8e805ffb205e7808559c0eac30d286f3395f006c358b100aef1e95fc705ec641",
    "policy_version": "1.0.0",
    "registry": {
        "content_hash": "sha256:50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884",
        "registry_version": "latency-metrics-v2.0.0",
    },
    "response_policy_hash": (
        "sha256:96457b318cc714f3d9d0d63a35b12548f6e030b10057b2c8e5a3a77e352fe1af"
    ),
    "schema_version": "profile-policy-v1",
    "selection": {
        "exclude_duplicates": True,
        "input_kind": "response",
        "mixed_group_labels": "exclude_partition_group",
        "partition_method": "n6_exact_partition_v1",
        "require_n6_eligible": True,
        "role": "training",
    },
    "statistics": {
        "absolute_deviation": "exact_binary64_difference_round_once",
        "center": "median",
        "computed_zero": "positive_zero",
        "dispersion": "raw_mad",
        "dispersion_floor": None,
        "empty_feature": "unavailable",
        "even_median": "exact_binary64_midpoint_round_once",
        "finite_arithmetic": "reject_unrepresentable",
        "nonzero_to_zero": "reject",
        "within_group": "median",
        "zero_dispersion": "exclude",
    },
    "weights": {"excluded": 0.0, "supported": 1.0},
}


def approved_policy_payload():
    payload = deepcopy(_APPROVED)
    digest = payload_hash(
        {k: v for k, v in payload.items() if k not in ("policy_id", "content_hash")}
    )
    if (
        digest != POLICY_HASH
        or payload["content_hash"] != digest
        or payload["policy_id"] != "profile-policy-" + digest[7:]
    ):
        raise ValueError("unreviewed profile policy change")
    return payload
