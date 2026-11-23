# Physical mixed and changing fixture challenges

`n11-physical-condition-challenge-recipe-v1` specifies three metadata-only recipes
for the owned contained fixture. It is separate from the three fixed-condition
source modes and from the [derived-source challenge checks](N11_OFFLINE_EVALUATION.md).
It does not implement a native runtime or authorize acquisition.

```python
from latency_fingerprinting.evaluation.protocols.physical_challenges import (
    physical_challenge_recipe,
    inspect_physical_challenge_recipe,
)

recipe = physical_challenge_recipe("mixed_delay_pressure")
declaration = inspect_physical_challenge_recipe(recipe)
assert declaration["state"] == "declared_recipe_only_runtime_unimplemented"
```

Recipes are detached dictionaries with a content hash. Inspection requires the
exact canonical declaration, including its safety limits; a recomputed hash does
not approve changed doses, transitions or budgets. These are not generic schema
roots or executable native acquisition plans. Existing contracts remain unchanged.

## Recipes and physical evidence

All recipes start with a healthy reference and end with a post-cleanup reference:
zero owned identity delay and no owned pressure workers. Neither implies global
host health. Cadence remains 30 fps degraded, 24 fps relief and 30 fps recovery.

| Recipe | Degraded | Relief and recovery | Condition transition |
| --- | --- | --- | --- |
| `mixed_delay_pressure` | 34,000 µs identity delay plus two owned pressure workers | Same simultaneous mixture | None between measured phases |
| `delay_to_pressure` | 34,000 µs identity delay, no pressure workers | Zero delay plus two owned pressure workers | Between degraded and relief |
| `pressure_to_delay` | Zero delay plus two owned pressure workers | 34,000 µs identity delay, no pressure workers | Between degraded and relief |

Mixtures must run simultaneously in the same owned source; averaging two old
traces is not a physical case. Changes occur between measured phases, with a new
one-second establishment after the setter/readback. This version does not specify
within-phase switching. Before/after witnesses must cover each complete measured
phase, not just prove that an injection command was issued.

Keep the original generation, camera/pipeline/peer ownership, fresh property
reads, pressure PID/start identities, CPU progress, cgroup identity, receiver
acknowledgment, media-health and restoration checks. A transition must retain its
last old-state read, setter brackets, first new-state read and establishment
boundary. Complete condition switching and establishment before dispatching the
cadence action: inserting a one-second switch into an already started action
could exceed its existing 1.75-second relief-start gate. Never pause or reset a
started action clock. Pressure removal must confirm process reaping; delay removal must
confirm the zero postimage. Healthy/post references retain encoded and CPU evidence.
Worker and controller clocks remain separate; no cross-clock subtraction.

The existing limits remain ceilings: 20 seconds of active condition, 40-second
child failsafe, 5-second cadence action, 4.5-second measured phase, 1.75-second
relief-start bound, 100 ms cadence settling anchored at the actual setter attempt,
50 ms CPU read and 100 ms encoded read. Transition/establishment work must
fit inside those limits. It cannot extend a watchdog or postpone its anchor.
Actual feasibility and concurrent dose indicators require native qualification.

## Source and scoring boundaries

The current fixed-condition selector, observer and receipts reject these recipes.
Implement a separately versioned source mode, transition-capable observer,
evidence inspector and projection before collection. Reusing old names or
loosening the old inspector would corrupt the original qualification boundary.

A changed source manifest/runtime context cannot borrow the frozen rx1 fit.
Qualify matched single-condition controls under the same new source and prepare
a new calibration/query protocol. Genuine sessions and correlations must be
documented; blocks are not automatically independent sessions.

Keep challenge identity and injected-condition labels out of numerical scoring
inputs. A stable mixture may yield an eligible response but has no single
training-condition truth. Preserve a computed abstention or single-condition
choice descriptively; neither is automatically an accepted diagnosis. Changing
conditions violate stable-pair assumptions. Do not stamp those pairs as stable
or force them through N2/N3/candidate admission. Retain a rejected/unavailable
input distinctly from a computed abstention, and record which structural gate ran.

Do not prescribe universal abstention as a target after inspecting challenges.
Report every planned case, including failure and unstarted suffixes, and keep
source verification, projection availability and numerical decisions separate.
No threshold tuning, fitting, replacement or retry uses challenge outcomes.

The next engineering step is native source implementation and synthetic lifecycle
qualification, followed by a concretely reviewed bounded engineering pilot. A
prospective challenge study is a separate collection decision. Numerical counts
and private session-specific allocations belong in the working plan, not in this
reusable recipe contract.
