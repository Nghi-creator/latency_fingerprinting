"""Raw challenge counter reconstruction; ownership/media qualification is separate."""

import hashlib
import json
import re

from latency_fingerprinting.evaluation.projections.encoded_event_source import (
    inspect_challenge_encoded_source,
)
from latency_fingerprinting.evaluation.protocols.physical_challenge_receipts import (
    _exact,
    _integer,
    _require,
    _states,
)
from latency_fingerprinting.evaluation.responses.cpu_resource_response import (
    PHASES,
    cpu_resource_response,
)
from latency_fingerprinting.json_io import strict_json_loads

ERROR = "invalid_challenge_measurements"
METHOD = "n11-physical-challenge-observation-v1"


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def inspect_challenge_measurements(acquisition_bytes):
    """Rebuild generic CPU and encoded windows without asserting stable-pair admission.

    Invalid structure raises. Valid but ineligible timing/trace remains unavailable.
    Original bytes must separately pass custody, lifecycle and media inspection.
    """
    try:
        _require(type(acquisition_bytes) is bytes and 0 < len(acquisition_bytes) <= 4 * 1024 * 1024)
        a = strict_json_loads(acquisition_bytes.decode())
        _require(a["method"] == "n11-physical-challenge-acquisition-v1")
        _require(a["role"] == "engineering_challenge_raw_phases_no_pair_or_diagnostic_label")
        _require(a["status"] == "passed" and a["live_authority"] is False)
        recipe = a["challenge_recipe"]
        before, after = _states(recipe)
        _require(a["mode"] == "engineering-n11-physical-challenge-" + recipe)
        events = a["events"]
        _require(
            type(events) is list
            and all(type(e) is dict and type(e.get("kind")) is str for e in events)
        )

        def one(kind, phase=None):
            found = [
                e
                for e in events
                if e["kind"] == kind and (phase is None or e.get("phase") == phase)
            ]
            _require(len(found) == 1)
            return found[0]

        record = one("n11_challenge_resource_context")
        _require(record["live_authority"] is False)
        context = record["context"]
        _exact(context, "method generation controller_origin_ns")
        _require(context["method"] == METHOD)
        generation = one("n11_pair_dispatched")["request"]["generation"]
        _exact(generation, "owner pipeline peer")
        _require(
            all(
                type(v) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", v)
                for v in generation.values()
            )
        )
        _require(context["generation"] == generation)
        origin = context["controller_origin_ns"]
        _require(
            type(origin) is str and re.fullmatch(r"[0-9]{1,19}", origin) and int(origin) < 2**63
        )
        clock = "controller-monotonic-" + _digest(context)
        worker_clock = "worker-monotonic-" + _digest(generation)
        _require(record["clock_id"] == clock)
        samples, native_previous, previous_sequence, previous_counter = {}, -1, -1, -1
        for phase in PHASES:
            reference = phase in ("healthy", "post")
            rows = (
                one("n11_challenge_reference", phase)["samples"]
                if reference
                else [
                    e for e in events if e["kind"] == "n11_pair_native" and e.get("phase") == phase
                ]
            )
            _require(type(rows) is list and 4 <= len(rows) <= 64)
            samples[phase] = []
            if reference:
                bounds = (0, 2**63 - 1)  # Reference duration is checked from actual reads below.
            else:
                bounds = tuple(
                    _integer(one(kind, phase)["at_ns"])
                    for kind in ("n11_pair_phase_started", "n11_pair_phase_completed")
                )
            for row in rows:
                cpu, read, encoded = (
                    row["container_cpu_read"],
                    row["native_read"],
                    row["encoded_counter_read"],
                )
                _require(
                    events.index(record)
                    < events.index(one("n11_challenge_reference", phase) if reference else row)
                )
                at = _integer(row["at_ns"])
                _require(
                    bounds[0]
                    <= _integer(cpu["read_start_ns"])
                    <= _integer(cpu["read_end_ns"])
                    <= bounds[1]
                )
                _require(0 <= cpu["read_start_ns"] - at <= 50_000_000)
                _require(cpu["phase"] == phase and cpu["clock_id"] == clock)
                _exact(read, "method clock_id basis read_start_ns read_end_ns")
                _require(
                    read["method"] == "native-counter-read-brackets-v1"
                    and read["basis"] == "worker_elapsed_monotonic_ns"
                    and read["clock_id"] == worker_clock
                )
                start, end = _integer(read["read_start_ns"]), _integer(read["read_end_ns"])
                counter, sequence = _integer(row["encoded_buffers"]), _integer(row["sequence"])
                _require(
                    native_previous < start <= end
                    and sequence > previous_sequence
                    and counter >= previous_counter
                )
                _exact(
                    encoded,
                    "method clock_id basis read_start_ns read_end_ns value scope "
                    "underlying_counter_freshness live_authority",
                )
                _require(
                    encoded["method"] == "native-encoded-counter-read-brackets-v1"
                    and encoded["clock_id"] == worker_clock
                    and encoded["basis"] == "worker_elapsed_monotonic_ns"
                )
                _require(
                    encoded["scope"] == "reported_encoded_counter_only_not_other_snapshot_fields"
                    and encoded["underlying_counter_freshness"]
                    == "not_authenticated_by_read_brackets"
                    and encoded["live_authority"] is False
                )
                _require(
                    start
                    <= _integer(encoded["read_start_ns"])
                    <= _integer(encoded["read_end_ns"])
                    <= end
                    and type(encoded["value"]) is int
                    and encoded["value"] == counter
                )
                native_previous, previous_sequence, previous_counter = end, sequence, counter
                samples[phase].append(cpu)
        cpu = cpu_resource_response(samples)
        spans, reasons = inspect_challenge_encoded_source(
            events, worker_clock=worker_clock, controller_origin=origin
        )
        wide = any(
            row["encoded_counter_read"]["read_end_ns"]
            - row["encoded_counter_read"]["read_start_ns"]
            > 100_000_000
            for e in events
            for row in (
                e.get("samples", [])
                if e["kind"] == "n11_challenge_reference"
                else [e]
                if e["kind"] == "n11_pair_native"
                else []
            )
        )
        if wide:
            reasons = [*reasons, "encoded_read_span_too_wide"]
        return dict(
            method="n11-physical-challenge-measurements-v1",
            acquisition_sha256="sha256:" + hashlib.sha256(acquisition_bytes).hexdigest(),
            state="unavailable"
            if reasons or cpu["state"] == "unavailable"
            else "counter_windows_reconstructed",
            cpu_response=cpu,
            encoded_event_spans=spans,
            encoded_reason_codes=reasons,
            stable_condition=before == after,
            stable_pair_admitted=False,
            source_media_verified=False,
            resource_dose_verified=False,
            n2_pair_admitted=False,
            empirical_acceptance=False,
            acquisition_authority=False,
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeError,
        OverflowError,
        StopIteration,
        AttributeError,
    ):
        raise ValueError(ERROR) from None
