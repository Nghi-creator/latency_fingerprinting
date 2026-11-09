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

N11 operator utilities are also tracked here:

- [`verify_native_exports.py`](verify_native_exports.py) replays a condition case's
  source hashes, native/phase receipt links, producer condition inspector, SDK/CLI
  windows and N2/N3 response. Its default is read-only. `--write-derived` creates
  missing derived files exclusively for the fixed condition-plan recipe.
- [`archive_evidence.py`](archive_evidence.py) creates an exclusive local archive
  with a checksum manifest and verifies every member; it can also verify an
  existing archive and bind a prior archive by its expected SHA-256.
- [`run_study_job.py`](run_study_job.py) supervises one bounded POSIX command in
  detached process sessions, with heartbeat, logs, terminal result and token-bound
  stop requests. It never retries or resumes a study.

See the [N11 operator tools guide](../docs/evaluation/N11_OPERATOR_TOOLS.md).
The [engineering pipeline qualification](../docs/evaluation/N11_PIPELINE_QUALIFICATION.md)
uses `qualify_resource_pipeline.py` for separate counter-specific projection,
fitting and truth-free scoring. Its engineering-only acquisitions are excluded
from prospective studies; accuracy is not a qualification gate.

`diagnose_counter_specific_fit.py` reconstructs a SHA-256-bound frozen fitting
artifact's distance bounds and per-coordinate separation margins. Its midpoint
and shared-query calculations are explicitly post hoc explanatory checks, never
replacement predictions, calibrated thresholds or held-out validation. It opens
only the supplied fitting artifact and writes an exclusive separate output directory.
Frozen historical scripts and private study assignments remain in ignored `local/`.

`check_resource_inspector.py --producer ROOT` exercises source inspector replay
and resource/raw-byte tamper rejection with synthetic producer fixtures. It runs
no acquisition and requires an explicitly selected producer checkout.
