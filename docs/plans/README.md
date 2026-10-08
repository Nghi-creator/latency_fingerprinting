# Implementation plans

## Active work

- [N4 — Stage-level observability](NEXT_IMPLEMENTATION_PLAN.md) is the active
  implementation plan. Steps 0–7 are ready to start and not implemented. Begin
  with both repository baselines, then timing/clock/identity/capability definitions.
  The scope spans Pixelated producer hooks/export and separate Python trace
  validation/inspection, preserving all existing N2/N3 meanings and pins.
- [Full roadmap](FULL_IMPLEMENTATION_PLAN.md) defines Phases 1–7. N4 addresses
  Phase 1.2; the Phase 1.3 scenario harness remains subsequent work. Slice numbers
  do not correspond one-to-one to roadmap phases.
- [Quality gates](../measurement/QUALITY_GATES.md) records the latest completed
  local baseline: 1,539 tests and 93.58% branch-inclusive coverage. Python 3.11/
  hosted verification remains pending, independently of starting N4.

## Completed work

- [Archived plans](archive/README.md) retain N1 measurement semantics, N2
  observation adoption and N3 analytical/fingerprint/matching execution gates.
- [Milestone archive](../archive/README.md) retains P0/N1/N2/N3 closeouts, progress
  and health audits. Historical counts and pending checks remain historical.
- [Current reference index](../README.md) links the implemented contracts,
  registry, adoption, analytical APIs, commands, fixtures and architecture.
  Those guides remain active because the software still uses them.

Archive completed plans and milestone records when transitioning slices. Preserve
their results and limitations, update inbound links, and retain normative
contracts/approved policies and reproduction artifacts in their canonical places.
Planned instrumentation must not be described as delivered evidence.
