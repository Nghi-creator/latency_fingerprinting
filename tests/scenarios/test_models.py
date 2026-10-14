"""Independent success/failure tables and adversarial detached-root boundaries."""

import json
import subprocess
import sys
from copy import deepcopy
from fractions import Fraction

import jsonschema
import pytest
from pydantic import ValidationError

from latency_fingerprinting.models import (
    ExperimentManifest,
    ExperimentPhaseEvidence,
    ExperimentResult,
)
from latency_fingerprinting.pipeline import canonical_json
from latency_fingerprinting.schemas import render_schema

from .cases import SECOND, aborted, evidence, manifest, result, unsupported

ROOTS = [
    (ExperimentManifest, manifest),
    (ExperimentPhaseEvidence, evidence),
    (ExperimentResult, result),
]


def set_path(value, path, replacement):
    target = value
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replacement


@pytest.mark.parametrize(("model", "factory"), ROOTS)
def test_roundtrip_schema_immutable_public_roots(model, factory):
    value = factory()
    parsed = model.model_validate(value)
    encoded = canonical_json(parsed)
    assert model.model_validate_json(encoded) == parsed
    jsonschema.Draft202012Validator(json.loads(render_schema(model))).validate(value)
    assert encoded.endswith("\n") and not encoded.endswith("\n\n")
    with pytest.raises(ValidationError):
        parsed.run_id = "run-2"
    value["run_id"] = "run-2"
    assert parsed.run_id == "run-1"
    copied = parsed.model_copy(update={"run_id": "run-0"})
    with pytest.raises(ValidationError):
        model.model_validate(copied)


@pytest.mark.parametrize(("model", "factory"), ROOTS)
@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("schema_version", "future-v1"),
        ("method_release", "n5-single-cause-v2"),
        ("run_id", "run-01"),
        ("run_id", "run-2147483648"),
        ("run_id", "run-1\n"),
        ("private_note", "secret"),
    ],
)
def test_closed_required_identity_fields(model, factory, field, bad):
    value = factory()
    value[field] = bad
    with pytest.raises(ValidationError):
        model.model_validate(value)


@pytest.mark.parametrize(("model", "factory"), ROOTS)
def test_every_field_required(model, factory):
    for field in factory():
        value = factory()
        del value[field]
        with pytest.raises(ValidationError):
            model.model_validate(value)


@pytest.mark.parametrize(
    ("path", "bad"),
    [
        (("seed",), True),
        (("seed",), "7"),
        (("seed",), 2**32),
        (("repeat_index",), 0),
        (("runtime", "width"), 1280.0),
        (("runtime", "height"), "720"),
        (("runtime", "fps"), 30.0),
        (("runtime", "cpu_allocation"), True),
        (("runtime", "cpu_allocation"), 65),
        (("runtime", "clock_resolution_ns"), 0),
        (("runtime", "kind"), "linux_x11"),
        (("runtime", "python_version"), "03.14.4"),
        (("runtime", "gst_version"), "1000.0.0"),
        (("runtime", "node_version"), "26.4.0\n"),
        (("core_version",), "a" * 40 + "\n"),
        (("producer_version",), "B" * 40),
        (("adapter", "state"), "unavailable"),
        (("adapter", "adapter_id"), "none"),
        (("actions", 0, "kind"), "shell"),
        (("actions", 0, "workers"), 3),
        (("actions", 0, "workers"), 0),
        (("actions", 0, "max_duration_ns"), 60 * SECOND),
        (("phases", 0, "phase"), "healthy"),
        (("phases", 0, "duration_ns"), SECOND - 1),
        (("phases", 0, "duration_ns"), 301 * SECOND),
        (("trace_policy", "max_frames"), 2001),
        (("trace_policy", "max_events"), 10001),
        (("trace_policy", "scope"), "per_run"),
        (("trace_policy", "every_nth_frame"), 0),
        (("trace_policy", "max_frames"), 899),
        (("trace_policy", "max_events"), 4499),
        (("actions",), []),
    ],
)
def test_manifest_failures(path, bad):
    value = manifest()
    set_path(value, path, bad)
    with pytest.raises(ValidationError):
        ExperimentManifest.model_validate(value)


def test_manifest_scenario_capabilities_and_exact_capacity():
    ExperimentManifest.model_validate(manifest("healthy"))
    value = manifest("network_delay")
    value["adapter"].update(adapter_id=None, state="unavailable", reason="adapter_not_implemented")
    ExperimentManifest.model_validate(value)
    value["adapter"].update(state="available", reason=None)
    with pytest.raises(ValidationError):
        ExperimentManifest.model_validate(value)
    value = manifest()
    value["adapter"].update(state="unavailable", reason="permission_denied")
    ExperimentManifest.model_validate(
        value
    )  # Requested action is retained despite unavailable preflight.
    value = manifest("healthy")
    for phase in value["phases"]:
        phase["duration_ns"] = 300 * SECOND
    with pytest.raises(ValidationError, match="watchdog"):
        ExperimentManifest.model_validate(value)
    value = manifest("healthy")
    value["phases"][1]["duration_ns"] = 300 * SECOND
    with pytest.raises(ValidationError, match="capacity"):
        ExperimentManifest.model_validate(value)
    value["trace_policy"]["every_nth_frame"] = 5
    ExperimentManifest.model_validate(value)
    value = manifest()
    value["phases"][2]["duration_ns"] = 290 * SECOND
    with pytest.raises(ValidationError, match="pressure duration"):
        ExperimentManifest.model_validate(value)
    value = manifest()
    value["trace_policy"].update(max_frames=900, max_events=4500)
    ExperimentManifest.model_validate(value)
    value["phases"][1]["duration_ns"] += 1
    with pytest.raises(ValidationError, match="capacity"):
        ExperimentManifest.model_validate(value)  # Exact integer ceiling, even for one nanosecond.


@pytest.mark.parametrize(
    "phase", ("warmup", "healthy", "degraded", "probe", "recovery", "cooldown")
)
def test_independent_evidence_arithmetic(phase):
    value = ExperimentPhaseEvidence.model_validate(evidence(phase))
    wall = sum(i.end_ns - i.start_ns for i in value.intervals)
    frames = sum(i.frames_end - i.frames_start for i in value.intervals)
    cpu = sum(i.worker_cpu_ns for i in value.intervals)
    assert Fraction(frames * SECOND, wall) == (24 if phase in ("degraded", "probe") else 30)
    assert Fraction(cpu * 100, wall) == (60 if phase in ("degraded", "probe") else 0)


@pytest.mark.parametrize(
    ("path", "bad"),
    [
        (("manifest_sha256",), "C" * 64),
        (("end_ns",), 0),
        (("reason",), "counter_reset"),
        (("intervals", 0, "start_ns"), 41 * SECOND),
        (("intervals", 0, "end_ns"), 40 * SECOND + 499_999_999),
        (("intervals", 0, "end_ns"), 46 * SECOND),
        (("intervals", 0, "frames_end"), 1199),
        (("intervals", 1, "frames_start"), 0),
        (("intervals", 0, "active_workers"), 0),
        (("intervals", 0, "active_workers"), 9),
        (("intervals", 0, "worker_cpu_ns"), SECOND + 1),
        (("intervals", 0, "worker_cpu_ns"), True),
        (("intervals", 0, "frames_start"), 2**53),
        (("intervals",), []),
    ],
)
def test_evidence_failures(path, bad):
    value = evidence()
    set_path(value, path, bad)
    with pytest.raises(ValidationError):
        ExperimentPhaseEvidence.model_validate(value)


@pytest.mark.parametrize(
    "reason",
    (
        "source_unavailable",
        "counter_reset",
        "clock_error",
        "collection_gap",
        "cancelled",
        "timeout",
    ),
)
def test_partial_unavailable_evidence_retains_only_prefix(reason):
    value = evidence()
    value.update(state="partial", reason=reason)
    value["intervals"] = value["intervals"][:25]
    ExperimentPhaseEvidence.model_validate(value)
    value["intervals"] = []
    ExperimentPhaseEvidence.model_validate(value)
    value["state"] = "unavailable"
    ExperimentPhaseEvidence.model_validate(value)
    value["intervals"] = evidence()["intervals"][:1]
    with pytest.raises(ValidationError):
        ExperimentPhaseEvidence.model_validate(value)


@pytest.mark.parametrize(
    ("path", "bad"),
    [
        (("reason",), "cancelled"),
        (("phases", 0, "start_ns"), 1),
        (("phases", 1, "phase"), "probe"),
        (("phases", 1, "state"), "partial"),
        (("phases", 0, "end_ns"), 0),
        (("phases", 0, "end_ns"), 303 * SECOND),
        (("phases", 5, "end_ns"), 1201 * SECOND),
        (("phases", 2, "start_ns"), 39 * SECOND),
        (("phases", 3, "start_ns"), 71 * SECOND),
        (("phases", 4, "start_ns"), 106 * SECOND),
        (("actions", 0, "started_ns"), 39 * SECOND),
        (("actions", 0, "stopped_ns"), 99 * SECOND),
        (("actions", 0, "state"), "started"),
        (("actions", 0, "reason"), "stop_failed"),
        (("cleanup", "ended_ns"), 102 * SECOND),
        (("cleanup", "owned_workers_remaining"), 1),
        (("cleanup", "started_ns"), 90 * SECOND),
        (("cleanup", "state"), "not_required"),
        (("artifacts", 0, "file_name"), "../artifact-1.json"),
        (("artifacts", 0, "file_name"), "artifact-2.json"),
        (("artifacts", 0, "schema_version"), "observation-window-v2"),
        (("artifacts", 0, "bytes"), 0),
        (("artifacts", 0, "bytes"), 10 * 1024**2 + 1),
        (("artifacts", 6, "phase"), "warmup"),
        (("artifacts",), []),
        (("effect", "healthy_fps"), None),
        (("effect", "healthy_fps"), "30"),
        (("effect", "healthy_fps"), True),
        (("effect", "healthy_fps"), float("inf")),
        (("effect", "degraded_fps"), -1.0),
        (("effect", "reason"), "pressure_not_observed"),
    ],
)
def test_result_failures(path, bad):
    value = result()
    set_path(value, path, bad)
    with pytest.raises(ValidationError):
        ExperimentResult.model_validate(value)


def test_cancelled_and_unsupported_independent_records():
    ExperimentResult.model_validate(aborted())
    ExperimentResult.model_validate(unsupported())
    value = unsupported()
    value["effect"]["healthy_fps"] = 0.0
    with pytest.raises(ValidationError):
        ExperimentResult.model_validate(value)
    value = aborted()
    value["effect"].update(state="verified", reason=None)
    with pytest.raises(ValidationError):
        ExperimentResult.model_validate(value)
    value = aborted()
    value["artifacts"].append(result()["artifacts"][3])
    with pytest.raises(ValidationError):
        ExperimentResult.model_validate(value)


@pytest.mark.parametrize(
    "reason",
    (
        "baseline_inadequate",
        "pressure_not_observed",
        "degradation_not_observed",
        "recovery_not_observed",
    ),
)
def test_failed_effect_is_valid_execution_not_diagnosis(reason):
    value = result()
    value["effect"].update(state="failed", reason=reason)
    ExperimentResult.model_validate(value)  # Linked arithmetic is deferred to bundle inspection.


def test_cleanup_failure_action_state_and_reference_integrity():
    value = aborted()
    value.update(reason="cleanup_failed")
    value["cleanup"].update(state="failed", reason="stop_failed", owned_workers_remaining=1)
    value["actions"][0].update(state="failed", reason="stop_failed", stopped_ns=None)
    ExperimentResult.model_validate(value)
    value = result()
    value["artifacts"][1].update(role="phase_evidence", phase="warmup")
    with pytest.raises(ValidationError, match="duplicate"):
        ExperimentResult.model_validate(value)
    value = result()
    value["artifacts"].reverse()
    with pytest.raises(ValidationError, match="increasing"):
        ExperimentResult.model_validate(value)
    value = result()
    value["actions"][0]["stopped_ns"] = None
    value["actions"][0].update(state="failed", reason="exit_failed")
    with pytest.raises(ValidationError, match="unstopped"):
        ExperimentResult.model_validate(value)


@pytest.mark.parametrize(
    ("model", "factory", "field", "limit"),
    [
        (ExperimentManifest, manifest, "phases", 6),
        (ExperimentManifest, manifest, "actions", 6),
        (ExperimentResult, result, "phases", 6),
        (ExperimentResult, result, "actions", 6),
        (ExperimentResult, result, "artifacts", 18),
        (ExperimentPhaseEvidence, evidence, "intervals", 1200),
    ],
)
def test_bounds_before_elements_and_revalidate_mutable_copies(model, factory, field, limit):
    value = factory()
    value[field] = [object()] * (limit + 1)
    with pytest.raises(ValidationError, match="bounded list"):
        model.model_validate(value)
    value[field] = iter([])
    with pytest.raises(ValidationError, match="bounded list"):
        model.model_validate(value)
    original = model.model_validate(factory())
    mutable = deepcopy(factory()[field])
    copied = original.model_copy(update={field: mutable})
    validated = model.model_validate(copied)
    assert isinstance(getattr(validated, field), tuple)
    mutable.clear()
    assert getattr(validated, field) == getattr(original, field)


@pytest.mark.parametrize(("model", "factory"), ROOTS)
def test_bounded_duplicate_safe_utf8_json(model, factory):
    text = json.dumps(factory())
    duplicate = text.replace('"run_id": "run-1"', '"run_id": "run-1", "run_id": "run-2"')
    for bad in (duplicate, b"\xff", "[" * 33 + "0" + "]" * 33, " " * (10 * 1024**2 + 1)):
        with pytest.raises((ValueError, ValidationError)):
            model.model_validate_json(bad)
    assert model.model_validate_json(text.encode()) == model.model_validate(factory())


@pytest.mark.parametrize(("model", "factory"), ROOTS)
def test_generic_cli_and_schema_export(model, factory, tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(factory()))
    process = subprocess.run(  # noqa: S603 - fixed local module and test-owned JSON.
        [
            sys.executable,
            "-m",
            "latency_fingerprinting",
            "validate",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert process.stdout == canonical_json(model.model_validate(factory()))
    assert process.stderr == ""


def test_float_negative_zero_and_nested_copy_revalidation():
    value = result()
    value["effect"]["pressure_cpu_percent"] = -0.0
    parsed = ExperimentResult.model_validate(value)
    assert "-0.0" not in canonical_json(parsed)
    copied_runtime = ExperimentManifest.model_validate(manifest()).runtime.model_copy(
        update={"fps": 30.0}
    )
    copied = ExperimentManifest.model_validate(manifest()).model_copy(
        update={"runtime": copied_runtime}
    )
    with pytest.raises(ValidationError):
        ExperimentManifest.model_validate(copied)


@pytest.mark.parametrize(
    ("state", "start", "stop", "reason"),
    [
        ("not_started", None, None, None),
        ("started", 40 * SECOND, None, None),
        ("stopped", 40 * SECOND, 65 * SECOND, None),
        ("failed", None, None, "start_failed"),
        ("failed", 40 * SECOND, None, "exit_failed"),
        ("failed", 40 * SECOND, 65 * SECOND, "cancelled"),
    ],
)
def test_aborted_action_lifecycle_prefix(state, start, stop, reason):
    value = aborted()
    value["actions"][0].update(state=state, started_ns=start, stopped_ns=stop, reason=reason)
    if start is None:
        value["cleanup"].update(state="not_required", started_ns=None, ended_ns=None)
    elif stop is None:
        value["cleanup"].update(
            state="unverified", reason="missing_evidence", owned_workers_remaining=None
        )
    ExperimentResult.model_validate(value)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"state": "not_started", "started_ns": 1, "stopped_ns": None}, "not-started"),
        ({"state": "started", "started_ns": None, "stopped_ns": None}, "only start"),
        ({"state": "stopped", "started_ns": None, "stopped_ns": None}, "both times"),
        (
            {"state": "failed", "started_ns": None, "stopped_ns": 1, "reason": "stop_failed"},
            "ordered",
        ),
        ({"state": "failed", "started_ns": 2, "stopped_ns": 1, "reason": "stop_failed"}, "ordered"),
    ],
)
def test_invalid_action_states(changes, match):
    value = aborted()
    value["actions"][0].update(changes)
    with pytest.raises(ValidationError, match=match):
        ExperimentResult.model_validate(value)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        (
            {
                "state": "not_required",
                "started_ns": None,
                "ended_ns": None,
                "owned_workers_remaining": 1,
            },
            "zero remaining",
        ),
        ({"state": "restored", "started_ns": None, "ended_ns": None}, "timing evidence"),
        ({"state": "failed", "reason": None}, "state/reason"),
    ],
)
def test_invalid_cleanup_states(changes, match):
    value = aborted()
    value["cleanup"].update(changes)
    with pytest.raises(ValidationError, match=match):
        ExperimentResult.model_validate(value)


def test_healthy_control_and_unverified_restoration():
    value = result()
    value["actions"] = []
    value["effect"].update(degraded_fps=30.0, pressure_cpu_percent=None)
    value["cleanup"].update(state="not_required", started_ns=None, ended_ns=None)
    ExperimentResult.model_validate(value)
    value["cleanup"].update(
        state="unverified", reason="missing_evidence", owned_workers_remaining=None
    )
    with pytest.raises(ValidationError, match="restoration"):
        ExperimentResult.model_validate(value)
    value["effect"].update(state="unavailable", reason="cleanup_unverified")
    ExperimentResult.model_validate(value)  # Completed execution is not a successful trial.


def test_completed_evidence_must_cover_last_interval_and_action_cleanup_order():
    value = evidence()
    value["intervals"].pop()
    with pytest.raises(ValidationError, match="entire phase"):
        ExperimentPhaseEvidence.model_validate(value)
    value = result()
    value["cleanup"].update(started_ns=99 * SECOND, ended_ns=99 * SECOND)
    with pytest.raises(ValidationError, match="stop must precede"):
        ExperimentResult.model_validate(value)
    value = aborted()
    value["actions"][0].update(state="not_started", started_ns=None, stopped_ns=None)
    value["cleanup"].update(state="not_required", started_ns=None, ended_ns=None)
    ExperimentResult.model_validate(value)


@pytest.mark.parametrize(("model", "factory"), ROOTS)
def test_nested_required_fields_extra_rejection_and_instance_mutations(model, factory):
    value = factory()
    field = (
        "runtime"
        if model is ExperimentManifest
        else "effect"
        if model is ExperimentResult
        else "intervals"
    )
    nested = value[field][0] if field == "intervals" else value[field]
    for name in tuple(nested):
        candidate = deepcopy(value)
        target = candidate[field][0] if field == "intervals" else candidate[field]
        del target[name]
        with pytest.raises(ValidationError):
            model.model_validate(candidate)
    nested["notes"] = "private"
    with pytest.raises(ValidationError):
        model.model_validate(value)


@pytest.mark.parametrize(("model", "factory"), ROOTS)
def test_cli_rejects_duplicate_keys_and_unknown_version(model, factory, tmp_path, capsys):
    from latency_fingerprinting.cli import main

    path = tmp_path / "record.json"
    text = json.dumps(factory()).replace(
        '"run_id": "run-1"', '"run_id": "run-1", "run_id": "run-2"'
    )
    path.write_text(text)
    assert main(["validate", str(path)]) != 0
    assert capsys.readouterr().out == ""
    value = factory()
    value["schema_version"] = "experiment-result-v99"
    path.write_text(json.dumps(value))
    assert main(["validate", str(path)]) != 0
    assert capsys.readouterr().out == ""
