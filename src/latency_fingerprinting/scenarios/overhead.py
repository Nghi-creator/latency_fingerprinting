"""Frozen N4 overhead arithmetic from raw process counters and hash-bound traces."""

import hashlib
import json
import os
import tempfile
from fractions import Fraction
from pathlib import Path

from ..observability.bundle import ingest_trace_bundle
from ..observability.output import write_trace_output
from .campaign import CampaignPlan, _snapshot
from .contracts import SECOND
from .overhead_models import OverheadEvidence, OverheadReport


def measure_cpu(item):
    return Fraction(item.cpu_ns * 100, item.wall_ns)


def measure_fps(item):
    return Fraction((item.frames_end - item.frames_start) * SECOND, item.wall_ns)


def _usable_pair(endpoints, start, end):
    return start in endpoints and end in endpoints and endpoints[end] >= endpoints[start]


def inspect_overhead(directory):
    directory = Path(directory)
    try:
        raw_plan = _snapshot(directory / "overhead-plan.json", 65536)
        plan = CampaignPlan.model_validate_json(raw_plan)
        evidence = OverheadEvidence.model_validate_json(
            _snapshot(directory / "overhead-evidence.json", 512 * 1024)
        )
        if (
            len(plan.trials) != 10
            or any(t.scenario != "healthy" or t.assignment != "engineering" for t in plan.trials)
            or evidence.campaign_id != plan.campaign_id
            or evidence.plan_sha256 != hashlib.sha256(raw_plan).hexdigest()
            or evidence.core_version != plan.core_version
            or evidence.producer_version != plan.producer_version
        ):
            raise ValueError("overhead plan/ownership drift")
        if evidence.runtime is not None and evidence.runtime.node_version != plan.node_version:
            raise ValueError("observed Node version differs from declaration")
        expected = {"overhead-plan.json", "overhead-evidence.json"} | {
            t.trace_file_name for t in evidence.trials if t.trace_file_name
        }
        from ..adapters.pixelated_bundle_io import _open_bundle

        fd = _open_bundle(directory)
        try:
            names = set()
            with os.scandir(fd) as entries:
                for entry in entries:
                    if len(names) >= 7:
                        raise ValueError("overhead inventory exceeds bound")
                    names.add(entry.name)
            if names != expected:
                raise ValueError("overhead artifact inventory drift")
        finally:
            os.close(fd)
        traces_ok = True
        summaries = []
        for trial in evidence.trials:
            if trial.trace_file_name is None:
                continue
            data = _snapshot(directory / trial.trace_file_name, 32 * 1024 * 1024)
            if (
                len(data) != trial.trace_bytes
                or hashlib.sha256(data).hexdigest() != trial.trace_sha256
            ):
                raise ValueError("enabled trace checksum drift")
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary).resolve() / "trace.gz"
                write_trace_output(path, data)
                trace = ingest_trace_bundle(path)
            if (
                trace.producer != "pixelated_engine"
                or trace.producer_version != evidence.producer_version
                or trace.provenance != evidence.provenance
                or len(trace.streams) != 1
            ):
                raise ValueError("nominal trace ownership drift")
            stream = trace.streams[0]
            if (
                stream.sampling.every_nth_frame != 1
                or stream.limits.max_frames != 2000
                or stream.limits.max_events != 10000
            ):
                raise ValueError("nominal trace policy drift")
            events = {}
            for event in stream.events:
                events.setdefault(event.frame_id, {})[event.boundary] = event.timestamp_ns
            queue = encode = joint = 0
            for frame in stream.frames:
                if frame.correlation != "exact":
                    continue
                seen = events.get(frame.frame_id, {})

                q = _usable_pair(seen, "pre_encode_queue_enter", "pre_encode_queue_exit")
                e = _usable_pair(seen, "encode_input", "encode_output")
                queue += q
                encode += e
                joint += q and e
            drops = sum(
                value for key, value in stream.loss.model_dump().items() if key.endswith("dropped")
            )
            passed = (
                queue >= 500
                and encode >= 500
                and joint * 100
                >= 95 * max(len(stream.frames), trial.frames_end - trial.frames_start)
                and drops == 0
            )
            traces_ok &= passed
            summaries.append(
                dict(
                    pair=trial.pair,
                    queue_pairs=queue,
                    encode_pairs=encode,
                    joint_pairs=joint,
                    frame_count=len(stream.frames),
                    drops=drops,
                    nominal_capture_passed=passed,
                    export_duration_ns=trial.export_duration_ns,
                )
            )
        pairs = []
        cpu, fps = [], []
        baseline_ok = True
        for pair in range(1, 6):
            rows = {t.mode: t for t in evidence.trials if t.pair == pair}
            if set(rows) != {"disabled", "enabled"}:
                continue
            disabled, enabled = rows["disabled"], rows["enabled"]
            baseline = measure_fps(disabled)
            baseline_ok &= baseline >= 27
            increase = measure_cpu(enabled) - measure_cpu(disabled)
            change = (measure_fps(enabled) - baseline) / baseline if baseline else None
            cpu.append(increase)
            if change is not None:
                fps.append(change)
            pairs.append(
                dict(
                    pair=pair,
                    disabled_cpu_percent=float(measure_cpu(disabled)),
                    enabled_cpu_percent=float(measure_cpu(enabled)),
                    disabled_fps=float(baseline),
                    enabled_fps=float(measure_fps(enabled)),
                    cpu_increase_percentage_points=float(increase),
                    fps_change_fraction=float(change) if change is not None else None,
                )
            )
        cpu_median = sorted(cpu)[2] if len(cpu) == 5 else None
        fps_median = sorted(fps)[2] if len(fps) == 5 else None
        diagnostic = None
        if evidence.diagnostic is not None:
            item = evidence.diagnostic
            samples = item.probe_durations_ns
            diagnostic = dict(
                observed_probes=item.observed_probes,
                retained_samples=len(samples),
                min_ns=min(samples) if samples else None,
                mean_ns=sum(samples) / len(samples) if samples else None,
                max_ns=max(samples) if samples else None,
                cpu_increase_percentage_points=float(
                    measure_cpu(item.measured) - measure_cpu(item.baseline)
                ),
                fps_change_fraction=float(
                    (measure_fps(item.measured) - measure_fps(item.baseline))
                    / measure_fps(item.baseline)
                )
                if measure_fps(item.baseline)
                else None,
            )
        passed = (
            evidence.state == "completed"
            and len(pairs) == 5
            and baseline_ok
            and traces_ok
            and cpu_median <= 5
            and fps_median >= Fraction(-5, 100)
        )
        report = dict(
            schema_version="n4-overhead-report-v1",
            state=evidence.state,
            reason=evidence.reason,
            provenance=evidence.provenance,
            pairs=pairs,
            median_cpu_increase_percentage_points=float(cpu_median)
            if cpu_median is not None
            else None,
            median_fps_change_fraction=float(fps_median) if fps_median is not None else None,
            baseline_passed=baseline_ok and len(pairs) == 5,
            nominal_traces=summaries,
            diagnostic=diagnostic,
            measured_thresholds_passed=passed,
            real_overhead_acceptance=passed and evidence.provenance == "producer_capture",
            remaining_n4_cases="interruption_tiny_capacity_reenable_two_peer_browser_require_separate_evidence",
            phase_1_acceptance="pending",
        )
        return OverheadReport.model_validate(report).model_dump(mode="json")
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError("invalid_overhead_evidence") from None


def register_overhead_command(subparsers):
    parser = subparsers.add_parser(
        "inspect-overhead", help="verify every frozen pair, trace and diagnostic"
    )
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)

    def run(args):
        try:
            report = inspect_overhead(args.directory)
            write_trace_output(
                args.output, (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
            )
        except (OSError, ValueError):
            raise ValueError("inspect-overhead: invalid_input_or_output") from None

    parser.set_defaults(handler=run)
