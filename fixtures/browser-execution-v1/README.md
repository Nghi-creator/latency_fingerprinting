# Browser execution fixtures, release 1.0.0

Synthetic independent evidence for `n4-browser-execution-v1`; no live acceptance claim.
Each case has a canonical record, checksum/length manifest and independently
specified expected summary. Expectations were authored from integer tables,
without calling the production collector or reconstruction algorithm.

| Case | Original API method | Additional execution method |
| --- | --- | --- |
| paired | Four frames; two negative exclusions; usable deltas 0 and 200,000 ns | Usable 350,000 and 100,000 ns; one negative and one missing endpoint |
| partial | One negative pair, retained in two events | Third event capacity-dropped; missing endpoint exclusion |
| unavailable | No callbacks; API unavailable | No callbacks; API unavailable |

The paired execution mean is 225,000 ns (0.225 ms); the original API mean is
100,000 ns (0.1 ms). Neither negative result is clamped. All three events share
one global event budget. Absolute clock origins are absent.

Read-only pin checks:

```sh
.venv/bin/python -m tests.observability.check_browser_execution
```

For the actual producer exporter, run in Pixelated's checkout (existing output
files in the selected directory are overwritten; choose a fresh directory):

```sh
N4_BROWSER_EXECUTION_BUNDLES_DIR=/private/tmp/n4-execution-produced \
  node --test --experimental-strip-types apps/web/tests/unit/player/browserStageTraceV2.test.ts
```

Then run in the core checkout:

```sh
.venv/bin/python -m tests.observability.check_browser_execution \
  --producer-bundles /private/tmp/n4-execution-produced
```

The optional handoff checks exact canonical raw record bytes and independent
summary bytes through directory/archive adoption and the normal CLI. Old N4 v1
fixtures remain in `fixtures/observability/` with their original release pins.
