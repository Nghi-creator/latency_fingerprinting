# Profile matching fixture release

[`fixtures/profile-matching-v1`](../../fixtures/profile-matching-v1) freezes
`n8-profile-matching-v1` software behavior under fixture release `1.0.0`.
The [release inventory](../../fixtures/profile-matching-v1/release.json) pins 76
operand files, 75 cases, the N6 and N7 fixture releases, the provisional policy
and the preimplementation design vectors. The checker pins the release itself.
Existing N6 datasets are referenced through their explicit pinned dependency;
no source capture is relabelled or copied into a positive matching example.

```sh
python -m tests.profile_matching.check_reproduction
python -m pytest tests/profile_matching
python -m tests.packaging.check_wheel
```

The checker verifies an exact flat inventory with bounded no-follow reads: at
most 96 members, 10 MiB per operand and 16 MiB total; the release file has a
separate 1 MiB cap. It verifies N6 and N7 dependency inventories/pins before
execution and again afterward. API and CLI results must equal complete frozen
canonical results, including all content IDs. Linked evidence also checks against
N6's independent inspection expectations and N7's independent build expectations.
Errors must keep their fixed private messages and preserve prior output. Success
prints one JSON receipt. There is no update/bless mode.

| Cases | Expected behavior |
| --- | --- |
| Policy and supported matches | Exact approved policy; two labels scored on the same evidence; five- and six-group statistics |
| Distance and margin boundaries | Distance 3 and margin 0.25 pass; excessive distance, ties and insufficient margin remain unknown |
| Signed zero and finite mean | Raw query negative zero is retained; averaging maximum finite contributions avoids a spurious running-sum overflow |
| Validation and final test | Label-blind decisions retain complete truth/group accounting in separate explicit modes |
| Whole-group refits | Ten five-group folds lose support and remain unknown; twelve six-group folds refit statistics and retain every outcome, including unknowns |
| Twelve linked synthetic datasets | Matching plus all three evaluation modes retain excluded responses, baselines, duplicates and global missing entries; none becomes a successful classification |
| Invalid linked inputs | Wrong source binding, split leakage, mismatched or forged snapshots, changed anchors, unapproved policy and absent query IDs fail privately |

Positive model results come from the independent Decimal/literal oracles frozen
before production N8 scoring and refitting. Linked expectations are independently
authored from pinned N6 metadata and exclusions, with no N8 scorer or evaluator
used to generate expected results. Their accuracy is zero when known truth has
only unknown predictions, and null with an empty known-truth denominator.

The installed-wheel check copies all three corpora to temporary directories and
runs every N8 case through the installed console entry point outside the checkout.
Both CI Python jobs run reproduction and installed-wheel verification.

**Provenance is `synthetic_and_model_only`.** Positive declarations have artificial
eligible metadata and no inspected physical acquisition behind them. Actual linked
synthetic evidence stays excluded. External reviews remain unauthenticated; this
release establishes software reproducibility, not real sample adequacy, diagnostic
accuracy, physical independence or trust promotion. No producer integration runs.

To revise this release, review changed operand bytes and independent expected
outcomes, version the fixture release as appropriate, and explicitly update operand
and release pins. Do not regenerate expectations from current production output
to make a failing check pass. The [design vectors](N8_DESIGN_VECTORS.json) continue
to cover arithmetic/selection extremes alongside the full runtime corpus.
