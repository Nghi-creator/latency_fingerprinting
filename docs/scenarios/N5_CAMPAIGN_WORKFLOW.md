# N5 campaign workflow and capture-pacing extension

**Coding status:** implemented; local verification recorded in the progress ledger.
**Live status:** not run. Docker Desktop on the Mac can provide the Linux engine;
a separate Linux machine is optional. Record the actual VM/container allocation.
[Original v1 contract](N5_EXPERIMENT_CONTRACT.md), [runtime ledger](N5_RUNTIME_ACCEPTANCE.md).

## Additive second fault contract

Frozen v1 healthy/host contention roots, release/pins, schemas and thresholds are
unchanged. Capture pacing uses `experiment-manifest-v2`,
`experiment-phase-evidence-v2`, `experiment-result-v2` and method
`n5-capture-pacing-v1`. Only `render_capture_slowdown` is approved in this extension;
network/encoder/client/mixed/changing controls stay unavailable. There are now
23 schemas: the previous fifteen plus three pacing, three campaign and two overhead
roots. Models and schemas import independently of runtime/file inspection.

The opt-in camera pipeline inserts `identity name=n5_capture_pacer` between the
capture caps and conversion, default delay zero, with handoffs disabled. Normal
startup has no new element, trace flags, campaign worker or evidence volume. See
[GStreamer's sleep-time property](https://gstreamer.freedesktop.org/documentation/coreelements/identity.html#identity:sleep-time).

A pacing action is fixed at 50,000 microseconds and zero workers. It starts before
degraded and stops before recovery. Its watchdog is bounded by degraded+probe+10 s,
40–300 s, and restores only the exact owned pipeline element. Foreign settings
or generations are never overwritten. Attempts, unknown clock offsets and failed
cleanup remain visible; successful setter startup is not a verified effect.

The independently recomputed predicate needs complete six-phase evidence, at
least 30 intervals/30 s in healthy/degraded/recovery and at least 30 exact same-frame
capture-output→pre-encode-queue-enter pairs in each evaluated phase. It uses the
lower median of integer stage delays. Baseline must reach 27 fps; degraded median
must be ≥40 ms and ≥40 ms above healthy, degraded FPS ≤95% of healthy, recovery
FPS ≥95% of healthy and recovery delay ≤healthy+10 ms. Available pacing effects
report `capture_delay_ns` and null CPU pressure. These provisional engineering
predicates are separate from N4's ≥500-pair/≥95%-coverage acceptance.

## Campaign ownership and commands

The producer library exposes `CampaignExecutor` and an opt-in camera control worker.
It operates on one existing draining peer; it does not launch or infer a workload.
An engine-owner workload/seed declaration must match the frozen plan. The camera
launcher supplies its observed Node version. Preflight retains observed runtime
metadata; unavailable preflight records a null acquisition in the index rather
than inventing versions, counters or bundle data.

The preparation command defaults to three reference and three held-out acquisitions
for healthy, host contention and capture pacing: 18 trials, each 10/30/30/30/30/10 s.
`--repeats` accepts 1–4; schedules are bounded to 24 trials. `--workers` declares
1–8 host workers, subject to actual observed CPU allocation. The seed is an owner
workload declaration; default schedule order is explicit and not randomized. Change
order only in the plan before submission/analysis. Each source ID is allocated
before execution; IDs and run aliases/repetition tuples cannot be reused.

Plans and inbox files are bounded, duplicate-safe UTF-8 JSON, closed fields and
private regular files. One immutable submission is accepted per camera lifetime.
A private nonblocking lease serializes submissions/execution and refuses dirty
ownership. Cancellation requires no live network API or arbitrary shell action.
Each successfully executed acquisition gets a fresh recording and source admission
floor, preserving old frozen traces without reusing their frames. Failed effects
remain in the schedule; aborted/unavailable/unsafe restoration stops subsequent
acquisitions. A terminal catalog records unexpected failure instead of leaving a
finished worker labeled running. Original request/plan bytes and all written bundles
are retained.

Producer commands, inside the engine container:

```sh
python3 -m scenario_harness.campaign_cli prepare --output /n5/control/plan.json \
  --core-version CORE_COMMIT --producer-version PRODUCER_COMMIT \
  --node-version OBSERVED_NODE_VERSION --workload-id workload-1 --seed 7 --workers 1
python3 -m scenario_harness.campaign_cli submit \
  --directory /n5/control --plan /n5/control/plan.json
python3 -m scenario_harness.campaign_cli cancel --directory /n5/control
```

The producer's [test procedure](../../../Pixelated-Studio-Edition/docs/n5-live-test-procedure.md)
details image/desktop startup, copying artifacts and the separate overhead request.
`clear-request` removes only fixed inbox/cancellation/error files under a clean
lease. It never removes acquired evidence or clears dirty restoration. Stop the
workload/camera before clearing an old request and starting another camera lifetime.

Core detached inspection:

```sh
latency-fingerprint inspect-experiment --bundle run-1.tar.gz --output result.json
latency-fingerprint inspect-campaign --directory campaign-1 --output campaign-report.json
```

The campaign inspector checks exact bounded inventory, plan/bundle byte receipts,
requested metadata, ordered acquisition prefixes, predeclared source IDs and
nonoverlapping acquisition windows, then verifies each experiment/effect. It stages
one opaque private compressed snapshot at a time and never extracts members into
paths. It reports every retained outcome and repeated reference/query predicates
for healthy and the two fault classes. Hashes/UUIDs/disjoint windows do not establish
scientific independence; external acquisition/workload verification and N4 gates
remain explicit. No report promotes N3 features or claims Phase 1 completion.

## Frozen overhead collection and reporting

The overhead submission uses a ten-trial engineering schedule. On the same warm
camera pipeline it executes five pairs in A/B, B/A, A/B, B/A, A/B order, each with
10 s warm-up and a fresh 30 s measured window. A is tracing disabled; B uses fresh
sampling-1 collectors, bounds 2000/10000 and the nominal 50 ms capture budget.
Camera-process CPU uses `process_time_ns` difference divided by observed wall time;
FPS uses encoded counter differences. Every raw pair, five enabled trace receipts
and export/write duration is retained. Separate ordinary-enabled and diagnostic
windows report bounded raw callback costs, actual probe count and process/FPS
changes; diagnostic timing is installed only for that explicit window.

```sh
python3 -m scenario_harness.campaign_cli prepare --overhead \
  --output /n5/control/overhead-plan.json --campaign-id campaign-2 \
  --core-version CORE_COMMIT --producer-version PRODUCER_COMMIT \
  --node-version OBSERVED_NODE_VERSION --workload-id workload-1 --seed 7
python3 -m scenario_harness.campaign_cli submit-overhead \
  --directory /n5/control --plan /n5/control/overhead-plan.json
latency-fingerprint inspect-overhead --directory campaign-2 --output overhead-report.json
```

The inspector verifies plan/order, every trace receipt, ≥500 usable queue/encode
pairs, ≥95% joint coverage against both trace frames and measured encoded counts,
zero nominal collector drops, all baselines ≥27 fps, at least 1000 diagnostic samples,
and verified cleanup. Five-pair medians use exact rational arithmetic: CPU increase
≤5 percentage points and FPS change ≥−5%, equality included. Synthetic evidence
can pass arithmetic but never real overhead acceptance. Generic `validate` checks
all new root/report shapes; use inspection for linked numerical evidence.

Both new inspection commands write canonical private atomic output silently and
preserve existing output on fixed failure without supplied path/data echo. Tiny
capacity, interruption/restart, disable/re-enable/two-peer/browser cases and external
source independence still require the separate actual trials in the inherited
acceptance ledger. Coding these tools does not replace running them.
