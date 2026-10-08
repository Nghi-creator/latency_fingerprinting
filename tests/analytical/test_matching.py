"""Independent scoring, exact boundaries and conservative decision priorities."""

import hashlib
import math

import pytest
from jsonschema import Draft202012Validator

from latency_fingerprinting.analytical.fingerprints import create_fingerprint_v2
from latency_fingerprinting.analytical.matching import verify_match_repository_v2
from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.analytical.repository import FingerprintRepositoryV2
from latency_fingerprinting.cli import main
from latency_fingerprinting.models import MatchResultV2
from latency_fingerprinting.pipeline import canonical_json
from tests.models.v2_cases import window_payload

from .cases import canonical, policy_payload
from .matching_cases import fingerprint, jitter_response, match, response


def test_independent_complete_score_evidence_identity_schema_and_cli(tmp_path, capsys):
    query, reference = response(), fingerprint(normalized=-0.25)
    result = match(query, [reference])
    assert result.decision == "matched" and result.accepted_label == "declared"
    assert result.match_strength == 0.8 and result.score_margin is None
    comparison = result.comparisons[reference.fingerprint_id]
    assert comparison.shared_features == tuple(sorted(policy_payload()["features"]))
    assert comparison.shared_weight == 22 and comparison.feature_coverage == 1
    assert comparison.distance == 0.25 and comparison.conflict_contribution == 0
    assert comparison.excluded_features == {}
    for evidence in comparison.evidence.values():
        assert (
            evidence.query_value,
            evidence.reference_value,
            evidence.residual,
            evidence.weight,
            evidence.weighted_squared_residual,
            evidence.classification,
        ) == (0, -0.25, 0.25, 1, 0.0625, "supporting")
    ref_hash = (
        "sha256:"
        + hashlib.sha256(canonical(reference.model_dump(mode="json", by_alias=True))).hexdigest()
    )
    refs = [{"fingerprintId": reference.fingerprint_id, "contentHash": ref_hash}]
    expected_id = (
        "match-v2-"
        + hashlib.sha256(
            canonical(
                {
                    "queryResponseId": query.response_id,
                    "policyHash": query.policy.content_hash,
                    "repositoryReferences": refs,
                }
            )
        ).hexdigest()
    )
    assert result.match_id == expected_id
    assert result.repository_references[0].content_hash == ref_hash
    payload = result.model_dump(mode="json", by_alias=True)
    Draft202012Validator(MatchResultV2.model_json_schema()).validate(payload)
    assert MatchResultV2.model_validate_json(canonical_json(result)) == result
    assert MatchResultV2.model_validate(result.model_dump()) == result
    assert (
        result.model_dump(by_alias=False)["comparisons"][reference.fingerprint_id]["distance"]
        == 0.25
    )
    verify_match_repository_v2(result, FingerprintRepositoryV2((reference,)))
    path = tmp_path / "match.json"
    path.write_text(canonical_json(result))
    assert main(["validate", str(path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == canonical_json(result) and captured.err == ""


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("invalid", "invalid_response"),
        ("empty", "no_fingerprints"),
        ("incompatible", "no_compatible_fingerprints"),
        ("insufficient", "insufficient_features"),
        ("weak", "weak_match"),
        ("ambiguous", "ambiguous_margin"),
        ("conflicting", "conflicting_evidence"),
    ],
)
def test_every_unknown_priority_path(kind, reason):
    query, records = response(), []
    if kind == "invalid":
        query, records = response(confounded=True), [fingerprint()]
    elif kind == "incompatible":
        records = [fingerprint(status="unreviewed")]
    elif kind == "insufficient":
        query = response(excluded=sorted(policy_payload()["features"])[16:])
        records = [fingerprint()]
    elif kind == "weak":
        records = [fingerprint(normalized=-0.3)]
    elif kind == "ambiguous":
        records = [fingerprint(normalized=-0.1), fingerprint(label="same_label", normalized=-0.12)]
    elif kind == "conflicting":

        def change(pair):
            item = window_payload(phase="relief", values=(0, 24, 48))["measurements"][
                "transport.jitter_ms"
            ]
            pair["relief_window"]["measurements"]["transport.jitter_ms"] = item

        records = [fingerprint(changes=change)]
    result = match(query, records)
    assert result.decision == "unknown" and result.unknown_reason == reason
    assert result.accepted_label is None
    if kind == "conflicting":
        comparison = next(iter(result.comparisons.values()))
        assert comparison.conflict_contribution == 1
        assert comparison.distance == pytest.approx(0.6 / math.sqrt(22))
        assert comparison.evidence["transport.jitter_ms"].classification == "conflicting"
    if kind == "invalid":
        assert tuple(result.candidate_rejections.values()) == (("query_invalid",),)
    assert match(response(confounded=True)).unknown_reason == "invalid_response"


@pytest.mark.parametrize("count,scored", [(3, False), (16, False), (17, True)])
def test_full_inventory_coverage_and_ordered_shared_rejections(count, scored):
    query = response(excluded=sorted(policy_payload()["features"])[count:])
    record = fingerprint()
    result = match(query, [record])
    if scored:
        comparison = result.comparisons[record.fingerprint_id]
        assert comparison.feature_coverage == 17 / 22
        assert set(comparison.excluded_features.values()) == {("query_excluded",)}
    else:
        assert result.candidate_rejections[record.fingerprint_id] == (
            ("shared_feature_count", "feature_coverage") if count == 3 else ("feature_coverage",)
        )


def test_reference_and_query_exclusions_are_retained_in_order():
    names = sorted(policy_payload()["features"])
    query = response(excluded=names[:2])
    record = fingerprint(excluded=names[1:3])
    result = match(query, [record])
    comparison = result.comparisons[record.fingerprint_id]
    assert comparison.excluded_features[names[0]] == ("query_excluded",)
    assert comparison.excluded_features[names[1]] == ("query_excluded", "reference_excluded")
    assert comparison.excluded_features[names[2]] == ("reference_excluded",)
    assert len(comparison.evidence) == 19


def test_ties_same_label_and_truncation_preserve_all_comparisons():
    records = [fingerprint(label=f"reference_{i}", normalized=-0.1) for i in range(7)]
    ids = sorted(record.fingerprint_id for record in records)
    a, b = match(records=records), match(records=reversed(records))
    assert canonical_json(a) == canonical_json(b)
    assert len(a.comparisons) == 7 and len(a.ranked_candidates) == 5
    assert [r.fingerprint_id for r in a.ranked_candidates] == ids[:5]
    assert a.score_margin == 0 and a.unknown_reason == "ambiguous_margin"
    same_label = [
        fingerprint(label="same", normalized=-0.1),
        fingerprint(label="same", normalized=-0.12),
    ]
    assert match(records=same_label).unknown_reason == "ambiguous_margin"


def test_weak_priority_over_margin_and_conflict():
    result = match(
        records=[fingerprint(normalized=0.7), fingerprint(label="other", normalized=0.71)]
    )
    assert result.unknown_reason == "weak_match"
    assert next(iter(result.comparisons.values())).conflict_contribution == 1


def test_residual_threshold_equality_is_supporting():
    result = match(records=[fingerprint(normalized=-0.5)])
    assert all(
        e.classification == "supporting"
        for c in result.comparisons.values()
        for e in c.evidence.values()
    )
    assert result.unknown_reason == "weak_match"


@pytest.mark.parametrize("target", ["residual", "sum"])
def test_unrepresentable_scoring_is_error_not_unknown(target):
    if target == "residual":
        query, record = response(normalized=1e160), fingerprint()
    else:
        query, record = response(normalized=4e153), fingerprint()
    with pytest.raises(ValueError, match="finite numeric"):
        match(query, [record])


@pytest.mark.parametrize("delta", [1e-200, 2e-162])
def test_squared_residual_or_mean_square_underflow_cannot_fabricate_zero_distance(delta):
    query = jitter_response(delta)
    record = create_fingerprint_v2(jitter_response(0), bottleneck_label="declared")
    assert query.features["transport.jitter_ms"].normalized_value == delta
    with pytest.raises(ValueError, match="finite numeric"):
        match(query, [record])


def test_small_representable_residual_retains_nonzero_distance_and_evidence():
    query = jitter_response(1e-150)
    record = create_fingerprint_v2(jitter_response(0), bottleneck_label="declared")
    result = match(query, [record])
    comparison = result.comparisons[record.fingerprint_id]
    assert comparison.distance == pytest.approx(1e-150 / math.sqrt(22), rel=1e-12, abs=0)
    assert comparison.evidence["transport.jitter_ms"].weighted_squared_residual == 1e-300
    assert MatchResultV2.model_validate_json(canonical_json(result)) == result


@pytest.mark.parametrize("delta", [1e-200, 2e-162])
def test_stored_result_validation_rejects_underflow_even_with_rehashed_identity(delta):
    record = create_fingerprint_v2(jitter_response(0), bottleneck_label="declared")
    payload = match(jitter_response(0), [record]).model_dump(mode="json", by_alias=True)
    query = jitter_response(delta)
    payload["queryResponse"] = query.model_dump(mode="json", by_alias=True)
    payload["matchId"] = (
        "match-v2-"
        + payload_hash(
            {
                "queryResponseId": query.response_id,
                "policyHash": query.policy.content_hash,
                "repositoryReferences": payload["repositoryReferences"],
            }
        )[7:]
    )
    evidence = payload["comparisons"][record.fingerprint_id]["evidence"]["transport.jitter_ms"]
    evidence.update(queryValue=delta, residual=delta, weightedSquaredResidual=delta * delta)
    with pytest.raises(ValueError, match="finite numeric"):
        MatchResultV2.model_validate(payload)


def test_floating_margin_boundaries_use_no_epsilon_fudge():
    records = [fingerprint(), fingerprint(label="second", normalized=1 / 0.901 - 1)]
    result = match(records=records)
    assert result.score_margin < 0.1 and result.unknown_reason == "ambiguous_margin"
    records[1] = fingerprint(label="second", normalized=1 / 0.899 - 1)
    result = match(records=records)
    assert result.score_margin >= 0.1 and result.decision == "matched"


def test_conflict_cap_equality_fails_and_margin_takes_priority():
    def change(pair):
        changes = [
            ("transport.jitter_ms", 0.6),
            ("client.decode_time_mean_ms", 0.3),
            ("client.jitter_buffer_delay_mean_ms", 0.3),
            ("client.available_incoming_bitrate_kbps", 0.3),
            ("encoder.queue_level_buffers", 0.3),
        ]
        for name, delta in changes:
            pair["relief_window"]["measurements"][name] = window_payload(
                phase="relief", values=(0, 60 * (1 + delta), 120 * (1 + delta))
            )["measurements"][name]

    record = fingerprint(changes=change)
    result = match(records=[record])
    comparison = result.comparisons[record.fingerprint_id]
    assert comparison.conflict_contribution == pytest.approx(0.5)
    # Test exact equality at the decision boundary independently of floating score arithmetic.
    from latency_fingerprinting.analytical.decisions import decision_payload

    raw = comparison.model_dump(mode="json", by_alias=True)
    raw["conflictContribution"] = 0.5
    query = response()
    refs = [{"fingerprintId": record.fingerprint_id}]
    assert (
        decision_payload(query, refs, {}, {record.fingerprint_id: raw})["unknownReason"]
        == "conflicting_evidence"
    )
    second = dict(raw, fingerprintId="second")
    assert (
        decision_payload(query, refs, {}, {record.fingerprint_id: raw, "second": second})[
            "unknownReason"
        ]
        == "ambiguous_margin"
    )
