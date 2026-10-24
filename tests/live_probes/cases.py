"""Literal synthetic evidence operands; no producer acquisition or live capability."""

import copy
import hashlib
import json

SETTINGS = dict(
    cpu_used=8,
    min_quantizer=4,
    max_quantizer=56,
    width=640,
    height=360,
    fps_numerator=30,
    fps_denominator=1,
    end_usage="cbr",
    threads=4,
    deadline_us=1,
    keyframe_max_dist=120,
    buffer_initial_ms=4000,
    buffer_optimal_ms=5000,
    buffer_size_ms=6000,
    lag_in_frames=0,
    dropframe_threshold=0,
    resize_allowed=False,
)


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def seal(value):
    payload = copy.deepcopy(value)
    payload.pop("evidence_id", None)
    payload.pop("content_hash", None)
    digest = hashlib.sha256(canonical(payload)).hexdigest()
    return dict(payload, evidence_id="live-evidence-" + digest, content_hash="sha256:" + digest)


def sample(at, count, bitrate):
    return dict(
        read_start_ns=at,
        read_end_ns=at + 1,
        counter_generation="counters-1",
        bitrate=bitrate,
        encoded_bytes=count * 6000,
        encoded_frames=count,
        decoded_frames=count,
        decoded_dropped=0,
        settings=copy.deepcopy(SETTINGS),
    )


def payload():
    return seal(
        dict(
            schema_version="live-probe-evidence-v1",
            method_release="n10-live-evidence-v1",
            assurance="offline_declared_evidence_not_live_authority",
            live_authority=False,
            capability="unavailable_unqualified",
            receiver_continuity="unverified",
            quality="not_evaluated",
            scope=dict(
                acquisition_id="acquisition-1",
                owner_generation="owner-1",
                pipeline_generation="pipeline-1",
                peer_generation=None,
                clock_domain="clock-1",
                clock_generation="process-1",
                clock_basis="process_monotonic_relative_ns",
                provenance="isolated_synthetic",
                producer_revision="a" * 40,
                image_hash="sha256:" + "b" * 64,
            ),
            intent=dict(
                request_id="request-1",
                capability_revision="unqualified-1",
                policy_hash="sha256:" + "c" * 64,
                family="vp8_target_bitrate",
                control="vp8enc.target-bitrate",
                unit="bit_per_second",
                prior_value=1000000,
                requested_value=500000,
                intent_at_ns=150,
                application_deadline_ns=250,
                restoration_deadline_ns=650,
                application_settling_ns=10,
                restoration_settling_ns=10,
            ),
            receipts=[
                dict(
                    phase=phase,
                    requested_value=value,
                    call_start_ns=start,
                    call_end_ns=start + 10,
                    outcome="returned",
                )
                for phase, value, start in (
                    ("application", 500000, 200),
                    ("restoration", 1000000, 400),
                    ("cleanup", 1000000, 600),
                )
            ],
            windows=[
                dict(
                    phase=phase,
                    start_ns=start,
                    end_ns=start + 100,
                    samples=[
                        sample(start + 10, count, bitrate),
                        sample(start + 80, count + 10, bitrate),
                    ],
                )
                for phase, start, count, bitrate in (
                    ("baseline", 0, 0, 1000000),
                    ("during", 230, 10, 500000),
                    ("restoration", 430, 20, 1000000),
                )
            ],
            reason_codes=["capability_unqualified"],
        )
    )
