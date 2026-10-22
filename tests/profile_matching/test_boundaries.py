"""Full-root unknown stages, raw signed zero, source binding and actual/global budgets."""

import copy

import pytest

from latency_fingerprinting.profile_matching import ProfileEvaluationResult, ProfileMatchResult
from tests.profiles.cases import NAMES, reviewed

from .cases import evaluation, match, query_changed, rebind, root_seal


def unknown_fields(decision, reasons, common=()):
    decision.update(
        common_feature_names=list(common),
        common_coverage=dict(numerator=len(common), denominator=22, value=len(common) / 22),
        ranked_profile_ids=[],
        best_label=None,
        runner_up_label=None,
        best_distance=None,
        runner_up_distance=None,
        margin=None,
        state="unknown",
        chosen_label=None,
        reason_codes=reasons,
    )


@pytest.mark.parametrize(
    "value,reasons",
    [
        (3.875, []),
        (4.0, ["ambiguous_labels"]),
        (4.0625, ["ambiguous_labels"]),
        (-1.0, []),
        (-1.5, ["distance_exceeded"]),
        (7.0, []),
        (float.fromhex("0x1.fffffffffffffp+1023"), ["distance_exceeded", "ambiguous_labels"]),
    ],
)
def test_full_root_decision_boundaries(value, reasons):
    p = query_changed(value)
    actual = ProfileMatchResult.model_validate(p)
    assert actual.model_dump(mode="json") == p
    assert list(actual.decision.reason_codes) == reasons


def test_raw_query_signed_zero_is_preserved_in_maps_and_feature_rows():
    p = query_changed(-0.0)
    actual = ProfileMatchResult.model_validate(p)
    assert actual.decision.query_feature_values[NAMES[0]].hex().startswith("-0x0")
    assert actual.decision.candidates[0].features[NAMES[0]].query_value.hex().startswith("-0x0")
    p["decision"]["candidates"][0]["features"][NAMES[0]]["query_value"] = 0.0
    with pytest.raises(ValueError, match="does not reconstruct"):
        ProfileMatchResult.model_validate(root_seal(p))


@pytest.mark.parametrize(
    "operation,reason", [("mark_stale", "external_review"), ("reject", "operator_rejected")]
)
def test_withdrawal_is_valid_unknown_not_a_reactivated_profile(operation, reason):
    p = match()
    p["evidence"]["snapshot"] = reviewed(p["evidence"]["snapshot"], operation, reason)
    d = p["decision"]
    d["query_feature_values"] = None
    for row in d["candidates"]:
        row.update(
            state="excluded",
            reason_codes=["snapshot_unavailable"],
            features=None,
            weight_sum=None,
            distance=None,
        )
    unknown_fields(d, ["snapshot_unavailable"])
    actual = ProfileMatchResult.model_validate(root_seal(p))
    assert actual.decision.state == "unknown"


def test_query_label_blindness_with_all_source_identities_rebound():
    p = match()
    before = (
        p["decision"]["best_distance"],
        p["decision"]["runner_up_distance"],
        p["decision"]["chosen_label"],
    )
    query_id = p["decision"]["query_entry_id"]
    for e in p["evidence"]["dataset"]["entries"]:
        if e["entry_id"] == query_id:
            e["label"] = "healthy"
    for e in p["evidence"]["report"]["entries"]:
        if e["entry_id"] == query_id:
            e["label"] = "healthy"
    rebind(p)
    actual = ProfileMatchResult.model_validate(p)
    assert (
        actual.decision.best_distance,
        actual.decision.runner_up_distance,
        actual.decision.chosen_label,
    ) == before


@pytest.mark.parametrize("asymmetric", [False, True])
def test_supported_candidates_share_one_mask_in_full_roots(asymmetric):
    p = match()
    snapshot = p["evidence"]["snapshot"]
    d = p["decision"]
    for profile in snapshot["profiles"]:
        missing = (
            range(18, 22)
            if asymmetric and profile["label"] == "healthy"
            else range(5)
            if profile["label"] == "host_contention"
            else ()
        )
        for name in [NAMES[i] for i in missing]:
            for item in snapshot["inputs"]:
                if item["entry_id"] in profile["selected_entry_ids"]:
                    item["feature_values"][name] = 0.0
            f = profile["features"][name]
            for row in f["group_values"]:
                row["median"] = 0.0
            f.update(
                state="excluded",
                reason_codes=["zero_dispersion"],
                weight=0.0,
                center=0.0,
                dispersion=0.0,
            )
        active = 22 - len(missing)
        profile.update(
            active_feature_count=active,
            active_feature_coverage=dict(numerator=active, denominator=22, value=active / 22),
        )
    rebind(p)
    common = list(NAMES[5:18] if asymmetric else NAMES[5:])
    if asymmetric:
        reasons = ["insufficient_common_features", "insufficient_common_coverage"]
        for row in d["candidates"]:
            row.update(
                state="excluded",
                reason_codes=reasons,
                features=None,
                weight_sum=None,
                distance=None,
            )
        unknown_fields(d, reasons, common)
    else:
        for profile, row in zip(snapshot["profiles"], d["candidates"], strict=True):
            for name in NAMES[:5]:
                f = row["features"][name]
                base = profile["features"][name]
                f.update(
                    state="excluded",
                    reason_codes=[
                        "profile_feature_excluded"
                        if profile["label"] == "host_contention"
                        else "not_common_feature"
                    ],
                    center=base["center"],
                    dispersion=base["dispersion"],
                    profile_weight=base["weight"],
                    applied_weight=0.0,
                    absolute_deviation=None,
                    standardized_deviation=None,
                    weighted_contribution=None,
                )
            row["weight_sum"] = 17.0
        d.update(
            common_feature_names=common,
            common_coverage=dict(numerator=17, denominator=22, value=17 / 22),
        )
    actual = ProfileMatchResult.model_validate(root_seal(p))
    assert actual.decision.common_feature_names == tuple(common)


@pytest.mark.parametrize(
    "kind",
    [
        "inputs",
        "profiles",
        "features",
        "candidates",
        "matrix",
        "refit_candidates",
        "refit_groups",
        "refit_references",
        "feature_rows",
        "candidate_rows",
    ],
)
def test_aggregate_budgets_precede_invalid_child_models(kind):
    p = {}
    if kind == "candidates":
        p["decision"] = {"candidates": [None] * 257}
    elif kind == "features":
        p["decision"] = {"candidates": [{"features": dict.fromkeys(range(23))}]}
    elif kind in ("inputs", "profiles"):
        p["refits"] = [{kind: iter(())}]
    elif kind == "matrix":
        p["confusion_matrix"] = dict.fromkeys(range(5))
    elif kind == "refit_candidates":
        p["refits"] = [{"profiles": [{}] * 256}, {"profiles": [{}]}]
    elif kind == "refit_groups":
        p["refits"] = [
            {"profiles": [{"features": {name: {"group_values": [{}] * 256} for name in NAMES}}] * 6}
        ]
    elif kind == "refit_references":
        p["refits"] = [
            {
                "profiles": [
                    {
                        "features": {
                            name: {"group_values": [{"entry_ids": ["x"] * 256}] * 7}
                            for name in NAMES
                        }
                    }
                ]
            }
        ]
    elif kind == "candidate_rows":
        p["decisions"] = [{"candidates": [{}] * 256}] * 17
    else:
        p["decisions"] = [
            {"candidates": [{"features": dict.fromkeys(NAMES)}] * 256},
            {"candidates": [{"features": dict.fromkeys(NAMES)}]},
        ]
    with pytest.raises(ValueError, match="N8 (global|collection|feature|refit|confusion)"):
        ProfileEvaluationResult.model_validate(p)


def test_claimed_skipped_refits_cannot_evade_actual_work_budget(monkeypatch):
    from latency_fingerprinting.profile_matching import evaluation as implementation

    p = evaluation("validation")
    p["evidence"] = match(20)["evidence"]
    p["mode"] = "leave_training_group_out"
    template = p["decisions"][0]
    entries = [e for e in p["evidence"]["report"]["entries"] if e["role"] == "training"]
    p["decisions"] = []
    for entry in entries:
        d = copy.deepcopy(template)
        d["query_entry_id"] = entry["entry_id"]
        p["decisions"].append(d)
    p["refits"] = [
        dict(
            refit_id="profile-refit-" + "0" * 64,
            excluded_group_id=g,
            state="skipped",
            reason_codes=["no_eligible_queries"],
            inputs=None,
            profiles=None,
            counts=None,
        )
        for g in sorted({e["group_id"] for e in entries})
    ]

    def forbidden(*args, **kwargs):
        raise AssertionError("fitting began before budget check")

    monkeypatch.setattr(implementation, "fit_profiles", forbidden)
    with pytest.raises(ValueError, match="actual refit work"):
        ProfileEvaluationResult.model_validate(root_seal(p))


def test_valid_but_incompatible_partition_has_no_compatible_profiles():
    from tests.calibration.cases import seal_report

    p = match()
    report = p["evidence"]["report"]
    query = report["entries"][-2]
    partition = "partition-" + "9" * 64
    query["partition_id"] = partition
    old = report["partitions"][0]
    old.update(
        retained_entries=old["retained_entries"] - 1,
        eligible_entries=old["eligible_entries"] - 1,
        eligible_groups=old["eligible_groups"] - 1,
    )
    report["partitions"].append(
        dict(
            partition_id=partition,
            input_kind="response",
            retained_entries=1,
            eligible_entries=1,
            eligible_groups=1,
        )
    )
    report["partitions"].sort(key=lambda row: row["partition_id"])
    seal_report(report)
    rebind(p)
    for row in p["decision"]["candidates"]:
        row.update(
            state="excluded",
            reason_codes=["partition_mismatch"],
            features=None,
            weight_sum=None,
            distance=None,
        )
    unknown_fields(p["decision"], ["no_compatible_profiles"])
    assert ProfileMatchResult.model_validate(root_seal(p)).decision.chosen_label is None


def test_one_supported_label_remains_unknown_even_at_zero_distance():
    p = match()
    snapshot = p["evidence"]["snapshot"]
    host = snapshot["profiles"][1]
    for item in snapshot["inputs"]:
        if item["entry_id"] in host["selected_entry_ids"]:
            item["feature_values"] = dict.fromkeys(NAMES, 0.0)
    for f in host["features"].values():
        for row in f["group_values"]:
            row["median"] = 0.0
        f.update(
            state="excluded",
            reason_codes=["zero_dispersion"],
            weight=0.0,
            center=0.0,
            dispersion=0.0,
        )
    host.update(
        state="rejected",
        reason_codes=["insufficient_active_features", "insufficient_active_coverage"],
        active_feature_count=0,
        active_feature_coverage=dict(numerator=0, denominator=22, value=0.0),
    )
    rebind(p)
    d = p["decision"]
    d["candidates"][1].update(
        state="excluded",
        reason_codes=["profile_rejected"],
        features=None,
        weight_sum=None,
        distance=None,
    )
    d.update(
        ranked_profile_ids=[d["candidates"][0]["profile_id"]],
        runner_up_label=None,
        runner_up_distance=None,
        margin=None,
        state="unknown",
        chosen_label=None,
        reason_codes=["no_competing_label"],
    )
    assert ProfileMatchResult.model_validate(root_seal(p)).decision.best_distance == 0.0
