"""Invented whole-case fixture through real producer ports and all replay gates."""

import argparse
import bisect
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from experiments.n11.physical_challenges.qualify import qualify_case


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def invented_source(producer, recipe):
    runtime = producer / "engine/runtime"
    sys.path[:0] = [str(runtime), str(runtime / "tests/python")]
    from qualification.observation.test_challenge_channel import ChannelTests
    from research.live_probe_control.control.contracts import Generation
    from research.physical_challenges.observer import ChallengeObservation

    f = ChannelTests("test_files_execute_complete_request_ack_transcript")
    try:
        handle, _ = f.make(recipe)
        clock = f.fixture.clock
        events = []
        samples = {}
        identity = {"first": "a" * 64}
        generation = f.fixture.generation
        context = dict(
            method="n11-physical-challenge-observation-v1",
            generation=generation,
            controller_origin_ns="0",
        )
        cpu_clock = "controller-monotonic-" + digest(context)
        o = ChallengeObservation.__new__(ChallengeObservation)
        o.pacer, o.origin, o.now = handle, 0, clock
        o.emit = lambda kind, **fields: events.append(dict(kind=kind, **fields))
        events.append(
            dict(
                kind="n11_challenge_resource_context",
                context=context,
                clock_id=cpu_clock,
                live_authority=False,
            )
        )

        def reference(phase):
            rows = []
            for _ in range(4):
                clock.advance(1.1)
                state = handle.sample(fresh=True)
                rows.append(dict(at_ns=clock.ns, condition_state=state))
            samples[phase] = rows
            events.append(
                dict(
                    kind="n11_challenge_reference",
                    phase=phase,
                    samples=rows,
                    worker_identities=identity,
                    live_authority=False,
                )
            )
            clock.advance(0.01)

        reference("healthy")
        o._send("start")
        handle.wait_established()
        dispatch = None
        for phase in ("degraded", "relief", "recovery"):
            if phase == "relief":
                o._send("prepare_relief")
                handle.wait_established()
                dispatch = clock.ns
                o._send("dispatch_relief")
                events.append(
                    dict(
                        kind="n11_pair_dispatched",
                        at_ns=dispatch,
                        live_authority=False,
                        request=dict(
                            generation=generation,
                            request_id="synthetic-request",
                            target_fps=24,
                            duration_ns=5_000_000_000,
                        ),
                    )
                )
            if phase == "recovery":
                clock.advance(max(0, (dispatch + 5_010_000_000 - clock.ns) / 1e9))
                result = dict(
                    request_id="synthetic-request",
                    outcome="completed",
                    restoration="verified_by_port",
                    reason="duration_elapsed",
                    live_authority=False,
                )
                events.extend(
                    [
                        dict(
                            kind="n11_pair_result",
                            at_ns=clock.ns,
                            result=result,
                            ledger_state="clean",
                            actions=1,
                            reserved_ns=7_000_000_000,
                        ),
                        dict(
                            kind="n11_pair_journal",
                            state="clean",
                            actions=1,
                            reserved_ns=7_000_000_000,
                            operation_done=True,
                            content_hash="d" * 64,
                            result=result,
                        ),
                    ]
                )
            o._send("begin_" + phase)
            start = clock.ns
            events.append(
                dict(
                    kind="n11_pair_phase_started",
                    phase=phase,
                    at_ns=start,
                    worker_identities=identity,
                    live_authority=False,
                    action_elapsed_ns=start - dispatch if phase == "relief" else None,
                )
            )
            rows = []
            for i in range(4):
                at = start + 1_000_000 + i * 1_060_000_000
                clock.advance((at - clock.ns) / 1e9)
                row = dict(kind="n11_pair_native", phase=phase, at_ns=clock.ns)
                rows.append(row)
                events.append(row)
            clock.advance((start + 3_200_000_000 - clock.ns) / 1e9)
            events.append(
                dict(
                    kind="n11_pair_phase_completed",
                    phase=phase,
                    at_ns=clock.ns,
                    action_elapsed_ns=clock.ns - dispatch if phase == "relief" else None,
                )
            )
            samples[phase] = rows
            o._send("end_" + phase)
        o._send("close")
        reference("post")
        events.append(
            dict(
                kind="n11_challenge_command_transcript",
                transcript=handle.transcript,
                live_authority=False,
            )
        )
        bounds = {
            p: tuple(
                next(e["at_ns"] for e in events if e.get("phase") == p and e["kind"] == kind)
                for kind in ("n11_pair_phase_started", "n11_pair_phase_completed")
            )
            for p in ("degraded", "relief", "recovery")
        }
        # Invented callbacks and counters, not measurements from actual media.
        times = []
        at = 1_000_000
        while at < clock.ns + 100_000_000:
            fps = 24 if bounds["relief"][0] <= at <= bounds["relief"][1] else 30
            at += 1_000_000_000 // fps
            times.append(at)
        trace_rows = [[i + 1, t - 10, t] for i, t in enumerate(times)]
        media = []
        seq = 0
        current = {}
        o.resource_context = context
        o.resource_sampler = SimpleNamespace(sample=lambda: current["cpu"])
        o.sampler_factory = lambda **kwargs: SimpleNamespace(sample=lambda: current["cpu"])
        slot = SimpleNamespace(owner=SimpleNamespace(generation=Generation(**generation)))
        for phase in ("healthy", "degraded", "relief", "recovery", "post"):
            o.challenge_stage = phase if phase in ("healthy", "post") else "pair"
            o.stage = "measure"
            o.phase = phase
            for row in samples[phase]:
                at = row["at_ns"]
                lo, hi = at - 1000, at - 1
                count = bisect.bisect_right(times, lo)
                fps = 24 if phase == "relief" else 30
                row.update(
                    sequence=seq,
                    configured_fps=fps,
                    negotiated_fps=fps,
                    capture_buffers=count,
                    encoded_buffers=count,
                )
                current["cpu"] = dict(
                    method="n11-private-cgroup-cpu-read-candidate-v1",
                    scope="private_container_cpu_counters_not_ownership_or_diagnosis",
                    clock_id=cpu_clock,
                    sequence=seq,
                    read_start_ns=at,
                    read_end_ns=at + 100,
                    source_identity={
                        k: dict(device=1, inode=i + 1)
                        for i, k in enumerate(("cgroup", "cpu.stat", "cpu.max"))
                    },
                    quota=dict(quota_usec=200000, period_usec=100000),
                    counters=dict(
                        usage_usec=0,
                        user_usec=0,
                        system_usec=0,
                        nr_periods=seq,
                        nr_throttled=0,
                        throttled_usec=0,
                    ),
                    counter_units="microseconds_for_usec_fields_counts_for_nr_fields",
                    underlying_counter_freshness="not_authenticated_by_read_brackets",
                    source_authenticity="declared_namespace_quota_and_file_identity_only",
                    live_authority=False,
                )
                row.update(
                    o.native_read_evidence(
                        slot,
                        dict(
                            read_start_ns=lo,
                            read_end_ns=hi,
                            encoded_buffers=count,
                            encoded_counter_read=dict(
                                method="native-encoded-counter-read-brackets-v1",
                                read_start_ns=lo,
                                read_end_ns=hi,
                                value=count,
                            ),
                        ),
                    )
                )
                media.append(
                    dict(
                        sequence=seq,
                        controller_received_ns=at - 1,
                        read_start_ns=lo,
                        read_end_ns=hi,
                        configured_fps=fps,
                        negotiated_fps=fps,
                        capture_buffers=count,
                        encoded_buffers=count,
                    )
                )
                seq += 1
        boundaries = []
        windows = {}
        for phase in ("healthy", "degraded", "relief", "recovery", "post"):
            lo, hi = (
                bounds[phase]
                if phase in bounds
                else (samples[phase][0]["at_ns"], samples[phase][-1]["at_ns"])
            )
            windows[phase] = dict(phase_start_ns=lo, phase_end_ns=hi)
            boundaries.extend(
                dict(phase=phase, edge=edge, at_ns=t) for edge, t in (("start", lo), ("end", hi))
            )
        n = len(times)
        read = times[-1] + 10_000_000
        events.append(
            dict(
                kind="n11_encoded_event_trace",
                method="n11-contained-encoded-event-trace-v1",
                state="count_reconciled",
                reason_codes=[],
                worker_clock_id="worker-monotonic-" + digest(generation),
                controller_origin_ns="0",
                controller_time_namespace="time:[123]",
                controller_boundaries=boundaries,
                windows=windows,
                trace=dict(
                    origin_ns="0",
                    time_namespace="time:[123]",
                    buffer_list=False,
                    observed=n,
                    rows=trace_rows,
                    identity_read=dict(
                        start_ns=read, end_ns=read + 1, count=n, observed_before=n, observed_after=n
                    ),
                ),
                live_authority=False,
            )
        )
        browser = []
        bridge = []
        relay = []
        owners = []
        workers = []
        for i, at in enumerate(range(0, clock.ns + 200_000_000, 200_000_000)):
            browser.append(
                dict(sequence=i, elapsed_ns=at, frames_decoded=i * 5, presented_frames=i * 5)
            )
            bridge.append(
                dict(
                    sequence=i,
                    browser_elapsed_ns=at,
                    received_ns=at,
                    checked_ns=at + 1,
                    local_sequence=None if i == 0 else i - 1,
                    accepted=True,
                )
            )
            relay.append(
                dict(sequence=i, received_ms=1700000000000 + i * 200, decision="forwarded")
            )
            if dispatch <= at <= dispatch + 5_000_000_000:
                owners.append(dict(sequence=i - 1, observed_ns=at, queued_ns=at + 2))
                workers.append(dict(sequence=i - 1, observed_ns=at, received_ns=at + 3))
        events.extend(
            [
                dict(
                    kind="n11_receiver_delivery",
                    bridge=bridge,
                    owner=owners,
                    worker=workers,
                    basis="browser_elapsed_separate_from_linux_monotonic",
                    live_authority=False,
                ),
                dict(
                    kind="n11_relay_receiver_delivery",
                    rows=relay,
                    basis="relay_wall_clock_ms_separate_from_browser_and_camera_clocks",
                ),
                dict(
                    kind="n11_worker_media_progress",
                    rows=media,
                    basis="worker_read_brackets_and_controller_receipt_separate_from_browser_clock",
                    live_authority=False,
                ),
            ]
        )
        return dict(
            synthetic_fixture=True,
            status="passed",
            method="n11-physical-challenge-acquisition-v1",
            role="engineering_challenge_raw_phases_no_pair_or_diagnostic_label",
            mode="engineering-n11-physical-challenge-" + recipe,
            challenge_recipe=recipe,
            live_authority=False,
            events=events,
            receiver_delivery_browser=browser,
        )
    finally:
        f.doCleanups()


NODE = """
import fs from 'node:fs/promises';
const [root,d,recipe]=process.argv.slice(1),runtime=root+'/engine/runtime/';
const {preparePhysicalChallengePlan}=await import('file://'+runtime+'scripts/research/n11/acquisition/physicalChallengeObservation.mjs');
const {freezeSourceFiles}=await import('file://'+runtime+'scripts/research/n11/acquisition/rawObservation.mjs');
const {fixture}=await import('file://'+runtime+'scripts/research/n11/receipts/physicalChallengeMediaFixture.mjs');
const {phaseHash}=await import('file://'+runtime+'scripts/research/n11/browser/challengePhaseCustody.mjs');
const {createPhysicalChallengeRawExport}=await import('file://'+runtime+'scripts/research/n11/export/physicalChallengeRawExport.mjs');
const json=v=>JSON.stringify(v,null,2)+'\\n';
const id='n11-raw-synthetic-'+recipe.replaceAll('_','-');
await fs.writeFile(d+'/exclusions.json',json({
 excluded_case_ids:['n11-raw-synthetic-excluded'],retry_allowed:false}));
const p=await preparePhysicalChallengePlan(['--image','sha256:'+'f'.repeat(64),
 '--acquisition-id',id,'--core-revision','a'.repeat(40),'--recipe',recipe,
 '--exclusions',d+'/exclusions.json','--output',d+'/plan.json']);
await freezeSourceFiles(d,p.source_sha256);
const a=JSON.parse(await fs.readFile(d+'/invented.json')),m=fixture(recipe,id);
a.context={image:p.image,software_hash:p.native_software_hash,host_platform:process.platform,host_arch:process.arch};
a.paired_observation=m.paired_observation;
a.events.push(...m.events.filter(e=>['camera_ready','control_capture_bound','complete','host_shutdown'].includes(e.kind)));
for(const raw of a.paired_observation.phases){
 const start=a.events.find(e=>e.kind==='n11_pair_phase_started'&&e.phase===raw.phase);
 const c=m.events.find(e=>e.kind==='n11_challenge_browser_phase_custody'&&e.phase===raw.phase);
 a.events.push({...c,native_phase_start_sha256:phaseHash(start)});
}
const ab=Buffer.from(json(a)),pb=await fs.readFile(d+'/plan.json');
await fs.writeFile(d+'/acquisition.json',ab);
await fs.writeFile(d+'/raw-export.json',json(createPhysicalChallengeRawExport(ab,pb)));
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    producer = args.producer.resolve()
    args.output_directory.mkdir()
    node = shutil.which("node")
    if node is None:
        raise ValueError("Node.js required")
    results = []
    for recipe in (
        "mixed_delay_pressure",
        "delay_to_pressure",
        "pressure_to_delay",
        "control_no_injected_fault",
        "control_owned_identity_delay",
        "control_owned_cpu_pressure",
    ):
        directory = args.output_directory / recipe
        directory.mkdir()
        (directory / "invented.json").write_text(json.dumps(invented_source(producer, recipe)))
        subprocess.run(  # noqa: S603
            [
                node,
                "--input-type=module",
                "-e",
                NODE,
                str(producer),
                str(directory.resolve()),
                recipe,
            ],
            check=True,
            timeout=60,
        )
        report = qualify_case(directory, producer)
        expected = (
            "rejected_changing_pair" if "_to_" in recipe else "descriptive_phase_rates_available"
        )
        if report["projection"]["state"] != expected:
            raise ValueError("unexpected synthetic projection state")
        (directory / "qualification.json").write_text(json.dumps(report, indent=2) + "\n")
        results.append(dict(recipe=recipe, state=report["projection"]["state"]))
    (args.output_directory / "results.json").write_text(
        json.dumps(dict(synthetic=True, native_cases=0, results=results), indent=2) + "\n"
    )
    print(json.dumps(results))


if __name__ == "__main__":
    main()
