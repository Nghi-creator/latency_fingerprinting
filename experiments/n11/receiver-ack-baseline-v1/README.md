# Interim N11 fixture results: receiver-acknowledged baseline

**Completed 22 November 2026.** The contained Frozen-Bubble/Linux fixture completed
36 acquisitions: 18 for calibration, then 18 held out for evaluation. The frozen
model returned **15 correct predictions, 3 abstentions and 0 incorrect predictions**.
This is a completed same-session fixture study. Broader N11 acceptance remains open.

| Declared fixture condition | Correct | Abstain | Incorrect | Held out |
| --- | ---: | ---: | ---: | ---: |
| No injected fault | 3 | 3 | 0 | 6 |
| Owned identity delay | 6 | 0 | 0 | 6 |
| Owned CPU pressure | 6 | 0 | 0 | 6 |
| **Total** | **15** | **3** | **0** | **18** |

Prediction coverage was 15/18 (83.3%). The three abstentions remain in the planned
denominator. Two no-fault cases exceeded their calibrated radius; both complete
distance intervals were outside it. A third lacked an eligible encoded response
because its identity prefix could not be reconciled. No query was replaced, and
thresholds were not adjusted using evaluation outcomes.

## Design and recorded verification

Six complete three-condition blocks supplied calibration, covering all six
condition orders. All six leave-one-block-out folds (18 certificates) passed.
The fitting bytes were frozen before any query acquisition. Six later blocks in
reverse order supplied the held-out cases. Acquisition or source-verification
failure would stop the remaining suffix without retries; failed calibration would
leave every query unstarted. There were no acquisition failures or unstarted cases.

The recorded private replay reproduced the fit and all 18 original prediction
files byte for byte. It also checked 108 phase exports, 36 restorations and 3,952
forwarded receiver reports with no rejection. An immediate post-collection Docker
inspection showed no running containers. A later inspection could not reach the
stopped daemon; it does not extend the earlier cleanup observation.

These are three **owned fixture conditions**, not independently established fault
causes. All observations came from one correlated host session; no independent
support groups are established. This does not demonstrate later-session transfer,
physical capture latency, mixed/changing faults, general diagnostic accuracy or
probe utility. The owned identity delay is not a capture-latency measurement.

## Files and public verification

- [protocol.json](protocol.json): sanitized block allocation, method/source identity and stopping rules.
- [calibration.json](calibration.json): fitting identity and reported fold/certificate outcomes.
- [outcomes.json](outcomes.json): all 18 query decisions, reasons and hashes of their original private files.
- [verification.json](verification.json): sanitized private replay and custody summary.
- [provenance.json](provenance.json): recorded revisions, source/fit identities and redaction boundaries.
- [history.json](history.json): directly relevant earlier results, including incomplete and negative outcomes.
- [checksums.json](checksums.json): SHA-256 inventory of the published files.

From the repository root, use Python 3.11 or later; no dependencies or acquisition:

```sh
python experiments/n11/receiver-ack-baseline-v1/verify_results.py
```

An absolute script path also works from another directory; data paths resolve
relative to the script. This command checks published file integrity, allocation, denominators, fold
coverage, query membership and outcome tallies. **It does not replay private raw
telemetry, refit calibration, authenticate scientific labels, or independently
verify the reported native checks.** Original file hashes identify private
artifacts; sanitized projections cannot reproduce those hashes. The private raw
archive is not part of this bundle. Checksums detect inconsistency, not authorship.

## Earlier outcomes stay visible

| Earlier cohort | Verified / failed / unstarted acquisitions | Query outcome | Scope |
| --- | --- | --- | --- |
| Original event-span V6 | 36 / 0 / 0 | 18 correct | Earlier same-session source |
| V6 later-session transfer | 6 / 1 / 11 | 3 correct, 3 abstain | Incomplete transfer; admission rejection and unknown pacing cleanup |
| Admission-repaired baseline | 24 / 1 / 11 | 6 correct | Stopped on receiver delivery/unbind timeout |

These source versions and sessions are separate. Do not pool them into one
accuracy or availability estimate. This table covers the direct predecessors,
not the full historical experiment registry. Earlier failed cohorts and unstarted
suffixes remain retained privately. Controlled admission and delivery repairs do
not establish the initiating cause of every earlier failure.

The recorded software/source identities predate later folder organization.
Use the recorded revision and source manifest for historical reconstruction; a
current checkout is not automatically the original qualified source.
