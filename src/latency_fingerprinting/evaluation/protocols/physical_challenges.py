"""Metadata-only physical fixture recipes; no runtime, scorer or collection authority."""

from copy import deepcopy

from latency_fingerprinting.analytical.policy_release import canonical_payload_bytes, payload_hash

RELEASE = "n11-physical-condition-challenge-recipe-v1"
NAMES = ("mixed_delay_pressure", "delay_to_pressure", "pressure_to_delay")
ERROR = "invalid_physical_challenge_recipe"
_NONE = dict(delay_us=0, pressure_workers=0)
_DELAY = dict(delay_us=34000, pressure_workers=0)
_PRESSURE = dict(delay_us=0, pressure_workers=2)
_MIXED = dict(delay_us=34000, pressure_workers=2)


def physical_challenge_recipe(name):
    """Return a canonical proposal, explicitly distinct from fixed-condition v1.

    Values preserve existing owned doses and safety ceilings. Witness requirements
    and phases are declarations: no returned object establishes feasibility,
    verifies a physical transition or grants permission to collect.
    """
    if type(name) is not str or name not in NAMES:
        raise ValueError(ERROR)
    before, after = {
        "mixed_delay_pressure": (_MIXED, _MIXED),
        "delay_to_pressure": (_DELAY, _PRESSURE),
        "pressure_to_delay": (_PRESSURE, _DELAY),
    }[name]
    changing = name != "mixed_delay_pressure"
    recipe = dict(
        method_release=RELEASE,
        name=name,
        scope="owned_fixture_challenge_not_causal_fault_label",
        stages=dict(healthy=_NONE, degraded=before, relief=after, recovery=after, post=_NONE),
        transitions=[dict(after="degraded", before="relief")] if changing else [],
        cadence_fps=dict(healthy=30, degraded=30, relief=24, recovery=30, post=30),
        safety=dict(
            maximum_condition_active_ms=20000,
            child_failsafe_ms=40000,
            cadence_action_ms=5000,
            maximum_measured_phase_ms=4500,
            cadence_settling_ms=100,
            cadence_settling_anchor="actual_setter_attempt",
            maximum_relief_start_ms=1750,
            maximum_cpu_read_ms=50,
            maximum_encoded_read_ms=100,
            extension_for_transition=False,
            failure="stop_and_verify_restoration_no_retry",
        ),
        witnesses=dict(
            generation="same_owned_camera_pipeline_peer_and_controller_generation",
            pressure="owned_pid_start_identity_cpu_progress_cgroup_identity_and_reap",
            property="fresh_identity_delay_preimage_set_readback_and_zero_postimage",
            phase="before_and_after_brackets_show_joint_state_for_complete_phase",
            transition="last_old_state_setter_brackets_first_new_state_and_new_establishment",
            transition_schedule="finish_before_cadence_dispatch_never_pause_started_action",
            transition_establishment_ms=1000,
            initial_condition_establishment_ms=1000,
            references="healthy_and_post_encoded_cpu_and_owned_absence_witnesses",
            receiver="acknowledged_delivery_binding_and_original_media_health_guards",
            clock_rule="retain_worker_and_controller_domains_no_cross_clock_subtraction",
        ),
        source_requirements=dict(
            separately_versioned_mode_observer_inspector_and_projection=True,
            fixed_condition_modes_accept_recipe=False,
            new_source_manifest_and_runtime_context=True,
            matched_single_condition_controls_and_new_fit_required=True,
            actual_session_and_correlation_documentation=True,
        ),
        scoring=dict(
            old_rx1_fit_reuse=False,
            paired_stationarity=(
                "violated_by_design_no_stable_pair_admission"
                if changing
                else "constant_owned_mixture_outside_training_labels"
            ),
            unavailable_and_rejected_inputs="separate_from_computed_abstention",
            single_condition_prediction="retain_as_descriptive_choice_not_mixture_truth",
            universal_abstention_acceptance_target=False,
            threshold_tuning_on_challenges=False,
        ),
        acquisition_authority=False,
        empirical_acceptance=False,
    )
    recipe = deepcopy(recipe)
    return {**recipe, "content_hash": payload_hash(recipe)}


def inspect_physical_challenge_recipe(recipe):
    """Check exact recipe declarations, not runtime events or reviewer authority."""
    try:
        if type(recipe) is not dict:
            raise ValueError(ERROR)
        expected = physical_challenge_recipe(recipe["name"])
        if canonical_payload_bytes(recipe) != canonical_payload_bytes(expected):
            raise ValueError(ERROR)
        return dict(
            state="declared_recipe_only_runtime_unimplemented",
            method_release=RELEASE,
            recipe_hash=expected["content_hash"],
            acquisition_authority=False,
            empirical_acceptance=False,
        )
    except (KeyError, TypeError, ValueError):
        raise ValueError(ERROR) from None
