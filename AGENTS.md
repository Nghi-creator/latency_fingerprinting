# Repository conventions

Commit subjects use `type: summary`, for example `fix: correct counter sampling`,
`feat: add a scenario adapter`, or `docs: update runtime acceptance`.

# Documentation scope

Keep `docs/` focused on project behavior, contracts, APIs, setup and reusable
contributor/operator procedures. Put personal plans, progress ledgers, audit
writeups and session-specific verification receipts in gitignored `local/`.
Do not add a public writeup for every audit.

# Living private plans

When implementing a slice, keep `local/plans/NEXT_IMPLEMENTATION_PLAN.md` current
with its status, decisions, remaining work and immediate next action. Update
`local/plans/FULL_IMPLEMENTATION_PLAN.md` when phase status, scope or dependencies
change. Track pending user/manual acceptance, failed gates and blockers with their
resolution in `local/plans/PHASE_1_2_RECAP.md`. Keep these files gitignored; do not
replace them with public audit logs. Roll the next-plan file forward at a reviewed
slice handoff, and distinguish software completion from empirical acceptance.
