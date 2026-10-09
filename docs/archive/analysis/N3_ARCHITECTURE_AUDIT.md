# Post-N3 architecture audit

> Archived milestone record, retained with its original results and limitations.
> The [active N4 plan](../../plans/NEXT_IMPLEMENTATION_PLAN.md) now covers stage-level observability.

**Reviewed locally:** 2026-10-08, including the follow-up health check after Step 7
**Environment:** macOS, Python 3.13.13
**Original milestone verification:** [N3 software closeout](N3_SOFTWARE_CLOSEOUT.md)

The delivered architecture keeps P0 matching separate from immutable N2 observation
adoption and N3 analytical derivation. Approved policy content and registry meaning
are enforced at strict model boundaries. Response/fingerprint/match IDs are canonical
and deterministic; declared labels/provenance remain distinct from software checking.
Comparison reconstruction and full repository verification have explicit trust limits.

The final review found a root-opening race in the v2 repository: ancestor symlinks
were checked before a full-path open, permitting replacement between those actions.
The loader now pins every ancestor through no-follow directory descriptors. A
regression replaces an ancestor after the precheck and proves the outside directory
is not followed. Existing file-replacement, FIFO, byte/depth/count and fail-closed
checks remain in place. Direct CLI inputs already used descriptor traversal.

Production responsibilities remain in focused modules: policy release, response
construction, fingerprint creation, bounded repository loading, compatibility,
scoring, decisions and matching. New models range from 77 to 235 lines; the v2 CLI
is 110 lines, leaving the existing CLI focused on registration/legacy handlers.
No further package restructuring is justified by this slice. Full embedded evidence
makes the synthetic snapshots larger by design; those bytes audit reconstruction
and do not enter the per-frame runtime.

Tests retain independent numerical expectations as well as exact snapshots/pins.
Whole-tree checks include fixture READMEs, all ten schemas, privacy/resource gates,
public commands, fresh imports and P0/N1/N2 reproduction. Current documentation
points to completed N3 software and pending hosted verification. Older milestone
counts and original audit findings remain historical records.

Remaining boundaries are explicit: Python 3.11/hosted results are pending; policy
parameters are software-provisional; structural compatibility is not demonstrated
cross-node transfer; producer/label truth is not authenticated by hashes. Stage
instrumentation, synchronized timing, experiment harness work and held-out scientific
evaluation remain in the broader roadmap. This review confirms the local software
gates, without claiming every possible defect or scientific gap is eliminated.

## Follow-up health check

Starting checkout was clean at `cd84bbd8c0ee6d09cffbd8d28d0b64041167bc65`.
Review covered analytical arithmetic/reconstruction, immutable models, input
boundaries, shared adoption/aggregation, module sizes, current guides, schemas,
fixture pins and CI configuration. Two concrete logic gaps were reproduced:

| Finding | Consequence | Repair |
| --- | --- | --- |
| Squaring a nonzero residual, or dividing its positive squared sum by shared weight, can underflow to zero | Unequal vectors could report distance zero | Reject both unrepresentable stages through the common comparison calculation used by matching and stored-result validation |
| Shared bundle loading checked paths before opening them and did not reject ancestor links | Directory/TAR replacement could follow an outside target; replacement by a FIFO could block | Pin every ancestor and the bundle root, open members relative to the directory descriptor with no-follow/nonblocking flags, require regular files, and bound TAR bytes before decoding |

Seven analytical regressions cover residuals of `1e-200` and `2e-162`, API and
stored-result rejection, private CLI failure, and a small representable `1e-150`
residual that retains nonzero distance/evidence. Twelve shared-reader regressions
cover ancestor links, directory/TAR/member replacement, FIFO replacement, a pinned
directory after path replacement, TAR growth and invalid requested member names.
The existing file-growth regression now exercises descriptor reads rather than
the obsolete `Path.open` seam.

The shared reader repair applies to P0 ingestion, N1 extraction and N2 adoption;
valid aggregation, serialization and artifact identities remain unchanged.
Schemas, approved policy content, scientific thresholds and all fixture pins are
preserved. No snapshots were refreshed. The reader remains a focused module;
larger registry/measurement/envelope modules retain cohesive responsibilities,
and no additional package restructuring is needed for these repairs. Retained
snapshot evidence remains deliberate duplication for audit/reproduction.

Current guides now document underflow and descriptor-based bundle reads. The stale
measurement package description is corrected; historical N2 findings and milestone
counts are explicitly distinguished from the delivered N3 path.

Final local Python 3.13.13 verification: **1,539 tests pass; 93.58% branch-inclusive
coverage**, above the unchanged 85% floor. Ruff lint/format, dependency checks,
all ten schema exports, canonical registry, four fixture families and three pinned
reproduction modules pass. Five controlled P0 artifacts validate; run-001 seed and
exact run-002 match bytes reproduce. All local Markdown/image links and diff checks
pass. Legacy missing-bundle diagnostics remain preserved. The final coverage run
used the unchanged repaired source tree; only current documentation counts were
updated afterward.

TAR input is buffered within the existing 64 MiB input cap (plus one rejection
sentinel byte). Full-limit memory/scaling characterization remains unmeasured,
alongside the hosted/minimum-version and scientific boundaries listed above.
