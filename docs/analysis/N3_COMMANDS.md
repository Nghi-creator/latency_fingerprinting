# N3 additive offline commands

**Delivered:** Step 6, 2026-10-08
**Contract:** [Analytical field contract](N3_ANALYTICAL_CONTRACT.md)
**APIs:** [Responses](N3_RESPONSE_DERIVATION.md), [fingerprints](N3_FINGERPRINTS.md),
[matching](N3_MATCHING.md)

All commands require an explicit local approved `FeaturePolicyV1` file. The policy
must equal the embedded policy for fingerprint creation and matching. Unknown or
altered releases fail, including edits accompanied by a recomputed hash. No v1
conversion, policy URL resolution or implicit fallback occurs.

## Build an analytical response

```bash
.venv/bin/python -m latency_fingerprinting build-response-v2 \
  --observation observation.json \
  --policy docs/analysis/N3_FEATURE_POLICY_SPEC.json > response.json
```

The input is an `observation-v2` pair, not an individual window or P0 response.
Output is the canonical `analytical-response-v2` record from pure derivation.
Incomplete or confounded evidence retains exclusions/invalidity and is a successful
analytical output. Malformed N2 pairs fail validation.

## Create a declared reference

```bash
.venv/bin/python -m latency_fingerprinting build-fingerprint-v2 \
  --response response.json \
  --policy docs/analysis/N3_FEATURE_POLICY_SPEC.json \
  --bottleneck-label network_pressure > references-v2/fingerprint.json
```

Supply an existing output directory if using shell redirection. Creation itself
writes only stdout. The required label is a sanitized declared identifier.
Default `--validation-status software_checked` requires at least 17/22 eligible
features. Explicit `unreviewed` or `rejected` permits lesser valid audit evidence;
invalid/confounded responses cannot become fingerprints under any status. The
status does not establish experimental truth or promote synthetic provenance.

## Match separate v2 evidence

```bash
.venv/bin/python -m latency_fingerprinting match-v2 \
  --response response.json \
  --policy docs/analysis/N3_FEATURE_POLICY_SPEC.json \
  --fingerprints references-v2 > match-result.json
```

Every repository JSON file is validated before decisions. Empty directories produce
`no_fingerprints`; malformed/mixed roots, duplicate IDs, unsafe links and resource
violations fail the command. There is no v1 `--allow-rejected-fingerprints` skip
option. Valid records with audit status remain in references and are rejected for
candidate compatibility. Conservative unknown results are successful JSON outputs,
with no accepted label and retained evidence.

## Read-only, bounded public boundary

Direct inputs use descriptor-based no-follow traversal, bounded regular-file reads,
strict UTF-8/JSON parsing and full model validation. Links in files/ancestors,
non-regular files, duplicate keys, non-finite values, JSON depth >128 and input
sizes >10 MiB fail. Repository limits remain 128 JSON files, 4,096 entries and depth
16, with the same per-file JSON bounds.

The complete validated canonical JSON is rendered and checked against a 10 MiB
UTF-8 output bound, including the final newline, before stdout receives any bytes.
Output equals the corresponding pure API and repeats identically for equal inputs.
Commands mutate no inputs, create no directories and read no remote policies.
Shell redirection controls output files and can create an empty file on failure.

Success, including a conservative unknown or invalid analytical response, exits 0.
Input/calculation/output failures exit 1, leave stdout empty and print only
`error: <command>: invalid_input_or_result`. Paths, malformed contents and Pydantic
input echoes are excluded. Argument/usage errors retain argparse's exit 2 behavior.
Existing v1 commands, generic root validation, ingestion and schema exports retain
their behavior; `match` remains the P0 matcher.

52 public command tests cover CLI/API byte parity, end-to-end module execution,
explicit statuses/arguments, wrong roots, malformed/altered policies, deterministic
privacy-limited failures, unsafe inputs/repositories, input growth, exact output
bounds, read-only inputs and v1 rejection. [Progress](../archive/analysis/N3_IMPLEMENTATION_PROGRESS.md)
records current local verification. Actual Python 3.11/hosted execution remains
pending. [Step 7 snapshots/pins](N3_ANALYTICAL_FIXTURES.md) and
[software closeout](../archive/analysis/N3_SOFTWARE_CLOSEOUT.md) are complete locally.
