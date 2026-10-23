"""Stage independent N9 model operands for an isolated installed-wheel smoke check."""

from tests.passive_gating.cases import POLICY, baseline, canonical, evidence, replay_payload, window

SCRIPT = """
import json
import pathlib
import sys
from latency_fingerprinting import models as m
from latency_fingerprinting import passive_gating as gate
p = json.loads(pathlib.Path(sys.argv[1]).read_bytes())
b = gate.fit_passive_baseline(p["evidence"], p["training"], p["policy"])
assert b.model_dump(mode="json") == p["baseline"]
r = m.PassiveReplay.model_validate(p["replay"])
rebuilt = gate.create_passive_replay(
    b, mode=r.mode, stream=r.stream.model_dump(), start_ms=r.start_ms,
    windows=[w.model_dump(mode="json") for w in r.windows],
    events=[e.model_dump() for e in r.events])
assert rebuilt == r
result = gate.evaluate_passive_replay(b, r, m.PassiveGatePolicy.model_validate(p["policy"]))
assert [row.recommendation for row in result.rows] == ["observe", "observe", "probe"]
assert result.final_state.bad_duration_ms == 6000
assert result.final_state.proposals == 1
assert result.final_state.last_proposal_ms == 6000
assert all(row.cause_label is None for row in result.rows)
assert m.PassiveBaseline.model_validate(b) == b
encoded = result.model_dump_json(by_alias=True)
assert m.PassiveGateResult.model_validate_json(encoded) == result
pathlib.Path(sys.argv[2]).write_text(result.model_dump_json(by_alias=True))
print("Installed N9 pure baseline/replay and all four standalone roots verified.")
"""


def stage(directory):
    ev, windows = evidence(
        [
            window("q0", query=True, fps=40.0),
            window("q1", query=True, start=2000, end=4000, fps=40.0),
            window("q2", query=True, start=4000, end=6000, fps=40.0),
        ]
    )
    b = baseline(ev, windows)
    data = dict(
        policy=POLICY,
        evidence=ev,
        training={key: value for key, value in windows.items() if key.startswith("train")},
        baseline=b,
        replay=replay_payload(b, windows),
    )
    operands = directory / "n9-model-operands.json"
    result = directory / "n9-result.json"
    operands.write_bytes(canonical(data))
    return operands, result
