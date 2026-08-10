"""Static vectors and expected decisions for the synthetic P0 corpus."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..models import MatchDecision, UnknownReason

SYNTHETIC_COMPATIBILITY_GROUP = "p0-synthetic-v1"

FEATURE_BASELINES: Mapping[str, tuple[float, str]] = {
    "client.received_bitrate_kbps": (3000.0, "kbps"),
    "client.received_fps": (40.0, "fps"),
    "transport.jitter_ms": (20.0, "ms"),
    "transport.packets_lost_delta": (10.0, "packets"),
}

REFERENCE_VECTORS: Mapping[str, Mapping[str, float]] = {
    "healthy": {
        "client.received_bitrate_kbps": 0.0,
        "client.received_fps": 0.0,
        "transport.jitter_ms": 0.0,
        "transport.packets_lost_delta": 0.0,
    },
    "network_pressure": {
        "client.received_bitrate_kbps": 0.10,
        "client.received_fps": 0.20,
        "transport.jitter_ms": -0.60,
        "transport.packets_lost_delta": -0.80,
    },
    "host_encoder_pressure": {
        "client.received_bitrate_kbps": 0.20,
        "client.received_fps": 0.60,
        "transport.jitter_ms": -0.10,
        "transport.packets_lost_delta": 0.0,
    },
}

QUERY_VECTORS: Mapping[str, Mapping[str, float]] = {
    "similar_network": {
        "client.received_bitrate_kbps": 0.12,
        "client.received_fps": 0.22,
        "transport.jitter_ms": -0.57,
        "transport.packets_lost_delta": -0.75,
    },
    "similar_encoder": {
        "client.received_bitrate_kbps": 0.18,
        "client.received_fps": 0.55,
        "transport.jitter_ms": -0.12,
        "transport.packets_lost_delta": -0.02,
    },
    "weak": {
        "client.received_bitrate_kbps": -0.90,
        "client.received_fps": 1.50,
        "transport.jitter_ms": 0.80,
        "transport.packets_lost_delta": -0.90,
    },
    "ambiguous": {
        "client.received_bitrate_kbps": 0.15,
        "client.received_fps": 0.40,
        "transport.jitter_ms": -0.35,
        "transport.packets_lost_delta": -0.40,
    },
    "conflicting": {
        "client.received_bitrate_kbps": 0.15,
        "client.received_fps": 0.65,
        "transport.jitter_ms": -0.65,
        "transport.packets_lost_delta": -0.75,
    },
    "incompatible_context": {
        "client.received_bitrate_kbps": 0.12,
        "client.received_fps": 0.22,
        "transport.jitter_ms": -0.57,
        "transport.packets_lost_delta": -0.75,
    },
}


@dataclass(frozen=True, slots=True)
class ExpectedDecision:
    decision: MatchDecision
    label: str | None = None
    unknown_reason: UnknownReason | None = None


QUERY_EXPECTATIONS: Mapping[str, ExpectedDecision] = {
    "similar_network": ExpectedDecision(MatchDecision.MATCHED, label="network_pressure"),
    "similar_encoder": ExpectedDecision(MatchDecision.MATCHED, label="host_encoder_pressure"),
    "weak": ExpectedDecision(MatchDecision.UNKNOWN, unknown_reason=UnknownReason.WEAK_MATCH),
    "ambiguous": ExpectedDecision(
        MatchDecision.UNKNOWN, unknown_reason=UnknownReason.AMBIGUOUS_MARGIN
    ),
    "conflicting": ExpectedDecision(
        MatchDecision.UNKNOWN, unknown_reason=UnknownReason.CONFLICTING_EVIDENCE
    ),
    "incompatible_context": ExpectedDecision(
        MatchDecision.UNKNOWN, unknown_reason=UnknownReason.INCOMPATIBLE_CONTEXT
    ),
}

__all__ = [
    "FEATURE_BASELINES",
    "QUERY_EXPECTATIONS",
    "QUERY_VECTORS",
    "REFERENCE_VECTORS",
    "SYNTHETIC_COMPATIBILITY_GROUP",
    "ExpectedDecision",
]
