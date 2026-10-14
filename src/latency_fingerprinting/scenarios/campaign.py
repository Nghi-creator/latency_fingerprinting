"""Detached campaign validation: frozen assignments, exact acquisitions and linked bundles."""

import hashlib
import json
import tempfile
from pathlib import Path

from ..adapters.pixelated_bundle_io import _open_bundle
from ..observability.output import write_trace_output
from .campaign_models import CampaignIndex, CampaignPlan, CampaignReport
from .inspect import inspect_experiment_bundle


def _snapshot(path, bound):
    import os
    import stat

    fd = _open_bundle(path)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("regular campaign artifact required")
        with os.fdopen(fd, "rb", closefd=False) as source:
            data = source.read(bound + 1)
        if len(data) > bound:
            raise ValueError("campaign artifact exceeds bound")
        return data
    finally:
        os.close(fd)


def inspect_campaign(directory):
    directory = Path(directory)
    try:
        plan_bytes = _snapshot(directory / "campaign-plan.json", 65536)
        plan = CampaignPlan.model_validate_json(plan_bytes)
        index = CampaignIndex.model_validate_json(
            _snapshot(directory / "campaign-index.json", 65536)
        )
        if (
            index.campaign_id != plan.campaign_id
            or index.plan_sha256 != hashlib.sha256(plan_bytes).hexdigest()
            or len(index.trials) > len(plan.trials)
        ):
            raise ValueError("campaign ownership drift")
        expected = {"campaign-plan.json", "campaign-index.json"} | {
            t.file_name for t in index.trials if t.file_name
        }
        # Fail boundedly before parsing unreferenced files or following input symlinks.
        import os

        fd = _open_bundle(directory)
        try:
            names = set()
            with os.scandir(fd) as entries:
                for entry in entries:
                    if len(names) >= 26:
                        raise ValueError("campaign inventory exceeds bound")
                    names.add(entry.name)
            if names != expected:
                raise ValueError("campaign inventory drift")
        finally:
            os.close(fd)
        previous_end, total, results = 0, 0, []
        for requested, ref in zip(plan.trials, index.trials, strict=False):
            if (requested.run_id, requested.source_id) != (ref.run_id, ref.source_id):
                raise ValueError("assignment/acquisition drift")
            if ref.status == "unavailable":
                results.append(
                    dict(
                        run_id=ref.run_id,
                        state="unavailable",
                        reason=ref.reason,
                        assignment=requested.assignment,
                        scenario=requested.scenario,
                    )
                )
                continue
            if ref.acquisition_started_ns < previous_end:
                raise ValueError("source acquisitions overlap")
            previous_end = ref.acquisition_ended_ns
            data = _snapshot(directory / ref.file_name, 64 * 1024 * 1024)
            total += len(data)
            if (
                total > 256 * 1024 * 1024
                or len(data) != ref.bytes
                or hashlib.sha256(data).hexdigest() != ref.sha256
            ):
                raise ValueError("campaign bundle length/hash drift")
            # Stage one pinned opaque snapshot; never extract archive members into paths.
            with tempfile.TemporaryDirectory() as temporary:
                snapshot = Path(temporary).resolve() / "bundle.gz"
                fd = os.open(snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as source:
                    source.write(data)
                inspected = inspect_experiment_bundle(snapshot)
            manifest, result = inspected.manifest, inspected.result
            checks = dict(
                run_id=requested.run_id,
                scenario=requested.scenario,
                assignment=requested.assignment,
                repeat_index=requested.repeat_index,
                seed=plan.seed,
                core_version=plan.core_version,
                producer_version=plan.producer_version,
                node_id=plan.node_id,
                workload_id=plan.workload_id,
            )
            if (
                any(getattr(manifest, k) != v for k, v in checks.items())
                or manifest.provenance != "producer_capture"
                or manifest.runtime.node_version != plan.node_version
            ):
                raise ValueError("trial declaration differs from frozen campaign")
            if (
                requested.scenario == "host_contention"
                and manifest.actions[0].workers != plan.host_workers
            ):
                raise ValueError("worker request drift")
            results.append(
                dict(
                    run_id=ref.run_id,
                    scenario=requested.scenario,
                    assignment=requested.assignment,
                    state=result.effect.state,
                    reason=result.effect.reason,
                    effect=result.effect.model_dump(mode="json"),
                )
            )
        if index.state == "finished" and (
            len(index.trials) != len(plan.trials)
            or any(t.status != "exported" for t in index.trials)
        ):
            raise ValueError("finished campaign lost trials")
        classes = {}
        for scenario in ("healthy", "host_contention", "render_capture_slowdown"):
            classes[scenario] = all(
                sum(
                    r["scenario"] == scenario
                    and r["assignment"] == assignment
                    and r["state"] == "verified"
                    for r in results
                )
                >= 2
                for assignment in ("reference", "held_out_query")
            )
        report = dict(
            schema_version="n5-campaign-report-v1",
            campaign_id=plan.campaign_id,
            state=index.state,
            planned_trials=len(plan.trials),
            retained_trials=len(index.trials),
            trials=results,
            repeated_held_out_effects=classes,
            repeated_effect_criteria_passed=index.state == "finished"
            and all(classes.values())
            and all(r["state"] == "verified" for r in results),
            source_independence="declared_disjoint_acquisitions_requires_external_verification",
            inherited_n4_acceptance="pending",
            phase_1_acceptance="pending",
        )
        return CampaignReport.model_validate(report).model_dump(mode="json")
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("invalid_campaign") from None


def register_campaign_command(subparsers):
    parser = subparsers.add_parser(
        "inspect-campaign", help="verify frozen assignments and every retained trial"
    )
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)

    def run(args):
        try:
            report = inspect_campaign(args.directory)
            write_trace_output(
                args.output, (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
            )
        except (OSError, ValueError):
            raise ValueError("inspect-campaign: invalid_input_or_output") from None

    parser.set_defaults(handler=run)
