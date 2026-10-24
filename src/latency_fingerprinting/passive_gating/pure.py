"""Pure factories over explicit declarations. These functions never inspect files."""

from collections.abc import Mapping

from ..analytical.policy_release import payload_hash
from ..models.observation_v2 import ObservationWindowV2
from .baseline import reconstruct_baseline, stratum_id
from .contracts import ASSURANCE, RELEASE, sequence, tree_budget
from .evidence import Evidence, metadata_reasons, quality_reasons, scope
from .models import BaselineInput, PassiveBaseline, PassiveGateResult, PassiveReplay, ReplayWindow
from .policy import PassiveGatePolicy
from .replay import reconstruct_replay


def seal(payload, name, prefix):
    content = {k: v for k, v in payload.items() if k not in (name, "content_hash")}
    digest = payload_hash(content)
    return dict(payload, **{name: prefix + digest[7:], "content_hash": digest})


def fit_passive_baseline(evidence, windows, policy):
    """Fit only the exact metadata-eligible training-window inventory supplied."""
    try:
        tree_budget(evidence)
        tree_budget(policy)
        if not isinstance(windows, Mapping) or len(windows) > 256:
            raise ValueError
        tree_budget(windows)
        evidence = Evidence.model_validate(evidence)
        policy = PassiveGatePolicy.model_validate(policy)
        inputs, used = [], set()
        for declaration, entry in zip(
            evidence.dataset.entries, evidence.report.entries, strict=True
        ):
            reasons = metadata_reasons(evidence, declaration, entry)
            window = sid = None
            if not reasons:
                window = ObservationWindowV2.model_validate(windows[entry.entry_id])
                used.add(entry.entry_id)
                evidence.bind_window(declaration, entry, window)
                sid = stratum_id(scope(window))
                reasons.extend(quality_reasons(window))
            inputs.append(
                BaselineInput(
                    entry_id=entry.entry_id,
                    group_id=entry.group_id,
                    stratum_id=sid,
                    window=window,
                    selected=not reasons,
                    reason_codes=reasons,
                )
            )
        if set(windows) != used:
            raise ValueError
        strata, counts, state = reconstruct_baseline(evidence, inputs)
        payload = dict(
            schema_version="passive-baseline-v1",
            method_release=RELEASE,
            policy=policy.model_dump(mode="json"),
            evidence=evidence.model_dump(mode="json"),
            inputs=[i.model_dump(mode="json") for i in inputs],
            strata=strata,
            state=state,
            counts=counts,
            assurance=ASSURANCE,
        )
        tree_budget(payload)
        return PassiveBaseline.model_validate(seal(payload, "baseline_id", "passive-baseline-"))
    except (ValueError, TypeError, OverflowError, KeyError):
        raise ValueError("invalid_passive_baseline") from None


def create_passive_replay(baseline, *, mode, stream, start_ms, windows, events):
    """Seal a complete replay declaration; evaluate it separately against the baseline."""
    try:
        baseline = PassiveBaseline.model_validate(baseline)
        sequence(events)
        sequence(windows)
        tree_budget(dict(stream=stream, windows=windows, events=events))
        if not isinstance(stream, Mapping) or set(stream) - {"stream_id"} != {
            "acquisition_namespace",
            "run_id",
            "clock_domain_id",
            "generation_id",
            "stratum_id",
        }:
            raise ValueError
        stream = dict(stream)
        content = {k: v for k, v in stream.items() if k != "stream_id"}
        identifier = (
            "passive-stream-"
            + payload_hash(
                dict(
                    method_release=RELEASE,
                    baseline_id=baseline.baseline_id,
                    dataset_id=baseline.evidence.dataset.dataset_id,
                    stream=content,
                )
            )[7:]
        )
        if stream.get("stream_id", identifier) != identifier:
            raise ValueError
        stream["stream_id"] = identifier
        sealed_events = []
        for event in events:
            if not isinstance(event, Mapping):
                raise ValueError
            body = {k: v for k, v in event.items() if k != "event_id"}
            identifier = (
                "passive-event-" + payload_hash(dict(method_release=RELEASE, event=body))[7:]
            )
            if event.get("event_id", identifier) != identifier:
                raise ValueError
            sealed_events.append(dict(event, event_id=identifier))
        payload = dict(
            schema_version="passive-replay-v1",
            method_release=RELEASE,
            policy_content_hash=baseline.policy.content_hash,
            baseline_id=baseline.baseline_id,
            dataset_id=baseline.evidence.dataset.dataset_id,
            mode=mode,
            stream=stream,
            start_ms=start_ms,
            windows=[ReplayWindow.model_validate(row).model_dump(mode="json") for row in windows],
            events=sealed_events,
            assurance=ASSURANCE,
        )
        tree_budget(payload)
        return PassiveReplay.model_validate(seal(payload, "replay_id", "passive-replay-"))
    except (ValueError, TypeError, OverflowError):
        raise ValueError("invalid_passive_replay") from None


def evaluate_passive_replay(baseline, replay, policy):
    """Reconstruct one immutable offline result; no hidden state or source reads."""
    try:
        baseline = PassiveBaseline.model_validate(baseline)
        replay = PassiveReplay.model_validate(replay)
        policy = PassiveGatePolicy.model_validate(policy)
        if policy != baseline.policy:
            raise ValueError
        rows, final, counts = reconstruct_replay(baseline, replay)
        payload = dict(
            schema_version="passive-gate-result-v1",
            method_release=RELEASE,
            policy=policy.model_dump(mode="json"),
            baseline=baseline.model_dump(mode="json"),
            replay=replay.model_dump(mode="json"),
            rows=rows,
            final_state=final,
            counts=counts,
            assurance=ASSURANCE,
        )
        tree_budget(payload)
        return PassiveGateResult.model_validate(seal(payload, "result_id", "passive-gate-"))
    except (ValueError, TypeError, OverflowError):
        raise ValueError("invalid_passive_replay") from None
