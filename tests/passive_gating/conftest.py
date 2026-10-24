"""Fresh independent model-only roots for each reconstruction attack."""

import pytest

from .cases import baseline, evidence, replay_payload, window


@pytest.fixture
def roots():
    ev, windows = evidence(
        [
            window("q0", query=True, fps=40.0),
            window("q1", query=True, start=2000, end=4000, fps=40.0),
            window("q2", query=True, start=4000, end=6000, fps=40.0),
        ]
    )
    b = baseline(ev, windows)
    r = replay_payload(b, windows)
    return ev, windows, b, r
