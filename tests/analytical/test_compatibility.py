"""Structural context/probe compatibility, strict JSON equality and ordered codes."""

import pytest
from pydantic import ValidationError

from latency_fingerprinting.analytical.compatibility import compatibility_rejections
from latency_fingerprinting.analytical.matching import match_response_v2
from latency_fingerprinting.analytical.repository import FingerprintRepositoryV2

from .matching_cases import fingerprint, response


def test_run_identity_clock_domain_and_named_scenario_are_ignored():
    def changes(pair):
        for phase in ("degraded_window", "relief_window"):
            window = pair[phase]
            window["run_id"] += "-other"
            window["clock"]["domain_id"] += "-other"
            window["context"].update(
                contextId="other-context", nodeId="other-node", networkScenario="other-scenario"
            )
        pair["observation_id"] += "-other"
        pair["intervention"]["probe_id"] += "-other"

    query, reference = response(), fingerprint(changes=changes)
    assert compatibility_rejections(query, reference) == ()
    result = match_response_v2(query, query.policy, FingerprintRepositoryV2((reference,)))
    assert result.decision == "matched"


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("status", ("validation_status",)),
        ("producer", ("capture_method_mismatch",)),
        ("context", ("context_mismatch",)),
        ("probe", ("probe_mismatch",)),
        ("settings", ("settings_mismatch",)),
        ("request", ("probe_mismatch", "settings_mismatch")),
        (
            "real",
            (
                "provenance_mismatch",
                "capture_method_mismatch",
                "clock_meaning_mismatch",
                "probe_mismatch",
            ),
        ),
    ],
)
def test_each_constructible_compatibility_rule(kind, expected):
    def changes(pair):
        for phase in ("degraded_window", "relief_window"):
            window = pair[phase]
            if kind == "producer":
                window["capture_method"]["producer_version"] = "other-version"
            elif kind == "context":
                window["context"]["workloadId"] = "other-workload"
            elif kind == "settings":
                window["effective_settings"]["constantSetting"] = True
        if kind == "probe":
            pair["intervention"]["intensity"] = 2
        elif kind == "request":
            pair["intervention"]["requested_settings"]["targetFps"] = 20
            pair["relief_window"]["effective_settings"]["targetFps"] = 20

    query = response()
    reference = fingerprint(
        status="unreviewed" if kind == "status" else "software_checked",
        real=kind == "real",
        changes=changes,
    )
    assert compatibility_rejections(query, reference) == expected
    result = match_response_v2(query, query.policy, FingerprintRepositoryV2((reference,)))
    assert result.candidate_rejections[reference.fingerprint_id] == expected
    assert result.unknown_reason == "no_compatible_fingerprints"


@pytest.mark.parametrize(
    "field,expected", [("context", "context_mismatch"), ("settings", "settings_mismatch")]
)
def test_bool_does_not_equal_number_in_structural_json(field, expected):
    def change(value):
        def apply(pair):
            for phase in ("degraded_window", "relief_window"):
                window = pair[phase]
                if field == "context":
                    window["context"]["nominalStreamProfile"]["flag"] = value
                else:
                    window["effective_settings"]["flag"] = value

        return apply

    assert compatibility_rejections(
        response(changes=change(1)), fingerprint(changes=change(True))
    ) == (expected,)


def test_all_applicable_codes_are_retained_in_contract_order():
    def changes(pair):
        for phase in ("degraded_window", "relief_window"):
            pair[phase]["context"]["workloadId"] = "other"
            pair[phase]["effective_settings"]["constant"] = 1
        pair["intervention"]["intensity"] = 2

    reference = fingerprint(status="rejected", real=True, changes=changes)
    assert compatibility_rejections(response(), reference) == (
        "validation_status",
        "provenance_mismatch",
        "capture_method_mismatch",
        "clock_meaning_mismatch",
        "context_mismatch",
        "probe_mismatch",
        "settings_mismatch",
    )


@pytest.mark.parametrize("kind", ["policy", "registry"])
def test_unknown_meanings_fail_input_validation_before_comparison(kind):
    query, reference = response(), fingerprint()
    if kind == "policy":
        bad_policy = reference.response.policy.model_copy(update={"policy_version": "2.0.0"})
        altered = reference.response.model_copy(update={"policy": bad_policy})
    else:
        window = reference.response.observation.degraded_window
        window = window.model_copy(
            update={
                "registry": window.registry.model_copy(
                    update={"content_hash": "sha256:" + "0" * 64}
                )
            }
        )
        observation = reference.response.observation.model_copy(update={"degraded_window": window})
        altered = reference.response.model_copy(update={"observation": observation})
    with pytest.raises(ValidationError):
        match_response_v2(
            query,
            query.policy,
            FingerprintRepositoryV2((reference.model_copy(update={"response": altered}),)),
        )


@pytest.mark.parametrize(
    "module",
    [
        "latency_fingerprinting.analytical.compatibility",
        "latency_fingerprinting.analytical.matching",
        "latency_fingerprinting.models.match_v2",
    ],
)
def test_public_entry_modules_import_in_fresh_interpreters(module):
    import subprocess
    import sys

    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        check=True,
    )
    assert completed.stdout == completed.stderr == b""
