# Implementation plans

## Active work

- [N4 — Stage-level observability](NEXT_IMPLEMENTATION_PLAN.md) remains active
  for acceptance. Software Steps 0–6 and Step 7 synthetic integration are complete
  locally; [software closeout](../observability/N4_SOFTWARE_CLOSEOUT.md) records
  the evidence. Next run the frozen real Linux capture and paired overhead gates
  in the [integration guide](../observability/N4_INTEGRATION_VERIFICATION.md), then
  attach actual minimum-version/hosted results. Existing N2/N3 meanings remain
  unchanged. The [health audit](../observability/N4_ARCHITECTURE_AUDIT.md) records
  subsequent hardening and current checks.
- [Full roadmap](FULL_IMPLEMENTATION_PLAN.md) defines Phases 1–7. N4 addresses
  Phase 1.2; the Phase 1.3 scenario harness remains subsequent work. Slice numbers
  do not correspond one-to-one to roadmap phases.
- [Quality gates](../measurement/QUALITY_GATES.md) records the latest completed
  local results. Python 3.11/hosted verification remains pending.

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
Implemented software and synthetic checks must remain separate from real measurements.
