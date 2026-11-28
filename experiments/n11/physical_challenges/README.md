# Physical challenge replay

Run from the core repository after installing its Python dependencies and the
producer's Node dependencies:

```sh
.venv/bin/python -m experiments.n11.physical_challenges.qualify \
  --case-directory "$CASE_DIRECTORY" --producer "$PRODUCER_REPOSITORY" \
  --output "$NEW_REPORT_PATH"
```

This reads the original acquisition, plan, raw export and exclusion files. It
replays custody, commands/references, delivery and measurement windows, verifies
both frozen and current producer source files, and invokes the actual producer
media-v2 inspector on temporary copies of the same original bytes. The producer
also recomputes its complete source inventory and native software identity before
and after media inspection. Sources and originals are checked again afterward.
Saved inspection reports are not accepted as replay results.

A case containing `failure.json` cannot be promoted by successful component
checks. CLI failures produce a new failure report and a nonzero exit status;
existing reports are never overwritten. No browser, container, pressure helper,
acquisition, calibration or prediction is launched.

`source_components_consistent` describes internal evidence consistency. Check the
separate projection state: constant variants may have descriptive phase rates,
valid insufficient measurements remain unavailable, and changing variants are
rejected from stable-pair projection. All reports retain false native
qualification, dose, N2, scoring and empirical authority. A new matched-source
calibration and prospective protocol are required for any later numerical study.

For an explicitly invented cross-repository software check:

```sh
.venv/bin/python -m experiments.n11.physical_challenges.check_qualification \
  --producer "$PRODUCER_REPOSITORY" --output-directory "$NEW_FIXTURE_DIRECTORY"
```

It uses producer test doubles for clocks/processes and invented telemetry. It
creates six synthetic cases and frozen source copies, then runs every replay
gate. Its identifiers are software vectors, not allocated research acquisitions.
It makes no claim about physical dose or live media behavior. Keep this output
separate from native pilot and study evidence.
