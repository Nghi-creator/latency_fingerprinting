# N4 inherited runtime acceptance

**Updated:** 2026-10-10. **Status:** pending; carried into N5 without waiving gates.
[Archived N4 software closeout](../archive/observability/N4_SOFTWARE_CLOSEOUT.md)
and [audit](../archive/observability/N4_ARCHITECTURE_AUDIT.md) record delivered
software and historical local checks. [N5](../plans/NEXT_IMPLEMENTATION_PLAN.md)
can supply shared experiment lifecycle/control while these gates remain open.

The [capability specification](N4_PRODUCER_CAPABILITIES.md) retains the frozen
criteria and [integration guide](N4_INTEGRATION_VERIFICATION.md) retains commands.
No synthetic run, test count or factory discovery closes these gates:

- Actual Linux/Xvfb/PulseAudio X11→queue→VP8 capture with a draining receiver,
  exact versions/config/commands and fresh recording after 10 s warm-up for 30 s.
  Current camera has no interactive recording reset; N5 must implement/verify
  appropriate producer control before claiming this case.
- At least 500 usable queue/encode pairs, ≥95% joint coverage with unique PTS
  evidence and zero nominal collector drops; tiny-capacity, interruption/restart,
  disable/re-enable, two-peer and supported/unsupported browser cases.
- Five paired disabled/enabled CPU/FPS trials in frozen order, each disabled
  baseline ≥27 fps; median CPU increase ≤5 percentage points and FPS change ≥−5%.
  No failure/nominal loss; retain all values, ≥1000-probe diagnostic and export time.
- Actual minimum-version/hosted results, real browser callbacks and picker
  interaction remain separate unverified evidence.

No deadline/method thresholds or artifact contracts change at the transition.
Update this live ledger only with new evidence; historical records remain intact.
