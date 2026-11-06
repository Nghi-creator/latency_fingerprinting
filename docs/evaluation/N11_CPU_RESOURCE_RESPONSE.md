# Candidate CPU resource difference response

`evaluation.cpu_resource_response` defines the separate release
`n11-cgroup-cpu-difference-response-candidate-v1`.
`cpu_resource_response_spec()` returns its content identity. It is a generic
resource measurement candidate, not a classifier, causal CPU diagnosis, media
degradation test or addition to N3's policy features.

`cpu_resource_response(windows)` consumes the complete `samples` mapping from a
previously verified producer `resource-observation.json`. Before using it, replay
the source inspector and byte-bound artifact through `verify_native_exports.py`.
The arithmetic API checks declared sample consistency but cannot authenticate
raw custody, execution, ownership witnesses or counter update freshness.

All five windows are required: healthy, degraded, relief, recovery and post.
Every supplied read is validated against the exact resource record schema;
condition names, fault settings and owned-worker metadata are not accepted fields.
The controller clock, quota/period and file identity must remain constant;
sequences are contiguous from zero, read brackets nonoverlapping and all six
cumulative source counters nondecreasing. Boolean/coercible numeric fields are
rejected. Quota is fixed at 200000/100000 microseconds. Future quota support would
need a separately reviewed context/contract change.

Each window requires 4–64 reads, at least 2 seconds between first read end and
last read start, at most 5 seconds between first read start and last read end,
at most 50 ms per read, at most 1.5 seconds between adjacent outer read bounds,
and at most 15 seconds between windows. Total reads are at most 128. Validly
structured unmet timing/sample limits return unavailable windows; malformed,
reset or context-changing input raises `ValueError`. No trimming, imputation or
adaptive sample selection is performed. Every read contributes to input identity,
including interior samples that do not affect endpoint arithmetic.

For microsecond counter delta `d` and read elapsed interval `[tmin,tmax]` in
nanoseconds, the rate envelope is:

`[max(0,d−1) × 1000 / tmax, (d+1) × 1000 / tmin]`.

The fixed one-microsecond sensitivity guard is explicit. It is not a confidence
interval, a guarantee about kernel update delay/burst size, or proof of exact
physical utilisation. All arithmetic uses rational numerator/denominator pairs.
Preserve these JSON integers losslessly; they can exceed JavaScript's exact
integer range.

Two rates are retained in each window:

- `cpu_quota_fraction`: CPU seconds consumed per wall second from `usage_usec`,
  divided by the fixed two-core quota;
- `throttled_seconds_per_wall_second`: reported throttled time rate from
  `throttled_usec`. This is not CPU utilisation or a wall-time percentage and
  is not clipped to one.

User/system CPU and period/throttling counts are checked for continuity but are
not selected response coordinates. No exact usage=user+system equality is
assumed across rounded kernel readings. No throttled-period count ratio is
computed under this contract.

The six fixed response coordinates retain both metrics for degraded minus
healthy, relief minus degraded, and post minus healthy. For interval rates
`[aL,aU]` and `[bL,bU]`, return `[aL−bU,aU−bL]`. These differences support zero
healthy rates without an epsilon or denominator fallback. They do not assume
statistical independence or replace intervals with midpoints.

Recovery has no difference coordinate but remains required for complete source
validity. Other eligible coordinates may stay visible for explanation when a
window is unavailable; the complete response remains unavailable unless all
five windows and six coordinates are eligible. There is no subset scoring.

The controller-clock resource response and worker-clock encoded response remain
separate source-local measurements. No cross-clock subtraction, frame residence
time, physical capture latency or N9 alignment follows. Post restoration follows
fault removal, not proof of probe benefit. Outputs keep confidence/diagnostic
labels null, independent support/accepted diagnostic groups zero, and acquisition
authority/empirical acceptance false. A future combined fitting/scoring method
must explicitly specify context binding, coordinates, arithmetic, abstention,
calibration and prospective protocol under its own identity.
