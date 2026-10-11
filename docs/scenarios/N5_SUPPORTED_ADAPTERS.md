# N5 supported adapters and fixed effects

**Delivered:** Step 5 software, 2026-10-11.
**Producer implementation/API:** [Supported adapter guide](../../../Pixelated-Studio-Edition/docs/n5-adapters.md).
**Contract:** [Frozen v1](N5_EXPERIMENT_CONTRACT.md).
**Criteria/availability:** [Capability matrix](N5_ADAPTER_CAPABILITIES.md).
**Independent expectations:** [Step 2 tables](N5_EXPERIMENT_EXAMPLES.md).

The producer now supplies concrete control-thread hooks for one existing Linux
camera peer and bounded owned CPU subprocesses. Preflight checks actual source,
transport, fixed VP8 input caps, encoder progress, opt-in recording ownership,
monotonic clock, visible cgroup/affinity allocation and native process-clock/pidfd
access. Workload alias/seed and engine Node version remain explicit declarations
from the campaign owner, which must provide the known scene recipe. This does not
infer screen content or prove a real campaign from a declaration.

Every worker stays parked until its exact boot/start/PID identity is durably
journalled. Startup acknowledgements do not prove a fault effect. Cleanup/recovery
pins and verifies process generations before TERM/KILL, uses bounded waits/reap and
never signals a reused PID. Private identities stay outside public roots. Unknown
workload/GI ownership remains dirty; native worker restoration cannot clean the
whole lease by itself. Owner SIGKILL cannot guarantee restoration.

Raw intervals use one exact camera generation's output counter and only owned
high-resolution worker CPU clocks. Configuration/allocation drift, disconnect,
counter regression, unexpected exit and CPU above owned capacity fail closed.
Retired camera callbacks cannot increment a replacement peer's counters. No core
dependency, filesystem I/O or new workload action is added to frame callbacks.

The producer's immutable `MeasuredEffect` calculator independently checks raw
coverage and frozen predicates using integer comparisons. Nominal 30/24/30 fps
with 60% CPU verifies. The 28.5 fps/50% CPU boundary verifies inclusively. Adequate
CPU with unchanged FPS fails degradation; insufficient baseline/pressure/recovery
keeps the frozen reason priority. All three evaluated phases need ≥30 intervals
and ≥30 seconds. Invalid/partial evidence and unverified cleanup cannot pass.

This remains a private producer calculation, not detached artifact inspection.
Core roots/schemas, earlier pins, policy releases and matcher thresholds are
unchanged. [Step 6](../plans/NEXT_IMPLEMENTATION_PLAN.md) must bind actual exported
roots/checksums and independently recompute effects during bounded offline adoption.
Independent fixture releases follow in Step 7.

Local tests use fake native/Gst dependencies and independently specified totals;
the actual parked-child integration case is skipped on this Mac. No real pressure,
Linux capture, overhead, minimum-version or hosted result was collected. Supported
software never establishes live availability. Other scenarios remain unavailable;
healthy plus one approved CPU fault cannot meet Phase 1.3's two real fault-class
gate. [Inherited N4 acceptance](../observability/N4_RUNTIME_ACCEPTANCE.md) stays open.
