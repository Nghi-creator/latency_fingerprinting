# N4 synthetic trace fixture release 1.0.0

These nine JSON artifacts are independently authored contract examples, pinned in
[the read-only checker](../../tests/observability/check_reproduction.py). They are
synthetic and use the placeholder producer commit `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
No artifact establishes real capture, overhead or clock synchronization.

- `host`: four admitted frames; queue samples 3, 0, 5 ms, encoder samples 4, 10,
  10 ms, capture-output ages 9, 12, 17 ms. The fourth frame lacks downstream
  endpoints. Queue mean is 8/3 ms, encode mean 8 ms, age mean 38/3 ms. A declared
  12 ms budget gives slack 3, 0, −5 ms and hit fraction 2/3; equality is a hit.
- `browser`: one local presentation/callback pair, 10 and 14 ms relative to its
  origin, yielding 4 ms callback lag. All host methods and budget are unavailable.
- `browser-unavailable`: no admitted frames or events; presentation capability
  explicitly reports `api_unavailable`. Callback lag is unavailable, never zero.

Expected summaries were authored from these integer examples, without calling the
reconstructor. Manifests pin canonical record bytes; separate SHA-256 literals pin
records, manifests and expected summaries. No regeneration command is provided.
Only `trace-manifest.json` and `trace-record.json` belong in a producer bundle;
`expected-summary.json` is a test oracle, not a bundle member.

Run `python -m tests.observability.check_reproduction` from the core checkout.
The [integration guide](../../docs/observability/N4_INTEGRATION_VERIFICATION.md)
reproduces these same records using both actual producer collectors/exporters.
