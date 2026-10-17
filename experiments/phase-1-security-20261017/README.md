# Focused security review — 2026-10-17

This review follows the [broad check and CodeQL follow-up](../phase-1-final-check-20261016/README.md).
It examines both repositories' TLS exceptions, credentials, process execution,
filesystem/input boundaries and CI trust boundaries. [Structured results](results.json)
retain baseline identities, changed-source hashes and local verification logs.
Prior uncommitted core documentation from the CodeQL follow-up was preserved.

## Findings fixed

**Hosted browser TLS:** the pairing smoke used a context-wide HTTPS error bypass
while visiting real hosted services. It now keeps context certificate validation
on and permits only chains containing the freshly generated companion key through
Chromium's [SPKI exception mechanism](https://chromium.googlesource.com/chromium/src/+/main/services/network/public/cpp/network_switches.cc).
A real local Chromium test uses the same browser/context factory as the smoke:
the owned self-signed endpoint succeeds, a separate self-signed key fails with
`ERR_CERT_AUTHORITY_INVALID`, and the owned endpoint remains usable afterward.
Invalid PEM input also fails before launching a browser. No machine trust store
or process-wide TLS setting is changed.

**Smoke credential/workspace hardening:** the probe credential previously embedded
only a timestamp. It now contains 192 cryptographically random bits. Certificates
are allocated at runtime in an atomically created private temporary directory;
configuration no longer reserves a predictable shared temporary pathname. Cleanup
only removes the allocated workspace. Contract-only mode allocates no certificate
workspace.

**Merge policy:** the privileged Dependabot policy did not require the newly added
Repository Quality lanes. It now requires successful current production-Node and
Node 26 checks, with corresponding strict branch rules. Completion of Repository
Quality also triggers policy evaluation. Missing/failing checks or missing rules
leave the PR unmerged. Ruleset settings were not changed; if auto-merge is enabled,
the documented new required checks must be configured before it can qualify again.
Tests cover each missing/failing lane and production Node pin drift.

## Reviewed without additional changes

Core untrusted JSON/archive readers retain size, expansion, regular-file/no-follow,
member-name and checksum controls. They do not extract untrusted archive paths or
execute evidence. Producer command execution uses argument arrays; controlled
pressure helpers retain bounded ownership/cleanup. API authorization, companion
guest/host restrictions, renderer isolation/IPC and cloud-download DNS pinning were
reviewed with their existing regression coverage. Remaining UI shuffle/widget IDs
and non-authorizing identifiers do not act as authentication secrets.

The previously dismissed network-to-report alerts remain intentional content writes
to locally determined paths. This pass does not suppress or dismiss alerts. Their destinations are determined before network data is received.

## Actual verification and remaining gates

- **2,032 core tests**, **93.55% branch-inclusive coverage**, Ruff/format, dependency
  consistency, all 25 schemas/registry and N1–N5/browser reproduction checks pass.
- **788 producer Node tests**, one existing external-artifact skip; full workspace
  lint/typechecks/builds, browser interactions, offline pairing contract and the
  real two-certificate TLS isolation test pass.
- Five npm advisory scopes and desktop build-chain gate pass with zero advisories.
  Temporary isolated `pip-audit` reports zero known advisories for 20 installed
  third-party distributions; the editable first-party package is intentionally
  excluded from that database lookup and reviewed/tested as source.
- All workflow YAML parses. The existing CI secret-pattern scan has no matching
  tracked working-tree files; it is a pattern check, not an exhaustive secret audit.

The TLS regression runs in the existing hosted contract chain after the desktop
build, so CI tests the same certificate generator and browser factory. No dependency
lock, frozen schema/fixture, matching policy, threshold or live recording changed.
These are local macOS Python 3.13 / Node 26 results, not hosted CodeQL, fresh image
scans, minimum-version/Linux validation or manual desktop acceptance. The ordinary
hosted security/quality jobs and manual [acceptance ledger](../../docs/scenarios/N5_RUNTIME_ACCEPTANCE.md)
remain required. No deployment, live hosted mutation, PR merge or ruleset update was
performed. Raw logs are under ignored `local/phase-1-security-20261017/`.
