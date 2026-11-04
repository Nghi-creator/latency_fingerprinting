# Fixture-study protocol declarations

`evaluation.fixture_protocol` provides a metadata-only planning/checking interface
for the separate fixture-condition experiment. It never opens feature artifacts,
creates native plans, authenticates review, confirms realized sessions or authorizes
collection. Existing N6/N7/N11 models and defaults remain unchanged.

`create_fixture_protocol_draft(...)` takes proposed blocks, correlation edges,
excluded case IDs and source/image hashes. It always creates a **pending** review.
A block declares its role (`training` or `evaluation`), host/session aliases,
complete three-condition order and one fresh native acquisition ID per condition.
All planned IDs must follow the native fixture namespace and be globally unique;
previously inspected/excluded IDs cannot be assigned again.

`inspect_fixture_protocol(plan)` checks the complete closed declaration, pins the
fixture method and common witness protocol, reconstructs correlation components,
and reports pending/rejected reviews or insufficient support. Shared `(host_id,
session_id)` and explicit correlation edges join blocks transitively. A component
cannot cross roles or count as multiple independent training blocks. Correlated
planned blocks require merging/redesign before allocation, not dropping data or
renaming a session. Host/session aliases are declarations, not physical evidence.

A complete declaration needs 6–32 distinct training components and 1–32 evaluation
components. These are software/arithmetic bounds, not power, accuracy or collection
approval. Arm-order counts are reported separately. The descriptive pilot protocol
has no empirical-acceptance threshold: it reports condition/block correct, error,
abstained and unavailable counts. Execution rules retain failed prefixes/unstarted
suffixes without retries and keep evaluation unstarted if calibration is unavailable.

The protocol ID hashes the complete proposal excluding `protocol_id`, `content_hash`
and `review`. Review binds that exact protocol ID. The content hash excludes only
`protocol_id` and `content_hash`, so review revisions change the content hash while
the review subject stays stable. Wrong/stale subjects fail. Confirmation/rejection
requires a reviewer alias and evidence hash; neither is authenticated by this API.
Changing the proposed source, assignments, counts or order requires a new subject
and a new review, not copying an old confirmation onto changed content.

`fixture_protocol_training_blocks(plan)` selects only training IDs from complete
reviewed declarations. It does not inspect or use evaluation feature values.
Pending, rejected, correlated or otherwise unavailable plans cannot be selected.
The numerical experiment still revalidates original responses/bindings separately.
Realized acquisition/session/correlation evidence must be linked and checked before
any study outcome is interpreted; this planning interface cannot substitute for it.

All reports retain `acquisition_authority: false`, `empirical_acceptance: false`,
`diagnostic_label: null` and zero accepted diagnostic groups. A state of
`reviewed_protocol_declarations_complete` means only internal declaration completeness,
not authenticated approval, physical independence, broad diagnosis or N11 acceptance.
