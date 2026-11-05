# N11 operator tools

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
