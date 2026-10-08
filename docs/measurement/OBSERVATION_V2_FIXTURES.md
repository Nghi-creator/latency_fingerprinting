# N2 observation fixtures and reproduction

Three [checked-in records](../../fixtures/observation-v2/README.md) lock canonical
JSON for the additive v2 contracts. These are software fixtures, not experimental
evidence, a new capture or a diagnosis benchmark.

| Fixture | Purpose and provenance |
| --- | --- |
| [adopted-browser-v1.json](../../fixtures/observation-v2/adopted-browser-v1.json) | Existing sanitized v1 bundle through the N2 importer; absent engine/encoder summaries and source-unavailable stage reasons |
| [adopted-engine-v2.json](../../fixtures/observation-v2/adopted-engine-v2.json) | Existing sanitized v2 bundle through the N2 importer; registry/support/interval evidence and four unavailable stages |
| [synthetic-pair.json](../../fixtures/observation-v2/synthetic-pair.json) | Artificial compatible degraded/relief records with synthetic provenance, simulated intervention and no executed action |

Adopted snapshots preserve `controlled_real` because the Pixelated importer
requires real capture provenance and the existing test inputs exercise that path.
That field does not turn these test inputs into controlled experiment evidence.
The synthetic pair uses `synthetic_series`, synthetic elapsed clocks and
`not_executed`; its identical artificial series do not demonstrate relief efficacy.
Its stage tuple is empty, which remains valid for callers outside the adopter.
Its artifact hash identifies canonical in-memory series input bytes from
`synthetic_source_bytes()` in the test builder, rather than a placeholder. Both
windows use the same artificial series and therefore the same source hash.

## Reproduction and independent expectations

[Fixture reconstruction](../../tests/observation_v2/fixture_cases.py) uses fixed
raw bundles/context and the existing synthetic model input builder. It calls the
production importer for adopted snapshots, without P0 conversion or ambient IDs.
The [CI check](../../tests/observation_v2/check_reproduction.py) reconstructs the
records once, compares exact
checked-in bytes, then fixed SHA-256 pins. Missing, changed or unexpected JSON and
pin drift fail with an error exit code, empty stdout and no traceback. Neither
checking command writes files or creates directories.

```bash
.venv/bin/python -m tests.observation_v2.check_reproduction
```

| File | SHA-256 |
| --- | --- |
| adopted-browser-v1.json | `50fd2ff8cb013a1d52564b5a21bbe210a25e810e0e55e036da5ca25c15911b81` |
| adopted-engine-v2.json | `f92e1fe241200609a8133be233053a79c7bbb3dca179ffd6ab3e1bbba09ab179` |
| synthetic-pair.json | `d6b96c18e0104fcd62ea2525b5637c6aadf7a033ac30d3b4e918be3ff8088954` |

These pins lock software serialization and adoption behavior. They do not by
themselves prove numerical correctness. [Fixture tests](../../tests/observation_v2/test_fixtures.py)
also retain independently supplied expectations: two 5,000 ms intervals each
increase frames decoded by 300, giving 60 frames/s, 600 frames total and complete
10,000 ms coverage. The unsupported proxy and absent engine values remain null.
Other counter/reset/gap cases retain the independently authored
[N1 arithmetic fixtures](ARITHMETIC_FIXTURES.md).

Both v2 roots validate through Python models, generated JSON Schema and the public
CLI with exact canonical bytes. Incompatible registry references are rejected.
Directory/TAR equality and unchanged source bytes remain covered by the
[adoption tests](../../tests/pixelated/test_observation_v2_adoption.py).
Public [N2 resource boundary cases](../../tests/observation_v2/test_cli_boundaries.py)
cover bytes/depth, total bundle size, TAR size/count/paths, CSV headers and row caps.

## Updating fixtures

Changes require deliberate review of record differences and the fixed pins.
`rendered_fixture_files()` returns candidate bytes in memory; use it to inspect
proposed records before replacing fixtures. No fixture generation command is part
of CI. Keep existing raw source fixtures unchanged and update N2 snapshots only
when the reviewed contract/adoption behavior warrants it.

Both Python 3.11 and 3.13 jobs run the reproduction command. Local final evidence
is **1,166 passing tests and 93.05% branch-inclusive coverage** on Python 3.13.13;
actual hosted/minimum-version execution remains pending. See the
[software closeout](../archive/measurement/N2_SOFTWARE_CLOSEOUT.md) and
[post-N2 audit](../archive/measurement/N2_ARCHITECTURE_AUDIT.md). The audit deliberately revised the
synthetic-pair pin after replacing its placeholder source hashes; adopted-record
pins remain unchanged.
