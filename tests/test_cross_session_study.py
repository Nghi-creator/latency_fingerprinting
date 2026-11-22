"""On-disk protocol and query-order checks with synthetic calibration."""

import importlib.util
import json
from pathlib import Path

import pytest

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.candidates.cross_session_candidate import (
    cross_session_candidate_spec,
)
from tests.evaluation.candidates.test_cross_session_candidate import setup  # noqa: F401
from tests.evaluation.projections.test_event_span_projection import event_source


def test_operator_scores_next_slot_and_rejects_reused_ledger_order(setup, tmp_path):  # noqa: F811
    file = Path(__file__).resolve().parents[1] / "experiments/cross_session_study.py"
    spec = importlib.util.spec_from_file_location("cross_session_operator", file)
    operator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operator)
    frozen, record = setup
    fit_file = tmp_path / "fit.json"
    fit_file.write_text(frozen)
    conditions = ("no_injected_fault", "owned_identity_delay", "owned_cpu_pressure")
    sessions = []
    for i in range(3):
        sessions.append(
            dict(
                session_id="later-session" if i == 0 else f"session-{i}",
                blocks=[
                    dict(
                        block_id=f"block-{i}-{j}",
                        condition_order=list(conditions),
                        acquisition_ids={c: f"case-{i}-{j}-{k}" for k, c in enumerate(conditions)},
                    )
                    for j in range(2)
                ],
            )
        )
    protocol = dict(
        state="prepared_session_records_pending",
        implementation=dict(
            method_spec=cross_session_candidate_spec(),
            processor_sha256=operator.sha(file.read_bytes()),
            dependency_sha256={str(file): operator.sha(file.read_bytes())},
        ),
        frozen_calibration=dict(file=str(fit_file), sha256=operator.sha(frozen.encode())),
        reserved_sessions=sessions,
        execution=dict(acquisition_cap=18, retries=False),
        excluded_new_case_ids=["old-case"],
        source_manifest_hash=record["observed_context"]["source_manifest_hash"],
        transfer_host_id=record["host_id"],
        calibration_session_ended_at_utc="2026-11-16T16:00:00Z",
    )
    protocol["content_hash"] = payload_hash(protocol)
    protocol_file = tmp_path / "protocol.json"
    protocol_file.write_text(json.dumps(protocol))
    checked, slots = operator.inspect_protocol(
        protocol_file, operator.sha(protocol_file.read_bytes())
    )
    case = tmp_path / "case"
    case.mkdir()
    value = event_source("operator-query", 1)
    (case / "acquisition.json").write_text(value["acquisition_json"])
    (case / "resource-observation.json").write_text(json.dumps(value["resource_artifact"]))
    session_file = tmp_path / "session.json"
    session_file.write_text(json.dumps(record))
    kwargs = dict(
        session_file=session_file, session_hash=payload_hash(record), case=case, history=[]
    )
    prediction = operator.score_next(checked, slots, query_id=slots[0]["query_id"], **kwargs)
    assert prediction["predicted_condition"] == "owned_identity_delay"
    with pytest.raises(ValueError, match="next declared query"):
        operator.score_next(checked, slots, query_id=slots[1]["query_id"], **kwargs)
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps(prediction))
    next_result = operator.score_next(
        checked, slots, query_id=slots[1]["query_id"], **(kwargs | {"history": [prior]})
    )
    assert next_result["state"] == "abstain"
    assert "prior_query_source_or_clock_overlap" in next_result["reason_codes"]
    prior.write_text(json.dumps(prediction | {"predicted_condition": "owned_cpu_pressure"}))
    with pytest.raises(ValueError, match="prior prediction content differs"):
        operator.score_next(
            checked, slots, query_id=slots[1]["query_id"], **(kwargs | {"history": [prior]})
        )
