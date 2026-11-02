# N11 software corpus v1

All telemetry, labels and reviews here are artificial. These cases provide no
independent acquisitions, authenticated labels, real fault qualification or
empirical acceptance. `software_only` remains the scope of every report.

- `planned-ledger`: five declared groups, three held out. One failed acquisition,
  one unstarted acquisition and one unknown retained case all count. Training and
  engineering groups do not increase the held-out denominator.
- `raw-passive`: five artificial independent baseline groups and one query run
  with two adjacent raw slices. The two slices share a source and clock, each
  contains one 300-frame/5-second interval, and no probe is proposed. This is one
  held-out group, with no diagnostic label.
- `unverified-diagnosis`: the existing N6 reviewed-role software example, retained
  as exact input bytes, exercises linked N7/N8. Missing original raw proof prevents
  outer diagnostic labels; both held-out groups remain unknown.
- `raw-diagnosis`: five artificial paired training groups and one validation pair
  reproduce every whole-bundle source. The linked evaluation is computed but stays
  unknown: the N7 profile lacks active feature support; the five identical N3
  references retain their zero-margin ambiguity. No threshold is weakened.
- `producer-window.tar`: output of Pixelated's actual v2 manifest composer and TAR
  writer using the sanitized artificial `tests/data/pixelated_bundle/valid-v2`
  content. It checks packaging interoperability, not acquisition or CSV sampling.
  The producer adds two privacy omissions; source content identity changes while
  numeric windows, support states and row identities remain equal.

`release.json` pins the exact file inventory and full-root snapshots. Its compact
expectations were authored from the ledger, source arithmetic and existing N6/N9
rules. Full report snapshots additionally lock serialization, result links and
embedded source identities; they are not an independent statistical oracle.
Raw archives and complete source roots are deliberately retained so replay never
needs a sibling checkout or regenerates its own inputs. JSON copies of prior N6
inputs are dependencies, not new acquisitions. TAR metadata has no evidentiary
meaning; the retained bytes are fixed.

Run `python -m tests.evaluation.check_reproduction`. The checker has no update or
bless mode. Negative tests mutate private copies to reject role leakage, missing
groups, duplicate exports, absent raw proofs and plausible rehashed false results.
Existing N6/N8/N9 frozen cases retain their own label, context, mixed/unseen,
staleness and whole-group exclusion expectations.
