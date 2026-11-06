# Prospective combined-resource study protocol

`evaluation.combined_study_protocol` defines
`n11-combined-resource-study-protocol-v1`. It pins the separate combined interval
method and explicit resource acquisition source. It does not accept an original
within-session protocol under the new identity, or authorize collection by itself.

`create_combined_study_protocol(...)` creates pending-review declarations for six
fitting and six later query blocks, at most 36 acquisitions. All twelve blocks
must declare the same host and actual session: one correlated component, zero
independent support groups. Counts are a proposed bounded design, not evidence of
approval. Each fitting block contains all three conditions; fitting uses every
condition permutation once, and query order reverses that sequence.

Every acquisition ID is unique, begins `n11-raw-cs-`, and differs from all declared
historical exclusions. Up to 1024 sorted unique exclusions are supported. The
protocol pins source/image hashes and the processor, verifier, runner and durable
supervisor file hashes. Content and review-subject identities cover the exact
proposal; changing method, tools, order, counts, scope or exclusions requires a
new content review. Pending/rejected protocols remain unavailable. Confirmed
review metadata is a caller declaration, not authenticated authorization.

`inspect_combined_study_protocol(plan)` checks metadata and reports no acquisition
authority or empirical acceptance in every state. A runner must separately check
the actual authorized scope and actual source/tool/dependency pins.

## Processor and runner

`experiments/combined_resource_study.py` has three passive operations:

- `inspect PROTOCOL`: validate declarations without allocation or acquisition;
- `fit ALLOCATION`: open only the first six fitting blocks, verify plan/source/
  image/witness/verifier receipts and raw hashes, construct source-bound condition
  declarations, and rebuild the combined calibration;
- `score --training FIT --case DIRECTORY --block ID --session ID`: rebuild the
  original calibration, then open only the query's raw acquisition and auxiliary
  resource measurements. Query truth-bearing plan/receipt files are not opened
  by scoring. Native verification precedes this operation separately.

Fitting checks the processor hash against the reviewed protocol. Missing query
paths cannot affect fitting. Output JSON contains opaque source text and exact
rational integers; store Python stdout bytes unchanged.

The producer `scripts/research/n11/combinedResourceStudy.mjs` provides separate
`allocate` and `run` commands accepting explicit config JSON. Allocation checks
all four tool hashes and the dependency closure, validates protocol review, and
exclusively freezes all 36 resource plans before any source run. Pending drafts
cannot allocate. The ordinary study runner still uses its original protocol.

Run requires the frozen allocation/protocol/runner, source/dependency hashes and
one documented actual session context. It refuses existing case outputs or
attempt markers. Every acquired case undergoes the shared native export verifier
before fitting or scoring. After 18 fitting acquisitions the processor fits once;
its original stdout bytes and SHA-256 freeze are retained before any query.
Unavailable calibration leaves every query unstarted. Available calibration
permits later queries only, scoring without truth input and saving prediction
bytes before condition truth joins the descriptive run ledger.

Exact rational prediction coordinates remain in their byte-preserved artifact.
The JavaScript ledger retains only state, predicted condition, reason codes and
artifact hash, avoiding precision loss from reserializing rational numbers.
Training-fit JSON is also preserved byte for byte.

A source, verification, scoring, dependency or context failure stops the entire
remaining suffix. There is no retry, replacement or resume. Fit-stage failure
leaves all queries unstarted with no failed acquisition ID; an attempted source
failure records that case separately. Successful process exit is not empirical
acceptance. Use the bounded durable supervisor for long native runs; it neither
retries studies nor infers acceptance from exit status.

## Required prospective review

Before collection, review the exact pending proposal, exclusions, actual machine/
session scope, source/image/tool pins, dependency closure, protocol counts,
no-retry/stop rules and finite execution budget. Source engineering cases stay
excluded from fitting/query data. Synthetic fixtures and passive compatibility
replays are not independent sessions or prospective condition-recognition data.
Original failed cohorts/negative results stay unchanged. Broad N11, physical
latency, N9, manual/hosted/perceptual/activation and benefit gates remain separate.
