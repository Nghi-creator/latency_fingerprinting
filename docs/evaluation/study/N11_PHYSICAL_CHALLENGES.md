# Physical mixed and changing fixture challenges

`n11-physical-condition-challenge-recipe-v1` specifies three metadata-only recipes
for the owned contained fixture. It is separate from the three fixed-condition
source modes and from the [derived-source challenge checks](N11_OFFLINE_EVALUATION.md).
The recipe declaration itself does not verify a native runtime or authorize acquisition.

```python
from latency_fingerprinting.evaluation.protocols.physical_challenges import (
    physical_challenge_recipe,
    inspect_physical_challenge_recipe,
)

recipe = physical_challenge_recipe("mixed_delay_pressure")
declaration = inspect_physical_challenge_recipe(recipe)
assert declaration["state"] == "declared_recipe_only_runtime_unverified"
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

## Command transcript inspection

The producer implements a separate fixture peer wrapper, bounded private-file
commands and joint-condition phase observer. The consumer checks their command
transcript with:

```python
from latency_fingerprinting.evaluation.protocols.physical_challenge_receipts import (
    inspect_challenge_transcript,
)

inspection = inspect_challenge_transcript(original_transcript_json_bytes)
assert inspection["n2_pair_admitted"] is False
```

This API accepts at most 4 MiB of strict JSON. It requires ten ordered normal
commands, exact canonical request/ack strings, original request hashes, unchanged
event prefixes, generation/channel/clock bindings, phase timing and terminal
cleanup. It checks controller and worker clocks separately. A failed or partial
prefix raises `ValueError("invalid_challenge_transcript")`; keep that original
prefix in the enclosing failed/unavailable case rather than retrying or dropping it.
The response is an inspection dictionary, not a new generic-validation schema root.

A consistent transcript establishes declared lifecycle consistency only.
`source_media_verified`, `resource_dose_verified`, `n2_pair_admitted` and
`empirical_acceptance` remain false. It does not rebuild raw browser/engine media,
verify numerical resource dose, qualify encoded-counter projection or authenticate
the supplied records. Changing recipes retain `changing_pair_not_stable`;
constant mixtures and controls still need separate source/projection admission.
The [synthetic fixture corpus](../../../fixtures/physical-challenge-v1/README.md)
exercises these boundaries using invented ports and clocks.

New source transcripts additionally retain `n11-physical-pressure-start-v1` in
each condition-application event: either the original pressure helper result and
exact active-intent JSON, bracketed on the worker clock, or explicit `null` when
that operation does not start pressure. Inspection checks the intent hash, two
distinct PID/start identities, matching worker boot, declared two-core allocation,
20-second lifetime and 40-second failsafe, and agreement with the first pressure
witness. These declarations do not authenticate execution or establish actual CPU
dose. The producer reads the existing durable file before cleanup removes it.

Use `inspect_challenge_transcript(raw, require_pressure_start=True)` for this
source requirement. The default remains compatible with historical transcripts;
they return `pressure_start_receipts_verified=False` when this evidence is absent.
Any supplied receipt is validated even without the requirement. A successful new
receipt leaves media, dose, N2 admission and empirical acceptance false.

## Raw acquisition and custody

The producer now wires six closed challenge/control acquisition modes into the
native/browser driver. Receiver-delivery and encoded-event diagnostics are
mandatory for this path. Source hashing and container mounts include current N11
helpers. A shared native-software identity function binds the prepared plan to
the actual driver context; it is distinct from the broader source-manifest hash.

The one-shot collector retains original acquisition/plan/exclusion bytes,
complete command strings and three raw phase captures. It never emits an N2
observation pair or a stable-pair bundle. Failed/partial acquisitions and changed
sources retain their original artifacts and a failure receipt. A failed overall
case cannot become a completed case just because some raw bytes replay.

```python
from latency_fingerprinting.evaluation.protocols.physical_challenge_raw import (
    inspect_challenge_raw_export,
)

custody = inspect_challenge_raw_export(
    original_acquisition_bytes, original_plan_bytes,
    original_raw_export_bytes, original_exclusion_receipt_bytes,
)
assert custody["n2_pair_admitted"] is False
```

This checks the four byte identities, native/source declarations, excluded-ID
ledger, all three captures and the embedded lifecycle transcript. Limits are
4 MiB each for acquisition/export and 1 MiB each for plan/exclusions. It does not
authenticate execution or verify raw media semantics, actual resource dose or
source-file contents. All media/dose/N2/empirical acceptance flags remain false.
Six invented exports produced by the JS exporter pass the Python custody checks;
they are software vectors, not native cases.

## Raw media and measurement windows

The producer's `inspectPhysicalChallengeMedia` checks the original acquisition
bytes against the explicit acquisition ID. It reuses the paired cadence and
restoration checks and raw within-phase settings checks, without declaring an N2
pair. It additionally checks challenge phase duration, browser connection/counter
continuity, native source allocation and encoder counter progression, including
retained prefixes outside the browser window. The collector saves raw artifacts
before this inspection. A rejection retains those files and closes the attempt
with `failure.json`; a passed raw acquisition alone is not a successful case.

The SDK can independently reconstruct counter windows:

```python
from latency_fingerprinting.evaluation.protocols.physical_challenge_measurements import (
    inspect_challenge_measurements,
)

measurements = inspect_challenge_measurements(original_acquisition_bytes)
assert measurements["n2_pair_admitted"] is False
```

This bounded byte interface requires the explicit challenge method/mode, a
generation-bound controller context, per-phase CPU samples and original native
and encoded getter brackets. It reuses the existing CPU interval calculation and
encoded trace rules under the challenge reference namespace. The original
fixed-condition entrypoint and its namespace remain unchanged. CPU read limits
and the 100 ms encoded-getter limit remain in force. A valid missing/ineligible
trace remains `unavailable`; it does not become a numerical abstention.

These are component checks. They do not yet jointly verify raw browser/controller
phase alignment, complete command/reference/receiver links, condition ownership
or dose. Their source/media, N2 and empirical acceptance flags remain false.
Changing conditions can have reconstructed counters while `stable_condition` is
false and stable-pair admission remains false. No scoring or fitting uses these
reports before the separate complete source/projection gate.

The recipe inspector now reports runtime **unverified** by metadata inspection;
the recipe content identities and authority/acceptance gates are unchanged. Older
archived declaration reports retain their original software-state wording.

Next are full source/media inspection and projection qualification, followed by
a concretely reviewed bounded native engineering pilot. A
prospective challenge study is a separate collection decision. Numerical counts
and private session-specific allocations belong in the working plan, not in this
reusable recipe contract.
