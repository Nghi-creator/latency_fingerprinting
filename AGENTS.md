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

# Agent workflow

- For non-trivial bugs and unexpected failures, use the `diagnosing-bugs` skill when available. Reproduce the failure, identify the first divergence, and collect evidence before modifying code.
- Use `tdd` for well-specified implementation changes with clear, executable test boundaries. Do not require it for exploratory research or trivial edits.
- Use `handoff` when explicitly requested to transfer unfinished work to a new session. Reference existing private plans instead of duplicating them.
- Prefer focused regression tests during development, followed by relevant broader verification. Report the exact commands, results, and any unverified behavior.
- Distinguish implementation defects from measurement, eligibility, calibration, and scientific-method limitations. An inconclusive result is not necessarily a software failure.
- Never alter frozen evidence, historical results, labels, or scientific acceptance criteria merely to make a run pass.
- Preserve failed and incomplete experimental outcomes. Do not silently retry, discard, or replace them.
- For cross-repository work, verify the relevant Pixelated producer version, source contracts, and compatibility before changing shared behavior.