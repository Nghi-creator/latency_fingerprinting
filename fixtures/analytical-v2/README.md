# N3 analytical software fixtures

**Release:** 1.0.0, 2026-10-08
**Provenance:** Explicitly synthetic software evidence

These 19 JSON snapshots cover approved policy, one synthetic observation, three
analytical responses, six declared reference fingerprints and eight match outcomes.
They test software contracts and arithmetic, not measured latency relief, diagnosis
accuracy, causal labels or calibrated thresholds. No probe was executed. Reference
labels remain synthetic declarations; software_checked means numerical/contract
consistency only.

The complete query has 22 zero responses; the matched reference has 22 values
of -0.25. Their residuals are 0.25 with unit weights, squared residuals 0.0625,
distance 0.25 and strength 0.8, which passes the strength boundary. The insufficient
query has 16 eligible features, and the confounded response excludes every feature.
Weak, ambiguous and conflicting references exercise the other numerical decisions.
Empty/unreviewed repositories exercise the remaining conservative outcomes.

[Independent expectations](../../tests/analytical/fixture_expectations.py) retain
these numbers separately from model/matcher outputs. [Reproduction](../../tests/analytical/check_reproduction.py)
checks them, canonical exact bytes and the pins below without regenerating files.
Both configured Python CI jobs run this gate. The raw observation bytes deliberately
reproduce the already pinned N2 synthetic pair; their analytical interpretation is
separate. Snapshot duplication retains the full embedded audit evidence required
by the contracts.

```bash
.venv/bin/python -m tests.analytical.check_reproduction
.venv/bin/python -m latency_fingerprinting match-v2 \
  --response fixtures/analytical-v2/responses/complete.json \
  --policy fixtures/analytical-v2/policy.json \
  --fingerprints fixtures/analytical-v2/references/matched
```

Use individual reference directories; the entire fixture tree contains multiple
root types and is intentionally not a valid fingerprint repository. Empty repository
cases use an empty temporary directory in tests. README files remain separate from
JSON snapshot inventories. [Fixture guide](../../docs/analysis/N3_ANALYTICAL_FIXTURES.md)
and [software closeout](../../docs/analysis/N3_SOFTWARE_CLOSEOUT.md) record the limits
and verification boundary.

SHA-256 hashes below cover full canonical file bytes. The policy's self-excluding
contentHash has a different purpose and remains
`sha256:96457b318cc714f3d9d0d63a35b12548f6e030b10057b2c8e5a3a77e352fe1af`.

| Snapshot | SHA-256 |
| --- | --- |
| [inputs/observation.json](inputs/observation.json) | `d6b96c18e0104fcd62ea2525b5637c6aadf7a033ac30d3b4e918be3ff8088954` |
| [matches/ambiguous_margin.json](matches/ambiguous_margin.json) | `a2a354f96b53edbe9129cf06ee65dddec911eb34b57457cff5acbb08cdcd9cd2` |
| [matches/conflicting_evidence.json](matches/conflicting_evidence.json) | `951e4ee9ae41c08e6d8c68d2bb813f204c9454fc6894dec2514f254113599163` |
| [matches/insufficient_features.json](matches/insufficient_features.json) | `51d92782bbee84b5e12b7e0976c4eca8d494630a482f03f9d709213836c8a4f8` |
| [matches/invalid_response.json](matches/invalid_response.json) | `9d0a1ed8d71cfacc1101c6a99c5adf5ade3617b8593a6f29bff2d3fb647b9752` |
| [matches/matched.json](matches/matched.json) | `df0475871d1f8c7b38613b3e2e7d42e82967d1f16ea91c3704fe82db4ba501bf` |
| [matches/no_compatible_fingerprints.json](matches/no_compatible_fingerprints.json) | `9d28b25d2d8e9ccaf7e6d1dab06f08bc8c35813afc97f0bc6a298fb95fa9c2a8` |
| [matches/no_fingerprints.json](matches/no_fingerprints.json) | `cf09d9322387ef747c55fb1faf32b7292a867f93c1ffe363e15a0ad52e93ecda` |
| [matches/weak_match.json](matches/weak_match.json) | `72df923fb7ffb1ae089d17ce79ab07d5a42a7e70ce10e26b1fefdf3ae96fcd8b` |
| [policy.json](policy.json) | `e3f54c5eb4b8fd4d406a9b201584a28db97c15b04478ae9226f854bb580bad7e` |
| [references/ambiguous/fingerprint-1.json](references/ambiguous/fingerprint-1.json) | `8bdffc0395a859501bcb7df5b9210754a69b93b5cfa18f43db46be97fe690029` |
| [references/ambiguous/fingerprint-2.json](references/ambiguous/fingerprint-2.json) | `842a0fe80ca5971c9922a06b245754c1fa85a066795bc46a8ed9f11e3a7361d8` |
| [references/conflicting/fingerprint.json](references/conflicting/fingerprint.json) | `12b8ee3344e559118c3b0a7e2994a0aef46f3cc6c3a3cc07461005c10a97e9be` |
| [references/matched/fingerprint.json](references/matched/fingerprint.json) | `c1bfbd794731177e7f3abd972a9d7856de2f86ca8a2a7ab7db4d77b37f4c572a` |
| [references/unreviewed/fingerprint.json](references/unreviewed/fingerprint.json) | `1ca0fe53b37d7d4afc1f0ffc09f27ba11da0e94657b14e7e6774dcb10921c66a` |
| [references/weak/fingerprint.json](references/weak/fingerprint.json) | `23394bd3f6c7b29a434d9c352f6ac9a8066a51e3a92db188a87c73bc2fe49542` |
| [responses/complete.json](responses/complete.json) | `4a3a636bc7a7c5ee0ac729be40035460fbdd477e41e22cd3965b91a19bc39427` |
| [responses/confounded.json](responses/confounded.json) | `801a6199289e6ae739107b05befb8752abad222c823056fafa966a2cdd8c3c67` |
| [responses/insufficient.json](responses/insufficient.json) | `07b8f7532fcddb251330a7a667b08e7dc13ba89a8cf2bb9b7c5ec03a289af208` |
