"""Declared structural compatibility for separate v2 analytical comparisons."""

COMPATIBILITY_CODES = (
    "validation_status",
    "registry_mismatch",
    "policy_mismatch",
    "provenance_mismatch",
    "capture_method_mismatch",
    "clock_meaning_mismatch",
    "context_mismatch",
    "probe_mismatch",
    "settings_mismatch",
)


def compatibility_rejections(query, fingerprint):
    # Resolve only when called: model root validation also imports the closed codes.
    from ..models.v2_common import json_equal

    reference = fingerprint.response
    a, b = query.observation, reference.observation
    aw, bw = a.degraded_window, b.degraded_window
    ignored = {"context_id", "node_id", "network_scenario"}
    contexts = [
        {
            key: value
            for key, value in window.context.model_dump(mode="json").items()
            if key not in ignored
        }
        for window in (aw, bw)
    ]
    probes = [
        {
            key: getattr(probe, key)
            for key in (
                "probe_type",
                "probe_version",
                "application_method",
                "intensity",
                "requested_settings",
            )
        }
        for probe in (a.intervention, b.intervention)
    ]
    checks = (
        fingerprint.validation_status == "software_checked",
        aw.registry == bw.registry,
        query.policy == reference.policy,
        aw.provenance == bw.provenance,
        aw.capture_method == bw.capture_method,
        (aw.clock.basis, aw.clock.provenance) == (bw.clock.basis, bw.clock.provenance),
        json_equal(*contexts),
        json_equal(*probes),
        json_equal(aw.effective_settings, bw.effective_settings)
        and json_equal(a.relief_window.effective_settings, b.relief_window.effective_settings),
    )
    return tuple(
        code for code, passed in zip(COMPATIBILITY_CODES, checks, strict=True) if not passed
    )
