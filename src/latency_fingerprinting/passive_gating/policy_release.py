"""Frozen approved N9 release, independent of docs paths and caller mutation."""

from copy import deepcopy

POLICY_HASH = "sha256:07beb342e6ae7387a6edb2235ba0b26a5122fb3fffb5f83b7da2e7109f48a5ca"

_APPROVED = {
    "assurance": "software_provisional_declared_elapsed_not_live_authority",
    "baseline": {
        "center": "median_of_group_medians",
        "center_strictly_positive": True,
        "confirmed_healthy_only": True,
        "minimum_availability": {"denominator": 5, "numerator": 4},
        "minimum_contributing_groups": 5,
        "minimum_groups": 5,
        "spread": "raw_median_absolute_deviation",
        "training_only": True,
        "weighting": "one_connected_source_group_one_vote",
        "zero_spread_allowed": True,
    },
    "calibration_method_release": "n6-calibration-evidence-v1",
    "clock": {
        "cross_domain_rebase": False,
        "expiration": "explicit_same_stream_tick",
        "generation": "externally_declared",
        "integral_milliseconds_only": True,
        "maximum_elapsed_ms": 9007199254740991,
        "monotonic_guarantee": False,
    },
    "content_hash": "sha256:07beb342e6ae7387a6edb2235ba0b26a5122fb3fffb5f83b7da2e7109f48a5ca",
    "evaluation": {
        "automatic_tuning": False,
        "empirically_calibrated": False,
        "live_execution": False,
        "trust_promotion": False,
    },
    "gates": {
        "low_maximum_ratio": {"denominator": 5, "numerator": 4},
        "maximum_proposals": 3,
        "minimum_bad_duration_ms": 6000,
        "minimum_bad_windows": 3,
        "minimum_good_duration_ms": 4000,
        "minimum_good_windows": 2,
        "proposal_cooldown_ms": 30000,
        "recovered_minimum_ratio": {"denominator": 10, "numerator": 9},
        "stale_after_ms": 5000,
    },
    "limits": {
        "maximum_baseline_windows": 256,
        "maximum_depth": 32,
        "maximum_entries": 256,
        "maximum_events": 256,
        "maximum_group_entry_references": 256,
        "maximum_groups": 256,
        "maximum_replay_windows": 256,
        "maximum_root_bytes": 10485760,
        "maximum_strata": 256,
    },
    "method_release": "n9-passive-gating-v1",
    "metric": {
        "canonical_unit": "fps",
        "clock_basis": "source_elapsed_ms",
        "kind": "gauge",
        "name": "client.received_fps",
        "primary_aggregation": "median",
        "raw_fields": ["fps"],
        "semantic_version": "1.0.0",
        "source": "browser_webrtc",
    },
    "operating_mode": "offline_provisional",
    "policy_id": (
        "passive-gate-policy-07beb342e6ae7387a6edb2235ba0b26a5122fb3fffb5f83b7da2e7109f48a5ca"
    ),
    "quality": {
        "imputation": None,
        "maximum_window_ms": 10000,
        "minimum_usable_samples": 2,
        "minimum_window_ms": 1000,
        "role": "analytical_candidate",
        "summary_status": "complete",
        "support": "supported",
        "temporal_coverage_claim": False,
    },
    "query": {
        "cause_label": None,
        "ignored_n6_reasons": ["label_unverified"],
        "modes": ["validation", "final_test"],
        "profile_hypotheses": "unavailable",
        "source_overlap_scope": "all_contributing_baseline_groups",
        "use_labels": False,
    },
    "registry": {
        "content_hash": "sha256:50329d193303c271194b28e9164ae8627dd257d7620174c5ab136ba209864884",
        "registry_version": "latency-metrics-v2.0.0",
    },
    "schema_version": "passive-gate-policy-v1",
    "scope": {
        "context_excluded_fields": ["context_id", "node_id", "network_scenario"],
        "fields": [
            "registry",
            "provenance",
            "capture_method",
            "clock",
            "source_format",
            "context",
            "effective_settings",
        ],
    },
}


def approved_policy_payload():
    return deepcopy(_APPROVED)
