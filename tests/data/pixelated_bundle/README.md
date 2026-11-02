# Sanitized Pixelated adapter fixture

This directory contains minimal, synthetic-shaped v1 and v2 exports that follow
the real Pixelated Studio Edition research-bundle filenames and columns. They
are software-test inputs, not experimental results. Identifiers are deliberately
anonymous and no URL, credential, device identity or personal path is retained.

`context.json` and `context-v2.json` are intentionally separate from their
bundle directories: Pixelated cannot declare the complete comparison context
required by the research contract, so callers must provide it explicitly.

`producer-sampled-v2.tar` is an artificial v2 export from Pixelated's actual
`createResearchRunExportArtifacts` and TAR writer. Unlike the sparse composer-only
fixture, it serializes browser/engine samples and events through the real CSV
writers and derives current support declarations. It adds sample-sequence CSV
columns (unavailable here) and explicit measurement declarations; it does not
supply genuine process/browser observations. Packet-loss totals currently inherit
source support because the exporter declares packet-loss deltas.
`producer-sampled-v2-source.json` binds the producer revision, archive hash and
eight source-module hashes. Its exact bytes
and independent numerical expectations are checked in
`tests/evaluation/test_sampled_export.py`. To repeat the boundary on a new path:

```sh
node --experimental-strip-types tests/evaluation/export_producer_samples.mjs \
  ../Pixelated-Studio-Edition /tmp/n11-producer-samples.tar
python -m tests.evaluation.producer_boundary /tmp/n11-producer-samples.tar \
  --full-sample-export
```

The helper decodes only the pinned simple unquoted test CSVs. It is not an importer
for user captures and never starts a service, browser, container or fault.
