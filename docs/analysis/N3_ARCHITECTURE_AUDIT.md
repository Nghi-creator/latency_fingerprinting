# Post-N3 architecture audit

**Reviewed locally:** 2026-10-08, including Step 7 fixture documentation
**Environment:** macOS, Python 3.13.13
**Verification:** [N3 software closeout](N3_SOFTWARE_CLOSEOUT.md)

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
