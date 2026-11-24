"""Byte-bound raw challenge custody plus lifecycle replay; no stable-pair admission."""

import hashlib
import json
import re

from latency_fingerprinting.analytical.policy_release import canonical_payload_bytes
from latency_fingerprinting.evaluation.protocols.physical_challenge_receipts import (
    _exact,
    _require,
    _states,
    inspect_challenge_transcript,
)
from latency_fingerprinting.json_io import strict_json_loads

ERROR = "invalid_challenge_raw_export"


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _parse(raw, limit):
    _require(type(raw) is bytes and 0 < len(raw) <= limit)
    value = strict_json_loads(raw.decode())
    _require(type(value) is dict)
    return value


def inspect_challenge_raw_export(acquisition_bytes, plan_bytes, export_bytes, exclusion_bytes):
    """Reconcile four original operands; the unqualified raw capture is never N2.

    The caller pins these original files externally. Hash/metadata consistency
    cannot authenticate execution, media semantics, source files or fault labels.
    Failed acquisition prefixes remain outside this completed-custody interface.
    """
    try:
        a = _parse(acquisition_bytes, 4 * 1024 * 1024)
        p = _parse(plan_bytes, 1024 * 1024)
        e = _parse(export_bytes, 4 * 1024 * 1024)
        exclusions = _parse(exclusion_bytes, 1024 * 1024)
        _exact(
            e,
            "schema_version scope acquisition_sha256 plan_sha256 recipe image "
            "native_software_hash source_manifest_hash transcript_json transcript_sha256 "
            "phases source_media_verified resource_dose_verified n2_pair_admitted "
            "empirical_acceptance",
        )
        _require(e["schema_version"] == "n11-physical-challenge-raw-export-v1")
        _require(e["scope"] == "raw_custody_requires_separate_source_qualification")
        _require(
            e["acquisition_sha256"] == _sha(acquisition_bytes)
            and e["plan_sha256"] == _sha(plan_bytes)
        )
        _require(p["schema_version"] == "n11-physical-challenge-plan-v1")
        recipe = p["recipe"]
        before, after = _states(recipe)
        _require(e["recipe"] == recipe == a["challenge_recipe"])
        _require(a["mode"] == p["mode"] == "engineering-n11-physical-challenge-" + recipe)
        _require(a["method"] == "n11-physical-challenge-acquisition-v1")
        _require(a["role"] == "engineering_challenge_raw_phases_no_pair_or_diagnostic_label")
        _require(a["status"] == "passed" and a["live_authority"] is False)
        _require(p["labels"] == "unavailable" and p["retry_allowed"] is False)
        _require(p["n2_pair_admitted"] is False and p["empirical_acceptance"] is False)
        _require(
            p["pair_semantics"]
            == (
                "changing_between_phases_not_stable_pair"
                if before != after
                else "unqualified_raw_phases"
            )
        )
        for key in (
            "source_media_verified",
            "resource_dose_verified",
            "n2_pair_admitted",
            "empirical_acceptance",
        ):
            _require(e[key] is False)
        _require(type(p["image"]) is str and re.fullmatch(r"sha256:[a-f0-9]{64}", p["image"]))
        _require(
            type(p["native_software_hash"]) is str
            and re.fullmatch(r"[a-f0-9]{64}", p["native_software_hash"])
        )
        _require(e["image"] == p["image"] == a["context"]["image"])
        _require(
            e["native_software_hash"] == p["native_software_hash"] == a["context"]["software_hash"]
        )
        sources = p["source_sha256"]
        _require(
            type(sources) is dict
            and sources
            and all(
                type(k) is str and k and type(v) is str and re.fullmatch(r"[a-f0-9]{64}", v)
                for k, v in sources.items()
            )
        )
        source_json = (json.dumps(sources, indent=2, ensure_ascii=False) + "\n").encode()
        _require(e["source_manifest_hash"] == p["source_manifest_hash"] == _sha(source_json))
        _require(
            p["exclusion_receipt_sha256"] == _sha(exclusion_bytes)
            and exclusions["retry_allowed"] is False
        )
        ids = exclusions["excluded_case_ids"]
        _require(type(ids) is list and len(ids) <= 10000 and all(type(i) is str for i in ids))
        _require(len(ids) == len(set(ids)) and ids == p["excluded_case_ids"])
        identifier = p["acquisition_id"]
        _require(
            type(identifier) is str
            and re.fullmatch(r"n11-raw-[a-z0-9-]{1,40}", identifier)
            and identifier not in ids
        )
        _require(type(a["events"]) is list)
        traces = [
            event
            for event in a["events"]
            if type(event) is dict and event.get("kind") == "n11_challenge_command_transcript"
        ]
        _require(len(traces) == 1 and traces[0]["live_authority"] is False)
        _require(type(e["transcript_json"]) is str)
        transcript_bytes = e["transcript_json"].encode()
        _require(_sha(transcript_bytes) == e["transcript_sha256"])
        transcript = strict_json_loads(e["transcript_json"])
        _require(
            canonical_payload_bytes(transcript) == canonical_payload_bytes(traces[0]["transcript"])
        )
        _require(transcript["recipe"] == recipe)
        lifecycle = inspect_challenge_transcript(transcript_bytes)
        captures = a["paired_observation"]["phases"]
        phases = ("degraded", "relief", "recovery")
        _require(
            type(captures) is list
            and len(captures) == 3
            and type(e["phases"]) is list
            and len(e["phases"]) == 3
        )
        for phase, capture, exported in zip(phases, captures, e["phases"], strict=True):
            _exact(exported, "phase capture_json capture_sha256")
            _require(capture["phase"] == exported["phase"] == phase)
            _require(
                capture["version"] == "n11-contained-raw-samples-v1"
                and capture["comparison_case_id"] == identifier
                and capture["failure"] is None
            )
            _require(
                type(capture["browser_samples"]) is list
                and len(capture["browser_samples"]) == 4
                and type(capture["engine_snapshots"]) is list
            )
            _require(
                type(exported["capture_json"]) is str
                and _sha(exported["capture_json"].encode()) == exported["capture_sha256"]
            )
            _require(
                canonical_payload_bytes(strict_json_loads(exported["capture_json"]))
                == canonical_payload_bytes(capture)
            )
        return dict(
            state="raw_challenge_custody_consistent_source_unqualified",
            raw_phases_bound=3,
            acquisition_sha256=_sha(acquisition_bytes),
            plan_sha256=_sha(plan_bytes),
            raw_export_sha256=_sha(export_bytes),
            lifecycle=lifecycle,
            source_media_verified=False,
            resource_dose_verified=False,
            n2_pair_admitted=False,
            empirical_acceptance=False,
            acquisition_authority=False,
        )
    except (KeyError, TypeError, ValueError, UnicodeError, OverflowError):
        raise ValueError(ERROR) from None
