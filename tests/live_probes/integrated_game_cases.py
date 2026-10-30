"""Small synthetic wrapper examples; no native observations or performance claims."""

from latency_fingerprinting.live_probes.integrated_game import MODES

META = dict(acquisition_id="game-cohort-1", producer_revision="a" * 40)


def cohort():
    rows = []
    for index, mode in enumerate(MODES):
        rows.append(
            dict(
                mode=mode,
                status="passed",
                live_authority=False,
                events=[
                    dict(
                        kind="control_result" if index == 0 else "game_failure_result",
                        ledger_state="clean" if index < 2 else "dirty",
                        result=dict(
                            request_id="request-1",
                            outcome="completed" if index == 0 else "aborted",
                            restoration="verified_by_port" if index < 2 else "unknown",
                            reason="duration_elapsed" if index == 0 else "cancelled",
                            live_authority=False,
                        ),
                    )
                ],
            )
        )
    return rows
