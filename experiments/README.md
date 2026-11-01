# Recorded experiments

This directory retains sanitized recorded evidence and reusable acquisition tools.
Synthetic regression inputs belong in [`fixtures/`](../fixtures/README.md);
raw/private captures and session notes remain ignored.

| Directory | Scope |
| --- | --- |
| [`p0/controlled-run-001/`](p0/controlled-run-001/) | Original P0 feasibility record and unvalidated seed fingerprint |
| [`p0/controlled-run-002/`](p0/controlled-run-002/) | Independent P0 repeat query against the run 001 seed |
| [`n5-runtime-20261013/`](n5-runtime-20261013/) | N5 runtime campaign and overhead evidence |
| [`n5-browser-execution-20261014/`](n5-browser-execution-20261014/) | N5 browser execution evidence |

The [P0 processing guide](p0/CONTROLLED_RUN_PROCESSING.md) describes the frozen
observation-v1 workflow and its evidence limits. It does not qualify current
contracts or production behavior.

[`bounded_cpu_pressure.py`](bounded_cpu_pressure.py) and
[`record_bundle_checksums.py`](record_bundle_checksums.py) are shared capture
utilities. They remain outside `p0/`; callers supply the run directory explicitly.
