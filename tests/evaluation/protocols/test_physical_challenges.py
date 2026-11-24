"""Physical challenge recipes preserve ownership, domains and original budgets."""

from copy import deepcopy

import pytest

from latency_fingerprinting.evaluation.protocols.physical_challenges import (
    inspect_physical_challenge_recipe,
    physical_challenge_recipe,
)


@pytest.mark.parametrize("name", ["mixed_delay_pressure", "delay_to_pressure", "pressure_to_delay"])
def test_recipes_require_new_source_and_matched_calibration(name):
    recipe = physical_challenge_recipe(name)
    result = inspect_physical_challenge_recipe(recipe)
    assert result["state"] == "declared_recipe_only_runtime_unverified"
    assert result["acquisition_authority"] is False
    assert result["empirical_acceptance"] is False
    assert (
        recipe["stages"]["healthy"]
        == recipe["stages"]["post"]
        == {
            "delay_us": 0,
            "pressure_workers": 0,
        }
    )
    assert recipe["safety"]["maximum_condition_active_ms"] == 20000
    assert recipe["safety"]["child_failsafe_ms"] == 40000
    assert recipe["safety"]["cadence_action_ms"] == 5000
    assert recipe["safety"]["maximum_relief_start_ms"] == 1750
    assert recipe["safety"]["cadence_settling_anchor"] == "actual_setter_attempt"
    assert recipe["scoring"]["old_rx1_fit_reuse"] is False


def test_mixed_means_simultaneously_owned_not_averaged_sources():
    recipe = physical_challenge_recipe("mixed_delay_pressure")
    assert all(
        recipe["stages"][p] == {"delay_us": 34000, "pressure_workers": 2}
        for p in ("degraded", "relief", "recovery")
    )
    assert recipe["transitions"] == []


@pytest.mark.parametrize("name", ["delay_to_pressure", "pressure_to_delay"])
def test_change_happens_between_phases_and_needs_new_establishment(name):
    recipe = physical_challenge_recipe(name)
    assert recipe["stages"]["degraded"] != recipe["stages"]["relief"]
    assert recipe["stages"]["relief"] == recipe["stages"]["recovery"]
    assert recipe["transitions"] == [{"after": "degraded", "before": "relief"}]
    assert recipe["witnesses"]["transition_establishment_ms"] == 1000
    assert recipe["scoring"]["paired_stationarity"] == "violated_by_design_no_stable_pair_admission"


@pytest.mark.parametrize("field", ["dose", "budget", "phase", "clock", "scoring", "extra", "hash"])
def test_modified_recipe_cannot_claim_the_canonical_contract(field):
    recipe = physical_challenge_recipe("mixed_delay_pressure")
    if field == "dose":
        recipe["stages"]["relief"]["delay_us"] = 35000
    elif field == "budget":
        recipe["safety"]["maximum_condition_active_ms"] = 21000
    elif field == "phase":
        recipe["stages"]["post"]["pressure_workers"] = 2
    elif field == "clock":
        recipe["witnesses"]["clock_rule"] = "subtract_worker_from_controller"
    elif field == "scoring":
        recipe["scoring"]["old_rx1_fit_reuse"] = True
    elif field == "extra":
        recipe["approved"] = True
    else:
        recipe["content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="invalid_physical_challenge_recipe"):
        inspect_physical_challenge_recipe(recipe)


@pytest.mark.parametrize("name", [None, True, "healthy", "host_contention", "mixed;run", 0])
def test_names_are_a_closed_fixture_namespace(name):
    with pytest.raises(ValueError, match="invalid_physical_challenge_recipe"):
        physical_challenge_recipe(name)


def test_returned_recipes_do_not_share_mutable_state():
    first = physical_challenge_recipe("mixed_delay_pressure")
    pristine = deepcopy(first)
    first["stages"]["degraded"]["pressure_workers"] = 0
    assert physical_challenge_recipe("mixed_delay_pressure") == pristine
