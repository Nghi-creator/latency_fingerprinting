"""Numeric parity does not transfer old method/source acceptance to mixed cases."""

import json

import pytest

from latency_fingerprinting.evaluation.projections.physical_challenge_projection import (
    project_physical_challenge,
)
from latency_fingerprinting.evaluation.projections.shared_window_projection import (
    project_shared_window_source,
)
from tests.evaluation.projections.test_event_span_projection import event_source
from tests.evaluation.protocols.test_physical_challenge_measurements import source


def test_stable_mixture_preserves_exact_old_arithmetic_with_separate_method_and_identity():
    raw = json.dumps(source()).encode()
    result = project_physical_challenge(raw)
    old = project_shared_window_source(event_source(), event_span=True)
    assert result["state"] == "descriptive_phase_rates_available"
    assert result["phase_rates"] == old["phase_rates"]
    assert result["marginal_bounds"] == old["marginal_bounds"]
    assert len(result["marginal_bounds"]) == 9
    assert result["projection_id"] != old["projection_id"]
    assert result["method_spec"]["content_hash"] != old["method_spec"]["content_hash"]
    assert result["diagnostic_label"] is None and not result["scoring_authority"]


@pytest.mark.parametrize("recipe", ["delay_to_pressure", "pressure_to_delay"])
def test_changing_conditions_are_rejected_instead_of_scored_or_called_abstentions(recipe):
    result = project_physical_challenge(json.dumps(source(recipe)).encode())
    assert result["state"] == "rejected_changing_pair"
    assert result["reason_codes"] == ["changing_pair_not_stable"]
    assert result["phase_rates"] == result["marginal_bounds"] == {}
    assert result["stable_pair_admitted"] is False


def test_missing_trace_is_unavailable_and_stable_zero_cpu_has_no_MAD_divisor():
    a = source()
    assert (
        project_physical_challenge(json.dumps(a).encode())["state"]
        == "descriptive_phase_rates_available"
    )
    a["events"] = [e for e in a["events"] if e["kind"] != "n11_encoded_event_trace"]
    result = project_physical_challenge(json.dumps(a).encode())
    assert result["state"] == "unavailable" and result["marginal_bounds"] == {}
