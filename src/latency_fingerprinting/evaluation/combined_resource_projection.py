"""Byte-bound combination of source-local encoded and generic CPU intervals."""

import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy

from ..analytical.policy_release import payload_hash
from ..json_io import strict_json_loads
from .cpu_resource_response import PHASES, cpu_resource_response, cpu_resource_response_spec
from .temporal_rate_response import (
    _project_temporal_source,
    temporal_rate_projection_spec,
    temporal_rate_response_spec,
)

RELEASE = "n11-combined-resource-projection-candidate-v1"
SOURCE_METHOD = "n11-contained-condition-resource-candidate-v1"
ERROR = "invalid_combined_resource_projection"
MAX_BYTES = 2 * 1024 * 1024
TEMPORAL_SPEC = {
    **temporal_rate_projection_spec(),
    "release": "n11-resource-source-encoded-projection-candidate-v1",
    "source_method": SOURCE_METHOD,
}
TEMPORAL_SPEC.pop("content_hash")
TEMPORAL_SPEC["content_hash"] = payload_hash(TEMPORAL_SPEC)
_SPEC = dict(
    release=RELEASE,
    source_method=SOURCE_METHOD,
    encoded_projection_hash=TEMPORAL_SPEC["content_hash"],
    encoded_response_hash=temporal_rate_response_spec()["content_hash"],
    cpu_response_hash=cpu_resource_response_spec()["content_hash"],
    binding="exact_utf8_acquisition_bytes_sha256_and_identical_embedded_cpu_samples",
    clocks="worker_and_controller_generation_bound_separate_no_cross_clock_subtraction",
    source_context="exact_controller_origin_generation_phase_and_runtime_image_software_platform_arch",
    runtime_context="source_image_digest_software_hash_platform_arch_must_match_across_training_query",
    availability="both_complete_responses_all_nine_coordinates_or_unavailable",
    assurance="external_producer_ownership_inspector_and_raw_source_custody_required",
    acquisition_authority=False,
    empirical_acceptance=False,
)


def combined_resource_projection_spec():
    return {**deepcopy(_SPEC), "content_hash": payload_hash(_SPEC)}


def _exact(value, keys):
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise ValueError(ERROR)


def project_combined_resource(source):
    """Rebuild from raw JSON text and its auxiliary artifact; never accept cached scores."""
    return _project_combined_resource(
        source, projection_spec=combined_resource_projection_spec(), temporal_spec=TEMPORAL_SPEC
    )


def _project_combined_resource(
    source, *, projection_spec, temporal_spec, counter_read_key="native_read"
):
    projection, _, _ = _project_combined_components(
        source,
        projection_spec=projection_spec,
        temporal_spec=temporal_spec,
        counter_read_key=counter_read_key,
    )
    return projection


def _project_combined_components(source, *, projection_spec, temporal_spec, counter_read_key):
    """Shared byte/ownership/CPU seam; callers fix a separately identified read contract."""
    try:
        _exact(source, ("acquisition_json", "resource_artifact"))
        text, artifact = source["acquisition_json"], source["resource_artifact"]
        if type(text) is not str or len(text) > MAX_BYTES:
            raise ValueError(ERROR)
        raw = text.encode("utf-8")
        if len(raw) > MAX_BYTES:
            raise ValueError(ERROR)
        acquisition = strict_json_loads(text)
        runtime_context = acquisition.get("context")
        _exact(runtime_context, ("image", "software_hash", "host_platform", "host_arch"))
        if (
            type(runtime_context["image"]) is not str
            or re.fullmatch(r"sha256:[a-f0-9]{64}", runtime_context["image"]) is None
            or type(runtime_context["software_hash"]) is not str
            or re.fullmatch(r"[a-f0-9]{64}", runtime_context["software_hash"]) is None
            or any(
                type(runtime_context[k]) is not str or not runtime_context[k]
                for k in ("host_platform", "host_arch")
            )
            or acquisition.get("role") != "engineering_resource_condition_witness_label_unavailable"
            or acquisition.get("mode")
            not in (
                "engineering-n11-resource-condition-no_injected_fault",
                "engineering-n11-resource-condition-owned_identity_delay",
                "engineering-n11-resource-condition-owned_cpu_pressure",
            )
        ):
            raise ValueError(ERROR)
        _exact(
            artifact,
            (
                "method",
                "source_payload_sha256",
                "context",
                "clock_id",
                "source_identity",
                "windows",
                "samples",
                "empirical_acceptance",
                "acquisition_authority",
            ),
        )
        raw_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
        if (
            artifact["method"] != SOURCE_METHOD
            or artifact["source_payload_sha256"] != raw_hash
            or artifact["empirical_acceptance"] is not False
            or artifact["acquisition_authority"] is not False
        ):
            raise ValueError(ERROR)
        encoded = _project_temporal_source(
            acquisition, SOURCE_METHOD, temporal_spec, counter_read_key=counter_read_key
        )
        events = acquisition["events"]
        if any(
            e.get("kind", "").startswith("n11_resource_")
            and e.get("kind") != "n11_resource_context"
            for e in events
        ):
            raise ValueError(ERROR)
        context_events = [e for e in events if e.get("kind") == "n11_resource_context"]
        if len(context_events) != 1:
            raise ValueError(ERROR)
        context_event = context_events[0]
        _exact(context_event, ("kind", "method", "clock_id", "context", "live_authority"))
        context = context_event["context"]
        _exact(context, ("method", "generation", "controller_origin_ns"))
        origin = context["controller_origin_ns"]
        generation = next(
            e["request"]["generation"] for e in events if e.get("kind") == "n11_pair_dispatched"
        )
        if (
            context["method"] != SOURCE_METHOD
            or context["generation"] != generation
            or type(origin) is not str
            or re.fullmatch(r"[0-9]{1,19}", origin) is None
            or int(origin) > 2**63 - 1
        ):
            raise ValueError(ERROR)
        clock = (
            "controller-monotonic-"
            + hashlib.sha256(
                json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )
        if (
            context_event["method"] != SOURCE_METHOD
            or context_event["live_authority"] is not False
            or context_event["clock_id"] != clock
            or artifact["context"] != context
            or artifact["clock_id"] != clock
        ):
            raise ValueError(ERROR)
        samples, windows = {}, []
        for phase in PHASES:
            if phase in ("healthy", "post"):
                reference = [
                    e
                    for e in events
                    if e.get("kind") == "n11_pacing_reference" and e.get("phase") == phase
                ]
                if len(reference) != 1:
                    raise ValueError(ERROR)
                rows = reference[0]["samples"]
            else:
                rows = [
                    e
                    for e in events
                    if e.get("kind") == "n11_pair_native" and e.get("phase") == phase
                ]
            if not rows or len(rows) > 64:
                raise ValueError(ERROR)
            samples[phase] = []
            for row in rows:
                sample = row["container_cpu_read"]
                if (
                    type(row.get("at_ns")) is not int
                    or type(sample.get("read_start_ns")) is not int
                    or type(sample.get("read_end_ns")) is not int
                    or not 0 <= sample["read_start_ns"] - row["at_ns"] <= 50_000_000
                ):
                    raise ValueError(ERROR)
                if phase in ("healthy", "post"):
                    kind = "n11_pacing_started" if phase == "healthy" else "n11_condition_cleanup"
                    boundaries = [e for e in events if e.get("kind") == kind]
                    if len(boundaries) != 1 or type(boundaries[0].get("at_ns")) is not int:
                        raise ValueError(ERROR)
                    boundary = boundaries[0]["at_ns"]
                    if (
                        phase == "healthy"
                        and sample["read_end_ns"] >= boundary
                        or phase == "post"
                        and sample["read_start_ns"] <= boundary
                    ):
                        raise ValueError(ERROR)
                else:
                    bounds = []
                    for kind in ("n11_pair_phase_started", "n11_pair_phase_completed"):
                        boundaries = [
                            e for e in events if e.get("kind") == kind and e.get("phase") == phase
                        ]
                        if len(boundaries) != 1 or type(boundaries[0].get("at_ns")) is not int:
                            raise ValueError(ERROR)
                        bounds.append(boundaries[0]["at_ns"])
                    if (
                        not bounds[0]
                        <= sample["read_start_ns"]
                        <= sample["read_end_ns"]
                        <= bounds[1]
                    ):
                        raise ValueError(ERROR)
                samples[phase].append(sample)
            first, last = samples[phase][0], samples[phase][-1]
            windows.append(
                dict(
                    phase=phase,
                    sample_count=len(rows),
                    read_start_ns=first["read_start_ns"],
                    read_end_ns=last["read_end_ns"],
                    inner_duration_ns=last["read_start_ns"] - first["read_end_ns"],
                    outer_duration_ns=last["read_end_ns"] - first["read_start_ns"],
                )
            )
        if payload_hash(artifact["samples"]) != payload_hash(samples) or payload_hash(
            artifact["windows"]
        ) != payload_hash(windows):
            raise ValueError(ERROR)
        first_sample_event = next(
            e
            for e in events
            if "container_cpu_read" in e
            or any("container_cpu_read" in row for row in e.get("samples", []))
        )
        if events.index(context_event) >= events.index(first_sample_event):
            raise ValueError(ERROR)
        cpu = cpu_resource_response(samples)
        identity = next(iter(samples.values()))[0]["source_identity"]
        if (
            payload_hash(artifact["source_identity"]) != payload_hash(identity)
            or cpu["clock_id"] != clock
        ):
            raise ValueError(ERROR)
        response_states = {"encoded": encoded["response"]["state"], "cpu": cpu["state"]}
        unavailable = [name for name, state in response_states.items() if state == "unavailable"]
        features = {}
        if not unavailable:
            features.update(
                {
                    "encoded." + n: row["ratio_minus_one"]
                    for n, row in encoded["response"]["features"].items()
                }
            )
            features.update(
                {"resource." + n: row["difference"] for n, row in cpu["features"].items()}
            )
        payload = dict(
            release=projection_spec["release"],
            spec=deepcopy(projection_spec),
            state="unavailable" if unavailable else "candidate_combined_response_available",
            reason_codes=["incomplete_component_responses"] if unavailable else [],
            unavailable_components=unavailable,
            source_bytes_sha256=raw_hash,
            source_payload_hash=encoded["source_payload_hash"],
            runtime_context_hash=payload_hash(runtime_context),
            source_worker_clock=encoded["response"]["clock_id"],
            source_controller_clock=clock,
            component_response_ids={
                "encoded": encoded["response"]["response_id"],
                "cpu": cpu["response_id"],
            },
            features=features,
            empirical_acceptance=False,
            acquisition_authority=False,
        )
        projection = {**payload, "response_id": "combined-resource-" + payload_hash(payload)[7:]}
        return projection, encoded["response"], cpu
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        StopIteration,
        UnicodeError,
    ):
        raise ValueError(ERROR) from None
