"""Independent browser evidence, interior resets, missingness and protected import."""

import copy
import hashlib
import json
import os
from pathlib import Path

import jsonschema
import pytest

from latency_fingerprinting.cli import main
from latency_fingerprinting.live_probes import (
    GameBrowserProbeEvidence,
    import_game_browser_acquisition,
    inspect_game_browser_evidence,
)
from latency_fingerprinting.schemas import render_schema

from .game_browser_cases import META, acquisition, evidence


def test_literal_rates_resources_immutability_and_independent_identity():
    raw = acquisition()
    e = import_game_browser_acquisition(raw, **META)
    r = inspect_game_browser_evidence(e)
    assert r.engineering_screen == "met" and r.declared_restoration_supported
    assert r.controller_outcome_consistent and r.browser_counters_consistent
    assert r.presentation_counts_consistent and r.unrelated_settings_stable
    assert r.worker_during_to_baseline_cpu_ratio == pytest.approx(0.8)
    assert [p.worker_cpu_percent for p in r.phases] == pytest.approx([30, 24, 30])
    assert r.browser_cpu_percent == pytest.approx(20)
    assert not r.live_authority and r.evidence_role == "engineering"
    assert r.perceptual_quality == "not_evaluated" and r.capability == "unavailable_unqualified"
    body = e.model_dump(mode="json", exclude={"evidence_id", "content_hash"})
    canonical = (
        json.dumps(body, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()
    independent_hash = hashlib.sha256(canonical).hexdigest()
    assert e.content_hash == "sha256:" + independent_hash
    assert e.evidence_id == "game-browser-evidence-" + independent_hash
    assert GameBrowserProbeEvidence.model_validate_json(e.model_dump_json()) == e
    raw["report"]["resource_samples"][0]["game"]["cpu_ticks"] = 0
    raw["source_hashes"].clear()
    assert (
        e.acquisition.source_hashes and e.acquisition.report.resource_samples[0].game.cpu_ticks > 0
    )
    with pytest.raises(ValueError):
        e.acquisition.source_hashes[0].name = "other"
    with pytest.raises(ValueError):
        e.acquisition.report.windows.baseline.start.at_ns = 0


@pytest.mark.parametrize(
    "place,key,value",
    [
        ("root", "live_authority", True),
        ("root", "live_authority", 0),
        ("root", "clock_alignment", "aligned"),
        ("root", "browser_clock_basis", "utc"),
        ("root", "owner_pid", 5),
        ("report", "live_authority", "false"),
        ("report", "perceptual_quality", "qualified"),
        ("report", "workload", "other_game"),
        ("report", "dimensions", [640, 360]),
        ("report", "dimensions", [640.0, 480]),
        ("report", "receiver_timeline", [None] * 1201),
        ("report", "resource_samples", [None] * 513),
        ("report", "browser_stats", [None] * 129),
        ("root", "browser_resources", [None] * 129),
        ("root", "source_hashes", {f"x{i}": "f" * 64 for i in range(33)}),
    ],
)
def test_closed_scope_no_authority_and_bounds(place, key, value):
    raw = acquisition()
    (raw if place == "root" else raw["report"])[key] = value
    with pytest.raises(ValueError):
        import_game_browser_acquisition(raw, **META)


@pytest.mark.parametrize(
    "fault",
    [
        "clock",
        "window",
        "settling",
        "resource_bracket",
        "resource_duplicate",
        "source_path",
        "protocol",
        "boolean_counter",
        "fractional_counter",
    ],
)
def test_ambiguous_structure_rejected_before_sealing(fault):
    raw = acquisition()
    r = raw["report"]
    if fault == "clock":
        r["observations"][1]["at_ns"] = 0
    elif fault == "window":
        r["windows"]["baseline"]["start"]["capture_buffers"] += 1
    elif fault == "settling":
        r["receipts"][0]["after_ns"] = 4500000000
    elif fault == "resource_bracket":
        r["resource_samples"][0]["read_start_ns"] = 0
    elif fault == "resource_duplicate":
        r["resource_samples"].insert(1, copy.deepcopy(r["resource_samples"][0]))
    elif fault == "source_path":
        raw["source_hashes"]["../private.key"] = "f" * 64
    elif fault == "protocol":
        r["protocol"]["maximum_browser_frames_dropped"] = 1
    elif fault == "boolean_counter":
        r["browser_stats"][10]["values"]["framesDropped"] = False
    else:
        r["browser_stats"][10]["values"]["framesDecoded"] = 1.5
    with pytest.raises(ValueError):
        import_game_browser_acquisition(raw, **META)


@pytest.mark.parametrize(
    "fault",
    [
        "worker_reset",
        "game_reset",
        "browser_cpu_reset",
        "browser_inventory",
        "missing_cpu",
        "missing_hz",
        "resource_error",
    ],
)
def test_resource_resets_and_missingness_never_become_zero_cost(fault):
    raw = acquisition()
    r = raw["report"]
    if fault == "worker_reset":
        r["resource_samples"][4]["worker_cpu_ns"] = 0
    elif fault == "game_reset":
        r["resource_samples"][4]["game"]["cpu_ticks"] = 0
    elif fault == "browser_cpu_reset":
        raw["browser_resources"][1]["cpu_seconds"] = 0
    elif fault == "browser_inventory":
        raw["browser_resources"][1]["inventory_hash"] = "1" * 64
    elif fault == "missing_cpu":
        r["resource_samples"].pop(3)
    elif fault == "missing_hz":
        r.pop("resource_clock_ticks_per_second")
    else:
        raw["browser_resource_error"] = "counter_unavailable"
    result = inspect_game_browser_evidence(import_game_browser_acquisition(raw, **META))
    if fault in ("browser_cpu_reset", "browser_inventory", "resource_error"):
        assert result.browser_cpu_percent is None
    elif fault in ("missing_hz", "game_reset"):
        assert result.phases[1].game_cpu_percent is None
    else:
        assert result.phases[1].worker_cpu_percent is None
    assert not result.live_authority


@pytest.mark.parametrize(
    "fault",
    [
        "rtp_reset",
        "frozen",
        "missing_decode",
        "frame_epoch",
        "callback_gap",
        "settings",
        "count_forged",
        "black_measured",
        "missing_visual_window",
        "wrong_outcome",
        "unknown_cleanup",
        "missing_generation",
    ],
)
def test_raw_met_flag_cannot_hide_bad_or_incomplete_transport(fault):
    raw = acquisition()
    r = raw["report"]
    if fault == "rtp_reset":
        r["browser_stats"][25]["values"]["framesReceived"] = 0
    elif fault == "frozen":
        r["browser_stats"][25]["values"]["freezeCount"] = 1
    elif fault == "missing_decode":
        for s in r["browser_stats"]:
            s["values"]["framesDecoded"] = None
    elif fault == "frame_epoch":
        r["receiver_timeline"][150]["presented_frames"] = 1
    elif fault == "callback_gap":
        r["receiver_timeline"][150]["browser_at_ns"] += 900000000
    elif fault in ("settings", "count_forged"):
        key, value = (
            ("settings_hash", "1" * 64) if fault == "settings" else ("receiver_frames", 1000)
        )
        r["observations"][4][key] = value
    elif fault == "black_measured":
        r["visual_samples"][10]["color_bins"] = 1
    elif fault == "missing_visual_window":
        r["visual_samples"] = [s for s in r["visual_samples"] if s["worker_at_ns"] < 7300000000]
    elif fault == "wrong_outcome":
        r["result"].update(outcome="aborted", reason="health_abort")
    elif fault == "unknown_cleanup":
        raw["container_cleanup"] = "unknown"
    else:
        r["generation"] = None
    e = import_game_browser_acquisition(raw, **META)
    assert e.acquisition.report.assessment.status == "met"
    result = inspect_game_browser_evidence(e)
    assert result.engineering_screen != "met"
    assert not result.live_authority


def test_separate_clock_offsets_do_not_invent_alignment():
    raw = acquisition()
    for field in ("receiver_timeline", "browser_stats", "visual_samples"):
        for s in raw["report"][field]:
            s["browser_at_ns"] += 4000000000000
    for s in raw["browser_resources"]:
        s["host_at_ns"] += 1000000000000
    r = inspect_game_browser_evidence(import_game_browser_acquisition(raw, **META))
    assert r.engineering_screen == "met" and r.clock_alignment == "none"
    assert r.browser_cpu_percent == pytest.approx(20)


def test_short_declared_window_remains_evidence_but_cannot_complete_protocol():
    raw = acquisition()
    r = raw["report"]
    r["windows"]["baseline"]["start"] = copy.deepcopy(r["observations"][1])
    result = inspect_game_browser_evidence(import_game_browser_acquisition(raw, **META))
    assert result.phases[0].state == "incomplete" and result.engineering_screen == "incomplete"


def test_sham_cannot_fabricate_request_and_failed_setup_invents_nothing():
    raw = acquisition()
    raw["mode"] = raw["report"]["mode"] = "sham"
    with pytest.raises(ValueError):
        import_game_browser_acquisition(raw, **META)
    raw = acquisition()
    raw.update(report=None, worker_exit_code=125, failure="worker_failed")
    e = import_game_browser_acquisition(raw, **META)
    result = inspect_game_browser_evidence(e)
    assert result.phases == () and result.engineering_screen == "incomplete"
    assert not result.declared_restoration_supported


def test_missing_restore_or_dirty_ledger_never_gets_getter_based_recovery():
    for fault in ("missing", "dirty"):
        raw = acquisition()
        r = raw["report"]
        if fault == "missing":
            r["windows"].pop("restoration")
        else:
            r["journal_state"] = "dirty"
        assert not inspect_game_browser_evidence(
            import_game_browser_acquisition(raw, **META)
        ).declared_restoration_supported


def test_content_and_source_manifest_tamper_rejected():
    for location in ("root", "manifest", "sample"):
        raw = evidence().model_dump(mode="json")
        if location == "root":
            raw["evidence_role"] = "final_test"
        elif location == "manifest":
            raw["acquisition"]["source_hashes"][0]["sha256"] = "1" * 64
        else:
            raw["acquisition"]["report"]["resource_samples"][0]["worker_cpu_ns"] = 0
        with pytest.raises(ValueError):
            GameBrowserProbeEvidence.model_validate(raw)
    with pytest.raises(ValueError):
        GameBrowserProbeEvidence.model_validate_json('{"x":NaN,"x":1}')


def test_cli_generic_validation_schema_and_no_input_overwrite(tmp_path, capsys):
    source = tmp_path / "acquisition.json"
    output = tmp_path / "evidence.json"
    source.write_text(json.dumps(acquisition()))
    args = ["import-game-browser-report", "--report", str(source), "--output", str(output)]
    for key, value in META.items():
        args += ["--" + key.replace("_", "-"), value]
    assert main(args) == 0 and capsys.readouterr().out == ""
    actual = GameBrowserProbeEvidence.model_validate_json(output.read_bytes())
    assert actual == evidence()
    assert main(["validate", str(output)]) == 0
    assert json.loads(capsys.readouterr().out) == actual.model_dump(mode="json")
    schema = json.loads(render_schema(GameBrowserProbeEvidence))
    jsonschema.validate(actual.model_dump(mode="json"), schema)
    for alias in ("same", "hardlink", "symlink"):
        target = tmp_path / alias
        if alias == "same":
            target = source
        elif alias == "hardlink":
            os.link(source, target)
        else:
            target.symlink_to(source)
        retained = source.read_bytes()
        args[args.index("--output") + 1] = str(target)
        assert main(args) == 1
        assert source.read_bytes() == retained
        assert (
            capsys.readouterr().err
            == "error: import-game-browser-report: invalid_input_or_output\n"
        )


def test_additive_schema_preserves_all_previous_38_bytes():
    previous = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in Path("schemas").glob("*.schema.json")
        if p.name
        not in {
            "game-browser-probe-evidence-v1.schema.json",
            "integrated-game-cohort-record-v1.schema.json",
        }
    }
    assert len(previous) == 38
    assert (
        hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest()
        == "b1be216932206f5d897851eb4913f0a315a43ef5994668020c2789777a1f3364"
    )
