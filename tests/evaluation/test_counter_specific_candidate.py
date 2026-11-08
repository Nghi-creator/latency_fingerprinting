"""Invented stable sources qualify software only, never empirical recognition."""

import hashlib
import json
from copy import deepcopy

import pytest

from latency_fingerprinting.evaluation import counter_specific_candidate as method
from latency_fingerprinting.evaluation.combined_interval_candidate import (
    combined_interval_candidate_spec,
)
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS
from tests.evaluation.test_combined_interval_candidate import CONTEXT, source
from tests.evaluation.test_counter_specific_projection import rows, seal


def point_source(identifier, arm=0, identical=False):
    value = source(identifier, arm, identical)
    raw = json.loads(value["acquisition_json"])
    for row in rows(raw):
        native = row["native_read"]
        row["encoded_counter_read"] = dict(
            method="native-encoded-counter-read-brackets-v1",
            clock_id=native["clock_id"],
            basis=native["basis"],
            read_start_ns=native["read_start_ns"],
            read_end_ns=native["read_end_ns"],
            value=row["encoded_buffers"],
            scope="reported_encoded_counter_only_not_other_snapshot_fields",
            underlying_counter_freshness="not_authenticated_by_read_brackets",
            live_authority=False,
        )
    return seal(value, raw)


def training(identical=False):
    result = {}
    for index in range(6):
        block = {}
        for arm, condition in enumerate(CONDITIONS):
            identifier = f"point-fit-{index}-{arm}"
            value = point_source(identifier, arm, identical)
            block[condition] = {
                "source": value,
                "binding": method.declare_counter_specific_binding(
                    value,
                    condition=condition,
                    context_hash=CONTEXT,
                    inspection_sha256="sha256:" + hashlib.sha256(identifier.encode()).hexdigest(),
                ),
            }
        result[f"block-{index}"] = block
    return result


def score(value, blocks, **changes):
    args = dict(
        session_id="engineering-session",
        query_session_id="engineering-session",
        query_block_id="later-block",
        context_hash=CONTEXT,
    )
    return method.score_counter_specific_candidate(value, blocks, **dict(args, **changes))


def test_zero_within_condition_dispersion_is_accepted_and_all_queries_score():
    blocks = training()
    before = deepcopy(blocks)
    fitted = method.fit_counter_specific_candidate(blocks, session_id="engineering-session")
    assert fitted["state"] == "candidate_calibration_available"
    assert fitted["calibration_query_count"] == 18
    assert all(f["complete_and_correct"] for f in fitted["folds"])
    assert (
        fitted["method_spec"]["arithmetic"]
        == "exact_rational_no_midpoint_epsilon_clipping_or_fitted_scale"
    )
    for arm, condition in enumerate(CONDITIONS):
        values = [f[condition]["source"] for f in blocks.values()]
        # Source identities differ; within-condition numerical responses are identical.
        from latency_fingerprinting.evaluation.counter_specific_projection import (
            project_counter_specific_resource,
        )

        assert all(
            project_counter_specific_resource(v)["features"]
            == project_counter_specific_resource(values[0])["features"]
            for v in values
        )
        result = score(point_source(f"fresh-query-{arm}", arm), blocks)
        assert result["predicted_condition"] == condition
        assert result["state"] == "candidate_condition_prediction"
        assert result["independent_support_groups"] == 0
        assert result["empirical_acceptance"] is False
    assert blocks == before


def test_ambiguous_classes_are_a_valid_unavailable_calibration_and_abstention():
    blocks = training(identical=True)
    fitted = method.fit_counter_specific_candidate(blocks, session_id="engineering-session")
    assert fitted["state"] == "unavailable"
    assert fitted["thresholds"] is None
    assert fitted["calibration_query_count"] == 18
    assert fitted["reason_codes"] == ["calibration_folds_not_all_robustly_correct"]
    result = score(point_source("fresh-uninformative", identical=True), blocks)
    assert result["state"] == "abstain"
    assert "calibration_unavailable" in result["reason_codes"]


def test_legacy_method_identity_is_unchanged_and_new_binding_cannot_be_interchanged():
    assert (
        combined_interval_candidate_spec()["content_hash"]
        == "sha256:158ce21d45deae05b0ad2871f2ccd8578b2a66d0646b87ef83d9b3b264daa327"
    )
    assert (
        method.counter_specific_candidate_spec()["content_hash"]
        != combined_interval_candidate_spec()["content_hash"]
    )
    blocks = training()
    blocks["block-0"][CONDITIONS[0]]["binding"]["release"] = (
        "n11-combined-resource-condition-binding-candidate-v1"
    )
    with pytest.raises(ValueError):
        method.fit_counter_specific_candidate(blocks, session_id="engineering-session")


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"query_session_id": "another-session"}, "different_query_session"),
        ({"query_block_id": "block-0"}, "query_block_overlap"),
        ({"context_hash": "sha256:" + "f" * 64}, "incompatible_query_context"),
    ],
)
def test_query_separation_guards_remain_active(change, reason):
    result = score(point_source("isolated-query"), training(), **change)
    assert result["state"] == "abstain" and reason in result["reason_codes"]


def test_old_sources_and_mixed_raw_cpu_bytes_are_rejected():
    with pytest.raises(ValueError):
        method.declare_counter_specific_binding(
            source("old"),
            condition=CONDITIONS[0],
            context_hash=CONTEXT,
            inspection_sha256="sha256:" + "e" * 64,
        )
    blocks = training()
    blocks["block-0"][CONDITIONS[0]]["source"]["acquisition_json"] += " "
    with pytest.raises(ValueError):
        method.fit_counter_specific_candidate(blocks, session_id="engineering-session")
