"""Hand-authored expectations from the frozen Step 2 example tables."""

PHASES = ("warmup", "healthy", "degraded", "probe", "recovery", "cooldown")
SECOND = 1_000_000_000


def manifest(scenario="host_contention"):
    return {
        "schema_version": "experiment-manifest-v1",
        "method_release": "n5-single-cause-v1",
        "experiment_id": "experiment-1",
        "run_id": "run-1",
        "node_id": "node-1",
        "workload_id": "workload-1",
        "clock_id": "clock-1",
        "provenance": "synthetic",
        "scenario": scenario,
        "seed": 7,
        "repeat_index": 1,
        "assignment": "engineering",
        "core_version": "a" * 40,
        "producer_version": "b" * 40,
        "runtime": {
            "kind": "synthetic",
            "python_version": "3.14.4",
            "node_version": "26.4.0",
            "gst_version": "1.28.2",
            "cpu_allocation": 2,
            "width": 1280,
            "height": 720,
            "fps": 30,
            "codec": "vp8",
            "clock_source": "python_monotonic_ns",
            "clock_resolution_ns": 1,
        },
        "adapter": {
            "adapter_id": "bounded_cpu_pressure" if scenario == "host_contention" else "none",
            "state": "available",
            "reason": None,
        },
        "phases": [
            {"phase": phase, "duration_ns": seconds * SECOND}
            for phase, seconds in zip(PHASES, (10, 30, 30, 30, 30, 10), strict=True)
        ],
        "actions": [
            {
                "action_id": "action-1",
                "kind": "cpu_pressure",
                "start_phase": "degraded",
                "stop_phase": "recovery",
                "workers": 1,
                "max_duration_ns": 70 * SECOND,
            }
        ]
        if scenario == "host_contention"
        else [],
        "trace_policy": {
            "scope": "per_phase",
            "every_nth_frame": 1,
            "max_frames": 2000,
            "max_events": 10000,
        },
    }


def evidence(phase="degraded"):
    start, end, frames, rate, workers, cpu = {
        "warmup": (0, 10, 0, 30, 0, 0),
        "healthy": (10, 40, 300, 30, 0, 0),
        "degraded": (40, 70, 1200, 24, 1, 600_000_000),
        "probe": (70, 100, 1920, 24, 1, 600_000_000),
        "recovery": (101, 131, 2670, 30, 0, 0),
        "cooldown": (131, 141, 3570, 30, 0, 0),
    }[phase]
    return {
        "schema_version": "experiment-phase-evidence-v1",
        "method_release": "n5-single-cause-v1",
        "manifest_sha256": "c" * 64,
        "run_id": "run-1",
        "phase": phase,
        "clock_id": "clock-1",
        "start_ns": start * SECOND,
        "end_ns": end * SECOND,
        "state": "complete",
        "reason": None,
        "intervals": [
            {
                "start_ns": (start + i) * SECOND,
                "end_ns": (start + i + 1) * SECOND,
                "frames_start": frames + i * rate,
                "frames_end": frames + (i + 1) * rate,
                "active_workers": workers,
                "worker_cpu_ns": cpu,
            }
            for i in range(end - start)
        ],
    }


def result():
    artifacts = []
    for phase, role in [(p, "phase_evidence") for p in PHASES] + [
        (p, "stage_trace") for p in PHASES[1:5]
    ]:
        number = len(artifacts) + 1
        artifacts.append(
            {
                "artifact_id": f"artifact-{number}",
                "file_name": f"artifact-{number}.json",
                "phase": phase,
                "role": role,
                "schema_version": "experiment-phase-evidence-v1"
                if role == "phase_evidence"
                else "stage-trace-record-v1",
                "bytes": 1,
                "sha256": "d" * 64,
            }
        )
    return {
        "schema_version": "experiment-result-v1",
        "method_release": "n5-single-cause-v1",
        "manifest_sha256": "c" * 64,
        "run_id": "run-1",
        "status": "completed",
        "reason": None,
        "phases": [
            {"phase": p, "start_ns": a * SECOND, "end_ns": b * SECOND, "state": "complete"}
            for p, (a, b) in zip(
                PHASES,
                ((0, 10), (10, 40), (40, 70), (70, 100), (101, 131), (131, 141)),
                strict=True,
            )
        ],
        "actions": [
            {
                "action_id": "action-1",
                "state": "stopped",
                "started_ns": 40 * SECOND,
                "stopped_ns": 100 * SECOND,
                "reason": None,
            }
        ],
        "artifacts": artifacts,
        "effect": {
            "state": "verified",
            "reason": None,
            "healthy_fps": 30.0,
            "degraded_fps": 24.0,
            "recovery_fps": 30.0,
            "pressure_cpu_percent": 60.0,
        },
        "cleanup": {
            "state": "restored",
            "reason": None,
            "started_ns": 100 * SECOND,
            "ended_ns": 101 * SECOND,
            "owned_workers_remaining": 0,
        },
    }


def unsupported():
    value = result()
    value.update(
        status="unsupported", reason="adapter_not_implemented", phases=[], actions=[], artifacts=[]
    )
    value["effect"] = dict.fromkeys(
        ("healthy_fps", "degraded_fps", "recovery_fps", "pressure_cpu_percent")
    )
    value["effect"].update(state="unavailable", reason="adapter_unavailable")
    value["cleanup"].update(state="not_required", started_ns=None, ended_ns=None)
    return value


def aborted():
    value = result()
    value.update(status="aborted", reason="cancelled")
    value["phases"] = value["phases"][:3]
    value["phases"][-1].update(state="partial", end_ns=65 * SECOND)
    value["actions"][0]["stopped_ns"] = 65 * SECOND
    value["artifacts"] = value["artifacts"][:3]
    value["cleanup"].update(started_ns=65 * SECOND, ended_ns=66 * SECOND)
    value["effect"].update(state="unavailable", reason="incomplete_run")
    return value
