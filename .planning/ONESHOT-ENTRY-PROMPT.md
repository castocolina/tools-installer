# tools-installer v0.49.0 - Claude Code Autonomous Run Driver

**DRAFT — not yet reviewed or run.** Copy-paste driver for a single long-running
Claude Code session across the remaining roadmap (expect a multi-hour,
possibly multi-day run). All operational detail — model routing, per-phase
checklist, gates, rules — lives in `.planning/ONESHOT-RULES.md`; this file
only starts the run and points there.

**Milestone state is a moving target — this file is a driver, not a status
report.** Do not trust any phase list or date baked into this prose; it goes
stale the moment a phase completes or a new one is inserted (this happened
once already — see git history on this file). Before pasting the block
below, read `.planning/ROADMAP.md` and `.planning/STATE.md` fresh, confirm
the `--only`/`--from`/`--to` flags on the command line actually match
current reality, and update the flags (not this prose) if they don't. Any
phase already past `/gsd-discuss-phase` has a locked `{N}-CONTEXT.md` in its
phase directory — an autonomous run goes straight to `/gsd-plan-phase` for
those, never re-discussing locked scope.

## How To Run

From the repository root:

```sh
claude --dangerously-skip-permissions
```

`--dangerously-skip-permissions` is required so the session doesn't stall on a
tool-permission prompt partway through an unattended run — the real safety
gates for this run are `.planning/ONESHOT-RULES.md`'s own Non-Negotiable
Rules (rules 5 and 9), not Claude Code's generic per-call confirmation.

Paste the block below as the first message, then leave it running.

---

▼▼▼ COPY FROM HERE ▼▼▼

/gsd-autonomous --only 16 --converge

You are the Claude Code orchestrator for the tools-installer v0.49.0
milestone. The command line above is authoritative for scope (`--only`,
`--from`, `--to`) — read `.planning/ROADMAP.md` and `.planning/STATE.md`
fresh to confirm which phase(s) that actually resolves to before doing
anything else; do not infer scope from this prose, which is reused
unchanged across different invocations with different flags.

Any phase in scope that already has a locked `{N}-CONTEXT.md` (discuss-phase
already ran) skips straight to `/gsd-plan-phase` — do not re-run
`/gsd-discuss-phase` or re-open scope already locked in that file. A phase
with no CONTEXT.md yet needs discuss-phase first, same as any normal run.

Read `.planning/ONESHOT-RULES.md` in full now, and again at the start of
every turn, along with `.planning/STATE.md`, `.planning/ROADMAP.md`, and
`.planning/REQUIREMENTS.md`. Follow `.planning/ONESHOT-RULES.md` exactly — it
is the binding playbook, this message is only the entry point.

Objective: run the requested scope to completion, unattended, stopping only
for a real destructive anomaly, an unrecoverable tool/authentication
failure, or a circuit breaker (`.planning/ONESHOT-RULES.md` Non-Negotiable
Rule 9). Never mutate the user's
real shell configuration (`~/.myshellrc`, `~/.zshrc`, `~/.bashrc`, etc.) or
perform a real package install/uninstall against this actual machine outside
a sandboxed test or a disposable container — see Rule 14's three-tier
verification model, which exists precisely so this never requires a mid-run
stop to ask. Defer everything a human needs to see to the end-of-phase UAT
report (`workflow.human_verify_mode: "end-of-phase"`) and the final
`RUN-REPORT.md` — the user reviews once, after waking up, not mid-run. Do
not ask the user to send a continuation command at any point between here
and milestone close.

Treat verification as an autonomous convergence loop: any failing test,
review finding, divergent TUI behavior, incomplete evidence, or gap report
must be planned, fixed, re-tested, and independently re-reviewed until clean.
Do not halt merely because a previous corrective attempt failed; halt only
for a real safety/confirmation condition or a demonstrated repeated
zero-progress tool failure.

If a `gaps_found` verification result appears at any phase, choose "Run gap
closure" yourself and continue the convergence loop described in
`.planning/ONESHOT-RULES.md` Non-Negotiable Rules, rule 10.

▲▲▲ COPY TO HERE ▲▲▲
