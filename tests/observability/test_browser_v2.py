"""Independent execution-endpoint arithmetic and strict version boundary regressions."""

import copy
import hashlib
import io
import json
import tarfile

import jsonschema
import pytest
from pydantic import ValidationError

from latency_fingerprinting.cli import main
from latency_fingerprinting.json_io import canonical_json
from latency_fingerprinting.observability import StageTraceRecord, reconstruct_trace
from latency_fingerprinting.observability.browser_v2 import (
    StageTraceRecordV2,
    StageTraceSummaryV2,
    parse_trace_record,
)
from latency_fingerprinting.observability.bundle import ingest_trace_bundle
from latency_fingerprinting.schemas import SCHEMA_MODELS
from tests.observability.check_browser_execution import FIXTURES, PINS, check_reproduction


def fixture(case="paired", member="trace-record.json"):
    return json.loads((FIXTURES / case / member).read_bytes())


def test_independent_fixture_pins():
    assert check_reproduction()["status"] == "current"
    assert {
        p.relative_to(FIXTURES).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(FIXTURES.rglob("*.json"))
    } == PINS


@pytest.mark.parametrize("case", ["paired", "partial", "unavailable"])
@pytest.mark.parametrize("archive", [False, True])
def test_independent_v2_arithmetic_bundle_and_cli(tmp_path, capsys, case, archive):
    source = FIXTURES / case
    bundle = tmp_path / ("bundle.tar.gz" if archive else "bundle")
    if archive:
        with tarfile.open(bundle, "w:gz", format=tarfile.USTAR_FORMAT) as target:
            for name in ("trace-manifest.json", "trace-record.json"):
                payload = (source / name).read_bytes()
                member = tarfile.TarInfo(name)
                member.size = len(payload)
                target.addfile(member, io.BytesIO(payload))
    else:
        bundle.mkdir()
        for name in ("trace-manifest.json", "trace-record.json"):
            (bundle / name).write_bytes((source / name).read_bytes())
    record = ingest_trace_bundle(bundle)
    assert isinstance(record, StageTraceRecordV2)
    summary = reconstruct_trace(record)
    assert isinstance(summary, StageTraceSummaryV2)
    assert canonical_json(summary).encode() == (source / "expected-summary.json").read_bytes()
    for model, value in [(StageTraceRecordV2, record), (StageTraceSummaryV2, summary)]:
        jsonschema.validate(value.model_dump(mode="json"), model.model_json_schema())
    adopted, inspected = tmp_path / "record.json", tmp_path / "summary.json"
    assert main(["ingest-trace", "--bundle", str(bundle), "--output", str(adopted)]) == 0
    assert main(["inspect-trace", "--trace", str(adopted), "--output", str(inspected)]) == 0
    assert adopted.read_bytes() == (source / "trace-record.json").read_bytes()
    assert inspected.read_bytes() == (source / "expected-summary.json").read_bytes()
    assert main(["validate", str(adopted)]) == main(["validate", str(inspected)]) == 0
    capsys.readouterr()


def test_v1_and_v2_are_explicit_disjoint_contracts():
    with pytest.raises(ValidationError):
        StageTraceRecord.model_validate(fixture())
    value = fixture()
    value["schema_version"] = "stage-trace-record-v1"
    with pytest.raises(ValidationError):
        parse_trace_record(value)
    with pytest.raises(ValueError):
        parse_trace_record([])
    with pytest.raises(ValueError):
        parse_trace_record({"schema_version": "stage-trace-record-v3"})
    assert SCHEMA_MODELS["stage-trace-record-v1.schema.json"] is StageTraceRecord
    assert SCHEMA_MODELS["stage-trace-record-v2.schema.json"] is StageTraceRecordV2
    assert SCHEMA_MODELS["stage-trace-summary-v2.schema.json"] is StageTraceSummaryV2


@pytest.mark.parametrize(
    "mutation",
    [
        "producer",
        "release",
        "clock",
        "capability",
        "event",
        "deadline",
        "correlation",
        "loss",
        "scopes",
        "limit",
    ],
)
def test_v2_cannot_smuggle_host_or_invalid_evidence(mutation):
    value = fixture()
    stream = value["streams"][0]
    if mutation == "producer":
        value["producer"] = "pixelated_engine"
    elif mutation == "release":
        value["method_release"] = "n4-stage-local-v1"
    elif mutation == "clock":
        stream["clock"]["source"] = "python_monotonic_ns"
    elif mutation == "capability":
        stream["capabilities"][-1]["state"] = "unavailable"
    elif mutation == "event":
        stream["events"][2]["boundary"] = "encode_output"
    elif mutation == "deadline":
        stream["deadline"] = {
            "method_id": "capture-output-budget",
            "method_version": 1,
            "budget_ns": 1,
        }
    elif mutation == "correlation":
        stream["frames"][0]["correlation"] = "ambiguous"
    elif mutation == "loss":
        stream["loss"]["retained_events"] += 1
    elif mutation == "scopes":
        extra = copy.deepcopy(stream)
        extra["stream_id"] = "stream-2"
        value["streams"].append(extra)
    elif mutation == "limit":
        stream["limits"]["max_events"] = 10
    with pytest.raises(ValidationError):
        StageTraceRecordV2.model_validate(value)


@pytest.mark.parametrize(
    "mutation", ["method", "mean", "exclusions", "support", "sample", "budget"]
)
def test_v2_summary_revalidates_independent_arithmetic(mutation):
    value = fixture(member="expected-summary.json")
    stream = value["streams"][0]
    result = stream["results"][-1]
    if mutation == "method":
        result["method_id"] = "presentation-callback-lag"
    elif mutation == "mean":
        result["mean_ms"] = 0.2
    elif mutation == "exclusions":
        result["exclusions"]["negative_duration"] = 0
    elif mutation == "support":
        stream["capabilities"][-1].update(state="unavailable", reason="source_unavailable")
    elif mutation == "sample":
        result["samples"][0]["delta_ns"] += 1
    elif mutation == "budget":
        stream["deadline_result"]["budget_ns"] = 1
    with pytest.raises(ValidationError):
        StageTraceSummaryV2.model_validate(value)


def test_manifest_cannot_relabel_v2_as_v1(tmp_path):
    for name in ("trace-manifest.json", "trace-record.json"):
        (tmp_path / name).write_bytes((FIXTURES / "paired" / name).read_bytes())
    manifest = fixture(member="trace-manifest.json")
    manifest["schema_version"] = 1
    manifest["trace_schema_version"] = "stage-trace-record-v1"
    (tmp_path / "trace-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="invalid_trace_bundle"):
        ingest_trace_bundle(tmp_path)
