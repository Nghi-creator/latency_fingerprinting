"""Linked N5 validation, separate from standalone shape validation and N3 matching."""

import hashlib
import tarfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from ..models.observation_v2 import ObservationWindowV2
from ..observability.json import decode_trace_json
from ..observability.trace import StageTraceRecord
from .bundle_io import ROOTS, read_members
from .contracts import SECOND
from .effects import recompute_effect
from .evidence import ExperimentPhaseEvidence
from .manifest import ExperimentManifest
from .result import Effect, ExperimentResult


@dataclass(frozen=True)
class InspectedExperiment:
    manifest: ExperimentManifest
    result: ExperimentResult
    effect: Effect
    artifacts: tuple


def _linked(manifest, result, models, calculator=recompute_effect):
    if result.run_id != manifest.run_id:
        raise ValueError("experiment run mismatch")
    unavailable = manifest.adapter.state == "unavailable"
    if unavailable != (result.status == "unsupported") or (
        unavailable and result.reason != manifest.adapter.reason
    ):
        raise ValueError("adapter/execution mismatch")
    if (
        tuple(a.action_id for a in result.actions) != tuple(a.action_id for a in manifest.actions)
        and not unavailable
    ):
        raise ValueError("requested actions lost")
    for action, requested in zip(result.actions, manifest.actions, strict=not unavailable):
        if (
            result.status == "completed"
            and action.started_ns is not None
            and action.stopped_ns is not None
            and action.stopped_ns - action.started_ns > requested.max_duration_ns
        ):
            raise ValueError("action exceeded declared bound")
    for actual, planned in zip(result.phases, manifest.phases, strict=False):
        if actual.state == "complete" and not (
            planned.duration_ns
            <= actual.end_ns - actual.start_ns
            <= planned.duration_ns + 2 * SECOND
        ):
            raise ValueError("actual phase differs from plan tolerance")
    phases = {p.phase: p for p in result.phases}
    evidence = {}
    for reference, model in zip(result.artifacts, models, strict=True):
        actual = phases[reference.phase]
        if reference.role == "phase_evidence":
            if (
                model.run_id != manifest.run_id
                or model.manifest_sha256 != result.manifest_sha256
                or model.clock_id != manifest.clock_id
                or model.phase != reference.phase
                or (model.start_ns, model.end_ns) != (actual.start_ns, actual.end_ns)
                or (model.state == "complete" and actual.state != "complete")
            ):
                raise ValueError("phase evidence ownership mismatch")
            workers = (
                manifest.actions[0].workers
                if manifest.actions and reference.phase in ("degraded", "probe")
                else 0
            )
            for row in model.intervals:
                # Partial fault phases may retain fewer workers after an abort, but
                # never foreign/excess workers or pressure in a healthy phase.
                if row.active_workers > workers or (
                    result.status == "completed" and row.active_workers != workers
                ):
                    raise ValueError("worker evidence contradicts requested action")
            evidence[reference.phase] = model
        elif reference.role == "stage_trace":
            if (
                model.producer != "pixelated_engine"
                or model.provenance != manifest.provenance
                or model.producer_version != manifest.producer_version
            ):
                raise ValueError("stage trace producer/provenance mismatch")
            for stream in model.streams:
                if (
                    stream.sampling.every_nth_frame != manifest.trace_policy.every_nth_frame
                    or stream.limits.max_frames != manifest.trace_policy.max_frames
                    or stream.limits.max_events != manifest.trace_policy.max_events
                ):
                    raise ValueError("trace policy mismatch")
        elif model.provenance.value != (
            "synthetic" if manifest.provenance == "synthetic" else "controlled_real"
        ):
            raise ValueError("observation provenance mismatch")
    # One observed counter generation across phases; no cross-phase reset hidden
    # by individually valid roots. D/P include their continuous transition.
    previous, previous_complete = None, False
    for phase in result.phases:
        item = evidence.get(phase.phase)
        if item is not None and item.intervals:
            first = item.intervals[0].frames_start
            if previous is not None and (
                first < previous
                or (phase.phase == "probe" and previous_complete and first != previous)
            ):
                raise ValueError("cross-phase frame counter changed generation")
            previous = item.intervals[-1].frames_end
            previous_complete = item.state == "complete"
        else:
            previous = None
            previous_complete = False
    effect = calculator(manifest, result, evidence)
    if effect != result.effect:
        raise ValueError("supplied effect differs from raw evidence")
    return effect


def inspect_experiment_bundle(path: Path) -> InspectedExperiment:
    """Read only, no extraction/runtime access; errors never expose supplied data."""
    try:
        files = read_members(path)
        from .pacing import ExperimentManifestV2, ExperimentPhaseEvidenceV2, ExperimentResultV2
        from .pacing_effect import recompute_pacing

        declaration = decode_trace_json(files["experiment-manifest.json"])
        if not isinstance(declaration, dict):
            raise ValueError("experiment manifest must be an object")
        pacing = declaration.get("schema_version") == "experiment-manifest-v2"
        manifest_class = ExperimentManifestV2 if pacing else ExperimentManifest
        result_class = ExperimentResultV2 if pacing else ExperimentResult
        manifest = manifest_class.model_validate(declaration)
        result = result_class.model_validate_json(files["experiment-result.json"])
        if result.manifest_sha256 != hashlib.sha256(files["experiment-manifest.json"]).hexdigest():
            raise ValueError("manifest checksum mismatch")
        if set(files) != ROOTS | {a.file_name for a in result.artifacts}:
            raise ValueError("experiment membership mismatch")
        classes = {
            "phase_evidence": ExperimentPhaseEvidenceV2 if pacing else ExperimentPhaseEvidence,
            "stage_trace": StageTraceRecord,
            "observation_window": ObservationWindowV2,
        }
        models = []
        for artifact in result.artifacts:
            data = files[artifact.file_name]
            if len(data) != artifact.bytes or hashlib.sha256(data).hexdigest() != artifact.sha256:
                raise ValueError("artifact checksum mismatch")
            models.append(classes[artifact.role].model_validate(decode_trace_json(data)))

        def calculator(manifest, result, evidence):
            traces = {
                ref.phase: model
                for ref, model in zip(result.artifacts, models, strict=True)
                if ref.role == "stage_trace"
            }
            return recompute_pacing(manifest, result, evidence, traces)

        effect = _linked(manifest, result, models, calculator if pacing else recompute_effect)
        return InspectedExperiment(manifest, result, effect, tuple(models))
    except (OSError, ValueError, KeyError, EOFError, tarfile.TarError, zlib.error):
        raise ValueError("invalid_experiment_bundle") from None
