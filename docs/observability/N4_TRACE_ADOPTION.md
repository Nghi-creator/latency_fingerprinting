# N4 standalone trace export and adoption

**Meaning:** [Frozen v1 contract](N4_TRACE_CONTRACT.md).
**Collectors:** [Host](N4_HOST_INSTRUMENTATION.md), [browser](N4_BROWSER_INSTRUMENTATION.md).

Pixelated exports a standalone `pixelated_stage_trace` artifact containing exactly
`trace-manifest.json` and `trace-record.json`. It is independent of research bundle
v2. The record includes clock, capabilities, correlation, sampling and loss; no
summary, observation or matching result is supplied by this artifact.

## Producer export

The producer commit must identify the deployed build: a lowercase forty-hex Git
commit, not a tag, URL or inferred core version. Uncommitted local instrumentation
is software evidence and cannot establish the real producer acceptance gate.

Host camera settings add to the existing opt-in collection configuration:

| Environment setting | Meaning |
| --- | --- |
| `PIXELATED_STAGE_TRACE_OUTPUT` | Existing-parent local destination for gzip TAR; absent skips persistence |
| `PIXELATED_STAGE_TRACE_PRODUCER_VERSION` | Forty-hex deployed producer commit; required when output is configured |

Normal loop exit/SIGTERM cleanup closes peers and finishes the recording before
`camera_trace_export.py` snapshots, hashes and writes it. No snapshot/hash/file
work occurs inside frame callbacks. Output pins no-follow ancestor/file handling
and atomically replaces a regular destination with a private 0600 file. Invalid
configuration/write failure produces a fixed diagnostic, preserves the previous
artifact and does not escape shutdown. Empty recordings produce no artifact.
Disabled tracing writes nothing. SIGKILL/process failure cannot promise an export.
Both runtime Dockerfiles include the exporter; no container build was performed.

Browser builds add `VITE_N4_STAGE_TRACE_PRODUCER_VERSION` to the existing
`VITE_N4_STAGE_TRACE=1` configuration. The mounted player owns the lifecycle hook
and displays **Finish and export stage trace** only when tracing is enabled.
The control finishes collection, hashes canonical bytes, creates a gzip TAR and
uses the existing local file picker/download mechanism. Cancellation is reported
and permits re-export; collection has already stopped. Invalid commit or exporting
before any media lifetime does not terminate future collection. The filename is
fixed `pixelated-stage-trace.tar.gz`; no game/session identity enters it.
Browser SHA-256 and gzip support are required for export; failure reports a fixed
status. There is no automatic download, upload or change to research-v2 output.

The exported runtime artifacts declare producer_capture. Synthetic software cases
explicitly request synthetic provenance through the export APIs. Neither declared
provenance nor a hash establishes real capture, timing accuracy or measured overhead.

## Offline adoption

Run from the core repository with its installed Python environment:

```bash
.venv/bin/python -m latency_fingerprinting ingest-trace \
  --bundle /absolute/trace.tar.gz --output /absolute/trace-record.json
.venv/bin/python -m latency_fingerprinting validate /absolute/trace-record.json
```

A directory with exactly the two regular files is also accepted. Use actual paths;
no-follow handling rejects symlink ancestors/inputs/outputs. Parent output
directories must already exist. A successful ingest writes canonical UTF-8 JSON
with one trailing LF and no stdout. Failures return exit 1 with the fixed
`error: ingest-trace: invalid_input_or_output` diagnostic, without echoing paths,
TAR names, private supplied values or Pydantic inputs. Existing output is preserved
until complete validation and successful atomic replacement.

The Python API is `observability.bundle.ingest_trace_bundle(Path(...))`, returning
an immutable, revalidated `StageTraceRecord`. The manifest must contain exactly
schema_version=1 (strict integer), bundle_type=pixelated_stage_trace,
trace_schema_version=stage-trace-record-v1, lowercase SHA-256 and a strict safe
trace byte count. The actual bytes must match both declared length and hash,
and must equal the Python model's canonical rendering. Matching hashes do not
allow unknown/private fields, reordered serialization, wrong versions or invalid
clock/identity/loss evidence. Manifest whitespace/order may vary; the trace is
canonical. Duplicate JSON keys and excessive depth fail before model loading.

Only gzip TAR and uncompressed directories are supported. Plain TAR/ZIP, links,
FIFOs/devices/directories inside TAR, extra/duplicate members, path aliases,
absolute/traversal names, TAR extensions and hidden nonzero trailers are rejected.
Physical headers are checked before recursive TAR extension parsing. Each JSON
is limited to 10 MiB/depth 32; compressed and expanded archives to 32 MiB. Record
limits remain sixteen lifetimes, 2000 frames and 10000 events across the whole
trace. These are provisional resource caps, not measured full-limit throughput.

## Verification and next step

Core and producer tests cover canonical bytes, bounded gzip layout, required
versions, empty recordings, shutdown persistence, private permissions, hostile
archive/JSON inputs, resource caps and failed atomic output.



See [offline reconstruction and inspect-trace](N4_TIMING_RECONSTRUCTION.md),
[integrated reproduction](N4_INTEGRATION_VERIFICATION.md) and the
[runtime measurement criteria](N4_PRODUCER_CAPABILITIES.md).

Atomic output closes file and directory descriptors on stream-creation or cleanup
failures. Existing output is preserved on failure. If temporary-file removal fails,
the private temporary file may remain; the directory is still closed and the
cleanup error is reported.

## Additive browser execution archives

Browser [execution v2](N4_BROWSER_EXECUTION_CONTRACT.md) uses the same two-member
layout and bounded reader, with manifest version 2 and explicit
`stage-trace-record-v2`. Manifest/record version mismatch is rejected. No CLI flag
is needed: `ingest-trace` validates the declared version and `inspect-trace`
returns its matching summary. N5 experiment artifacts continue to require their
original host trace v1; this extension does not widen their schemas or effects.
