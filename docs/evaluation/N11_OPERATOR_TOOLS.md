# N11 operator tools

The [separate within-session experiment](N11_WITHIN_SESSION.md) has its own SDK
method/protocol and producer runner. It does not relax the independent-session API.

Reusable cross-repository processing and custody commands live in `experiments/`.
Native plan allocation and single-session orchestration live in the producer's
`engine/runtime/scripts/research/n11/studySession.mjs`. Raw captures, frozen
assignments, machine paths, run receipts and personal plans remain in ignored
`local/`. Frozen scripts are historical evidence; do not replace them retroactively
with newer utilities.

## Verify exported condition evidence

Run from the core checkout with its environment active:

```sh
python experiments/verify_native_exports.py /path/to/condition-case \
  --producer /path/to/Pixelated-Studio-Edition \
  --policy docs/analysis/N3_FEATURE_POLICY_SPEC.json
```

The case must contain the native plan, source snapshot, acquisition, control
receipt, and degraded/relief/recovery phase bundles and contexts. By default it
must also contain derived windows, observation and response. CLI replay uses
temporary outputs and leaves existing artifacts untouched. The producer checkout
is explicitly trusted executable code: its condition inspector is replayed with
Node.js. Each originally declared source file must still match that checkout.
Additional checkout files do not authenticate the original dependency closure.

For a newly acquired condition case, add `--write-derived` to create missing phase
windows, observation and analytical response after validation. Derivation supports
the fixed condition-plan v1 recipe (30/24/30 FPS, five-second action). Existing
derived files are checked, never replaced. A failure retains any partial outputs;
it does not authorize reacquisition. The JSON report goes to stdout and reports
eligible features without fitting a classifier or asserting diagnosis acceptance.

## Archive selected evidence

Choose inputs explicitly; this tool does not decide what may be shared:

```sh
python experiments/archive_evidence.py /backup/new-run.tar.gz \
  --include run=/path/to/private/run \
  --include plans=/path/to/private/plans \
  --prior /backup/previous-run.tar.gz --prior-sha256 EXPECTED_HEX_SHA256
python experiments/archive_evidence.py /backup/new-run.tar.gz --verify
```

Archive names must be relative paths without traversal. Symlinks, duplicate names,
an archive inside an included directory, and an existing output archive are
rejected. New archives use mode 0600. Every member is checked against the embedded
manifest without extraction. On failure the archive is retained for inspection;
no successful receipt is emitted. A successful stdout receipt establishes a
verified local copy, not remote backup or authenticity of the original evidence.

## Frozen session orchestration

The producer tool takes `allocate CONFIG.json` or `run CONFIG.json`; its adjacent
operator guide describes the configuration. Allocation prepares plans and freezes
their hashes, source manifest, protocol, verification command, dependency files
and orchestrator hash. It validates protocol metadata through the core SDK.
Running selects exactly one training block, checks declared session context and
pins, then acquires and invokes the frozen verification command sequentially.
Evaluation collection requires a separate calibrated workflow.

A verification command suitable for new condition cases is this argument array,
with the case directory appended by the orchestrator:

```json
[
  "/absolute/core/.venv/bin/python",
  "/absolute/core/experiments/verify_native_exports.py",
  "--producer", "/absolute/producer",
  "--policy", "/absolute/core/docs/analysis/N3_FEATURE_POLICY_SPEC.json",
  "--write-derived"
]
```

Pin the verifier, policy and relevant core dependency files in the allocation's
`dependencyFiles`. A command exiting successfully is recorded as a command-level
check; its configured semantics determine what was verified. It is not an
independence or scientific-acceptance declaration.

Session context is an operator declaration, not evidence automatically proving
independence. These tools do not resolve an undefined session-boundary rule or
create distinct sessions from container restarts. Known cross-session correlations
require regrouping the protocol before collection. Source/tool changes require
new prospective reviewed pins; never rewrite historical allocations to bypass
their source guards. These commands themselves collect no study data unless the
explicit producer `run` operation is invoked.

## Durable bounded execution

Fitting and prediction JSON from the Python processor must be stored as its exact
output bytes. JavaScript parse/stringify changes numbers such as `6.0` to `6` and
can invalidate embedded response identities even when numeric equality holds.
Keep frozen originals unchanged. Any recovery from authoritative case files must
be a separately named derived artifact with input hashes and reproduced results.

Use the checkout's POSIX helper for a reviewed run that must outlive its launching
terminal or tool session:

```sh
python experiments/run_study_job.py start \
  --job-directory /absolute/run/job --cwd /absolute/core \
  --timeout-seconds 3600 -- \
  /absolute/node /absolute/producer/engine/runtime/scripts/research/n11/withinSessionStudy.mjs \
  run /absolute/run/run-config.json
python experiments/run_study_job.py status /absolute/run/job
python experiments/run_study_job.py stop /absolute/run/job
```

The job directory must not exist. The explicitly supplied command is trusted
operator input, executed as an argument vector with no shell. The launcher exits
after starting a separate-session supervisor; its command also has an independent
process session and detached I/O. The manifest pins supervisor source, command,
working directory, aggregate deadline and a fresh job token. Heartbeats, command
output and terminal status remain in that private directory. No recurring task,
automatic restart, study resume or acquisition retry is created. Pin the helper
in a future allocation's processing dependencies before collection.

The launcher passes the exact manifest hash to the supervisor. Changed commands
are refused before execution; later manifest changes stop the owned command, and
status/stop operations reject changed metadata. They never execute replacement
arguments from a modified manifest.

The whole-job deadline defaults to one hour and is limited to two hours; it does
not extend any per-case native, action, freshness or verification deadline. Stop
requests are job-token-bound files, not signals sent to PIDs loaded from a file.
The supervisor terminates only its own active command process group, escalating
after ten seconds if necessary. Check the acquisition's resource cleanup evidence
separately after cancellation or a deadline.

A zero command exit means process completion, not study acceptance: an unavailable
calibration may also end normally. Inspect the producer's `session-result.json`
and calibration report. A missing/stale heartbeat is unconfirmed supervision,
never evidence that acquisition completed or permission to retry. Detachment
survives the caller exiting; it does not guarantee survival of host failure or a
forced supervisor kill. Missing terminal acquisition receipts remain uncertain
attempts and the study's no-retry/failure rules still apply.
