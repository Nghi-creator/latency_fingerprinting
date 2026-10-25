"""Cadence import, immutable bounds, fault retention and independent screens."""

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.cli import main
from latency_fingerprinting.live_probes import (
    CadenceProbeEvidence,
    import_cadence_worker_report,
    inspect_cadence_probe_evidence,
)
from latency_fingerprinting.schemas import render_schema

from .cadence_cases import META, evidence, report


def test_independent_rates_clock_domains_and_immutable_identity():
    raw = report()
    root = import_cadence_worker_report(raw, **META)
    inspection = inspect_cadence_probe_evidence(root)
    assert inspection.local_screen == "met"
    assert inspection.producer_assessment_matches
    assert inspection.declared_restoration_supported
    assert not inspection.live_authority
    assert inspection.capability == "unavailable_unqualified"
    assert inspection.quality == inspection.resource_cost == "not_evaluated"
    assert CadenceProbeEvidence.model_validate_json(root.model_dump_json()) == root
    body = root.model_dump(mode="json", exclude={"evidence_id", "content_hash"})
    assert payload_hash(body) == root.content_hash
    raw["observations"][0]["capture_buffers"] = 9000
    assert root.report.observations[0].capture_buffers != 9000
    with pytest.raises(ValueError):
        root.report.observations[0].capture_buffers = 0
    with pytest.raises(ValueError):
        root.report.windows.baseline.end = root.report.windows.baseline.start


@pytest.mark.parametrize(
    "field,value",
    [
        ("live_authority", True),
        ("live_authority", 0),
        ("live_authority", "false"),
        ("scope", "gameplay"),
        ("quality", "qualified"),
        ("resource_cost", "measured"),
        ("clock_basis", "utc"),
        ("pts_basis", "aligned"),
        ("unknown", None),
        ("receipts", [None] * 3),
        ("observations", [None] * 513),
        ("receiver_timeline", [None] * 1201),
    ],
)
def test_closed_report_and_no_coercion(field, value):
    raw = report()
    raw[field] = value
    with pytest.raises(ValueError):
        import_cadence_worker_report(raw, **META)


@pytest.mark.parametrize(
    "change",
    [
        "observation_clock",
        "receipt_clock",
        "setter_value",
        "window_not_retained",
        "settling",
        "fractional_fps",
        "boolean_counter",
        "protocol",
        "unknown_window",
    ],
)
def test_ambiguous_chronology_and_protocol_rejected(change):
    raw = report()
    if change == "observation_clock":
        raw["observations"][1]["at_ns"] = raw["observations"][0]["at_ns"]
    elif change == "receipt_clock":
        raw["receipts"][0]["after_ns"] = 0
    elif change == "setter_value":
        raw["receipts"][0]["requested_fps"] = 30
    elif change == "window_not_retained":
        raw["windows"]["during"]["start"]["capture_buffers"] += 1
    elif change == "settling":
        raw["receipts"][0]["after_ns"] = 1700000000
    elif change == "fractional_fps":
        raw["observations"][0]["configured_fps"] = 30.0
    elif change == "boolean_counter":
        raw["observations"][0]["receiver_frames"] = True
    elif change == "protocol":
        raw["protocol"]["maximum_pts_gap_ns"] *= 2
    else:
        raw["windows"]["warmup"] = raw["windows"]["baseline"]
    with pytest.raises(ValueError):
        import_cadence_worker_report(raw, **META)


@pytest.mark.parametrize(
    "fault",
    [
        "pts_reverse",
        "pts_gap",
        "pull_reverse",
        "count_forged",
        "counter_reset",
        "health",
        "settings",
        "missing_generation",
    ],
)
def test_faults_preserved_and_producer_met_never_promotes(fault):
    raw = report()
    if fault == "pts_reverse":
        raw["receiver_timeline"][5]["pts_ns"] = 0
    elif fault == "pts_gap":
        raw["receiver_timeline"][5]["pts_ns"] += 900000000
    elif fault == "pull_reverse":
        raw["receiver_timeline"][5]["observed_at_ns"] = 0
    elif fault in ("counter_reset", "count_forged", "health", "settings"):
        key, value = {
            "counter_reset": ("capture_buffers", 0),
            "count_forged": ("receiver_frames", 300),
            "health": ("healthy", False),
            "settings": ("settings_hash", "e" * 64),
        }[fault]
        raw["observations"][3][key] = value
        raw["windows"]["during"]["end"][key] = value
    else:
        raw.pop("generation")
    root = import_cadence_worker_report(raw, **META)
    assert root.report.assessment.status == "met"
    result = inspect_cadence_probe_evidence(root)
    assert result.local_screen == "not_met"
    assert not result.live_authority


def test_partial_setup_failure_no_invented_frames_protocol_or_recovery():
    raw = report()
    for field in (
        "generation",
        "receipts",
        "observations",
        "windows",
        "receiver_timeline",
        "result",
        "journal_state",
        "protocol",
        "assessment",
    ):
        raw.pop(field)
    raw.update(status="unavailable", teardown="not_created")
    root = import_cadence_worker_report(raw, **META)
    assert root.report.result is None and root.report.generation is None
    result = inspect_cadence_probe_evidence(root)
    assert result.local_screen == "incomplete"
    assert not result.declared_restoration_supported


def test_dirty_declared_port_success_cannot_support_recovery():
    raw = report()
    raw["journal_state"] = "dirty"
    assert not inspect_cadence_probe_evidence(
        import_cadence_worker_report(raw, **META)
    ).declared_restoration_supported


def test_sealed_content_tamper_or_unsafe_json_rejected():
    raw = evidence().model_dump(mode="json")
    raw["report"]["observations"][0]["capture_buffers"] = 0
    with pytest.raises(ValueError):
        CadenceProbeEvidence.model_validate(raw)
    for value in ('{"schema_version":"x","schema_version":"y"}', '{"x":NaN}'):
        with pytest.raises(ValueError):
            CadenceProbeEvidence.model_validate_json(value)


def test_generic_cli_schema_and_protected_import(tmp_path, capsys):
    source = tmp_path / "report.json"
    output = tmp_path / "evidence.json"
    source.write_text(json.dumps(report()))
    args = ["import-cadence-report", "--report", str(source), "--output", str(output)]
    for key, value in META.items():
        args += ["--" + key.replace("_", "-"), value]
    assert main(args) == 0
    assert capsys.readouterr().out == ""
    root = CadenceProbeEvidence.model_validate_json(output.read_bytes())
    assert root == evidence()
    assert main(["validate", str(output)]) == 0
    assert json.loads(capsys.readouterr().out) == root.model_dump(mode="json")
    schema = json.loads(render_schema(CadenceProbeEvidence))
    jsonschema.validate(root.model_dump(mode="json"), schema)
    protected = source.read_bytes()
    args[args.index("--output") + 1] = str(source)
    assert main(args) == 1
    assert source.read_bytes() == protected
    assert capsys.readouterr().err == "error: import-cadence-report: invalid_input_or_output\n"


def test_one_additive_schema_keeps_previous_37_bytes():
    previous = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in Path("schemas").glob("*.schema.json")
        if p.name != "cadence-probe-evidence-v1.schema.json"
    }
    assert len(previous) == 37
    # Freeze the pre-cadence inventory, including bitrate-v1, independently.
    assert (
        hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest()
        == "449fce6876f25e8dbf0c279adfeb7cb1a35a5dfe01db9ca6be502ef7993f60ed"
    )
