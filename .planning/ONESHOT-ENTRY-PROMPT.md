# tools-installer v0.49.0 - Claude Code Autonomous Run Driver

**DRAFT — not yet reviewed or run.** Copy-paste driver for a single long-running
Claude Code session across the remaining roadmap (expect a multi-hour,
possibly multi-day run). All operational detail — model routing, per-phase
checklist, gates, rules — lives in `.planning/ONESHOT-RULES.md`; this file
only starts the run and points there.

**Current milestone state (2026-09-15):** Phase 15 (Catalog accuracy, Doctor
refresh, version parsing, ownership attribution) is complete. Six decimal
phases (15.1-15.6) were inserted afterward from live UAT feedback on the
shipped v1 app and already have discussed context (`{N}-CONTEXT.md` in each
phase directory) — none are planned or executed yet:

- 15.1 — Catalog post-update refresh, staleness, and version-status color legend
- 15.2 — Install output buffering and live-progress clarity (streaming)
- 15.3 — Registry `audience` field audit (63 of 89 `registry.toml` entries)
- 15.4 — Catalog ownership visibility and Uninstall screen real manager attribution
- 15.5 — Relax `set_login_shell`'s immutable-host block from silence to an honest
  explanation (chsh is confirmed absent on Bazzite; see its CONTEXT.md for the
  full root-cause investigation)
- 15.6 — Terminal-emulator default-shell configuration (Konsole/kitty/WezTerm) —
  the actual "zsh just works" fix split out of 15.5

All six already have locked decisions in their CONTEXT.md files — an
autonomous run should go straight to `/gsd-plan-phase` for each rather than
re-discussing scope.

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

/gsd-autonomous --to 15.6 --converge

You are the Claude Code orchestrator for the remaining tools-installer
v0.49.0 milestone: six already-discussed decimal phases (15.1 through 15.6,
inserted from live UAT feedback — see each phase's `{N}-CONTEXT.md` for
locked decisions) still need planning and execution.

Only implement through phase 15.6. Every phase in this range already has a
CONTEXT.md — skip straight to `/gsd-plan-phase` for each; do not re-run
`/gsd-discuss-phase` or re-open scope already locked in those files.

Read `.planning/ONESHOT-RULES.md` in full now, and again at the start of
every turn, along with `.planning/STATE.md`, `.planning/ROADMAP.md`, and
`.planning/REQUIREMENTS.md`. Follow `.planning/ONESHOT-RULES.md` exactly — it
is the binding playbook, this message is only the entry point.

Objective: run the milestone to completion, unattended, from the earliest
incomplete phase through Phase 15.6, stopping only for a real destructive
anomaly, an unrecoverable tool/authentication failure, or a circuit breaker
(`.planning/ONESHOT-RULES.md` Non-Negotiable Rule 9). Never mutate the user's
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
