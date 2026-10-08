# N3 analytical fixtures and reproduction gates

**Release:** 1.0.0, 2026-10-08
**Inventory and full-file pins:** [Fixture README](../../fixtures/analytical-v2/README.md)

The separate `fixtures/analytical-v2` family contains 19 canonical JSON snapshots:
an approved policy, one observation, complete/insufficient/confounded responses,
six declared references and eight match outcomes. Every observation/fingerprint
remains synthetic, with no executed intervention or scientific calibration claim.
The observation intentionally reuses the exact N2 synthetic pair bytes; existing
N2 artifacts and pins remain unchanged.

Independent [numerical expectations](../../tests/analytical/fixture_expectations.py)
check 22 complete zero responses, primary gauge/rate units, a 16-feature response,
confounder invalidity, a -0.25 reference vector and all match decisions. Expected
residuals, weighted squares, distance, strength, margin and conflict contribution
are authored from the field contract rather than copied from snapshots.

The matched case has distance 0.25 and strength 0.8. Unknown cases cover invalid
response, empty repository, no compatible reference, insufficient shared features,
weak match, ambiguous margin and conflicting evidence. Stored results reproduce
through `match-v2` and repository-backed verification; public response and reference
creation also reproduce their snapshots exactly.

```bash
.venv/bin/python -m tests.analytical.check_reproduction
```

This test-support module is read-only. It verifies independent expectations,
reconstructed canonical bytes, unexpected/missing/changed JSON files and separately
retained SHA-256 pins. Symlinked snapshot files fail drift checks. Failure leaves
stdout empty and returns an error without a traceback. It never creates missing
directories or refreshes fixtures/pins to make CI pass. Both Python 3.13 and 3.11
CI jobs run it; actual hosted/minimum-version execution remains separately pending.

The full-file policy pin differs from its self-excluding release contentHash.
Changing policy meanings requires a reviewed new policy release. Snapshot updates
require review of independent expectations, intended bytes and pins together.
Reference directories contain only fingerprint roots; loading the whole fixture
tree as a reference repository correctly fails on mixed roots.

40 new closeout cases cover all snapshots, public/repository-backed reproduction,
read-only drift/failure behavior, synthetic hygiene, CI gate presence and the final
repository ancestor replacement regression. See [closeout](../archive/analysis/N3_SOFTWARE_CLOSEOUT.md)
and [architecture audit](../archive/analysis/N3_ARCHITECTURE_AUDIT.md) for final verification and scope.
