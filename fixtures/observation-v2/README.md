# N2 software fixtures

These three canonical records verify software contracts and adoption. They are
not experiment or diagnosis evidence. Adopted snapshots retain the importer's
required `controlled_real` provenance from existing sanitized test bundles; the
pair is explicitly synthetic with a simulated, unexecuted intervention.

See the [fixture guide](../../docs/measurement/OBSERVATION_V2_FIXTURES.md) for
source inputs, independent arithmetic expectations, SHA-256 pins and update policy.
Reproduce read-only with:

```bash
.venv/bin/python -m tests.observation_v2.check_reproduction
```
