"""Verified N2/N3 bindings, compatibility projections and controlled label support."""

from ..analytical.policy_release import payload_hash
from ..models.v2_common import json_equal, thaw_json


def windows(record, kind):
    if kind == "response":
        observation = record.observation
        return observation.degraded_window, observation.relief_window
    return (record,)


def verify_bindings(entry, record, sources):
    for binding, window in zip(
        entry.source_bindings, windows(record, entry.input_kind), strict=True
    ):
        source = sources[binding.source_id]
        artifact = window.source_artifact
        if (
            binding.window_id != window.window_id
            or ("baseline" if binding.window_role == "healthy" else binding.window_role)
            != window.phase.value
            or source.run_id != window.run_id
            or source.source_type != artifact.source_type
            or source.source_content_hash != artifact.content_hash
            or source.bundle_schema_version != artifact.bundle_schema_version
        ):
            raise ValueError("calibration source/window binding mismatch")


def partition_id(record, kind):
    window = windows(record, kind)[0]
    context = window.context.model_dump(mode="json")
    for field in ("context_id", "node_id", "network_scenario"):
        del context[field]
    probe, policy_hash = None, None
    if kind == "response":
        intervention = record.observation.intervention.model_dump(mode="json")
        probe = {
            key: intervention[key]
            for key in (
                "probe_type",
                "probe_version",
                "application_method",
                "intensity",
                "requested_settings",
                "observed_settings",
            )
        }
        policy_hash = record.policy.content_hash
    payload = dict(
        input_kind=kind,
        registry=window.registry.model_dump(mode="json"),
        policy_hash=policy_hash,
        provenance=window.provenance.value,
        capture_method=window.capture_method.model_dump(mode="json"),
        clock=dict(basis=window.clock.basis.value, provenance=window.clock.provenance),
        context=context,
        probe=probe,
        effective_settings={
            w.phase.value: thaw_json(w.effective_settings) for w in windows(record, kind)
        },
    )
    return "partition-" + payload_hash(payload)[7:]


def semantic_identity(record, kind):
    return (
        kind,
        record.response_id
        if kind == "response"
        else payload_hash(record.model_dump(mode="json", by_alias=True)),
    )


def label_reasons(entry, record, experiment, reviews):
    review = reviews.get(entry.label_review_id)
    confirmed = review is not None and review.outcome == "confirmed"
    reasons = []
    if entry.label_basis in ("unknown", "declared_only") or not confirmed:
        reasons.append("label_unverified")
    if entry.label_basis != "controlled_effect":
        return reasons
    manifest, result = experiment.manifest, experiment.result
    mapping = {
        ("n5-single-cause-v1", "healthy"): ("healthy", "healthy"),
        ("n5-single-cause-v1", "host_contention"): ("host_contention", "degraded"),
        ("n5-capture-pacing-v1", "render_capture_slowdown"): (
            "render_capture_slowdown",
            "degraded",
        ),
    }
    if mapping.get((manifest.method_release, manifest.scenario)) != (
        entry.label,
        entry.experiment_phase,
    ):
        raise ValueError("calibration scenario label/phase mismatch")
    window = windows(record, entry.input_kind)[0]
    if (
        window.context.workload_id != manifest.workload_id
        or window.context.encoder_family != "vp8"
        or (window.provenance.value == "synthetic") != (manifest.provenance == "synthetic")
    ):
        raise ValueError("calibration experiment ownership mismatch")
    producer = window.capture_method.producer_version
    if producer is not None and producer != manifest.producer_version:
        raise ValueError("calibration producer revision mismatch")
    declared = window.context.versions.get("pixelatedSourceRevision")
    if declared is not None and declared != manifest.producer_version:
        raise ValueError("calibration context revision mismatch")
    if "targetFps" in window.effective_settings and not json_equal(
        window.effective_settings["targetFps"], manifest.runtime.fps
    ):
        raise ValueError("calibration effective FPS mismatch")
    if (
        result.status != "completed"
        or experiment.effect.state != "verified"
        or result.cleanup.state not in ("restored", "not_required")
        or manifest.adapter.state != "available"
    ):
        reasons.append("effect_unverified")
    phase = next((p for p in result.phases if p.phase == entry.experiment_phase), None)
    if not confirmed or producer is None or phase is None or phase.state != "complete":
        reasons.append("binding_unverified")
    return reasons
